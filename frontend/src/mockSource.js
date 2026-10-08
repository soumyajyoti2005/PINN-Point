import { validateEvent } from './schemas'

class MockSource {
  constructor(onEvent) {
    this.onEvent = onEvent
    this.timer = null
    this.minute = 0
    this.playing = false
    this.speed = 1
    this.nodes = []
    this.blockedPipe = 'P-046-044'
    this.blockedUpstreamNode = 'MH-046'
  }

  async init() {
    try {
      const net = await import('./mock/network.json')
      this.nodes = net.default.nodes.filter(n => n.has_sensor).map(n => n.id)
    } catch (e) {
      console.warn("MockSource failed to load mock network", e)
      this.nodes = ['MH-009', 'MH-022', 'MH-046']
    }
  }

  subscribe(callback) { this.onEvent = callback }
  play() { if (!this.playing) { this.playing = true; this.tick() } }
  pause() { this.playing = false; if (this.timer) clearTimeout(this.timer) }
  seek(minute) { this.minute = Math.max(0, Math.min(120, minute)); this.emitCurrentState() }
  setSpeed(x) {
    this.speed = x
    if (this.playing) { this.pause(); this.play() }
  }

  tick() {
    if (!this.playing) return
    this.emitCurrentState()
    this.minute += 1
    if (this.minute > 120) {
      this.minute = 120
      this.pause()
      return
    }
    this.timer = setTimeout(() => this.tick(), 1000 / this.speed)
  }

  emitCurrentState() {
    const t = this.minute
    const ts = new Date().toISOString()
    const rain = Math.max(0, 60 - Math.abs(t - 30)*2)
    
    this.onEvent({ v: 1, type: "rain_update", zone_id: "kolkata-amherst", ts, intensity_mm_hr: rain })

    this.nodes.forEach((nodeId, idx) => {
      const scale = 0.5 + (idx % 5) * 0.1
      let obs = (rain / 60) * scale
      if (nodeId === this.blockedUpstreamNode && t >= 15) {
        obs += Math.min(0.5, (t - 15) * 0.015)
      }
      this.onEvent({ v: 1, type: "level_update", node_id: nodeId, ts, level_m: Number(obs.toFixed(3)) })
    })

    this.onEvent({ type: 'tick', time_min: t })

    if (t % 5 === 0) {
      const conf = Math.min(0.99, 0.1 + (t / 120) * 0.5)
      this.onEvent({
        v: 1, type: "detection",
        detection: {
          detection_id: Date.now(), ts, top_pipe_id: this.blockedPipe, confidence: Number(conf.toFixed(3)),
          candidates: [
            { pipe_id: this.blockedPipe, score: Number(conf.toFixed(3)) },
            { pipe_id: "P-041-040", score: 0.15 }
          ],
          status: "new"
        }
      })
    }
  }
}

class ReplaySource {
  constructor(onEvent, scenarioId) {
    this.onEvent = onEvent
    this.scenarioId = scenarioId
    this.timer = null
    this.minute = 0
    this.playing = false
    this.speed = 1
    this.data = null
  }

  async init() {
    const apiUrl = import.meta.env.VITE_API_URL
    const res = await fetch(`${apiUrl}/api/v1/replay/${this.scenarioId}`)
    this.data = await res.json()
  }

  subscribe(callback) { this.onEvent = callback }
  play() { if (!this.playing) { this.playing = true; this.tick() } }
  pause() { this.playing = false; if (this.timer) clearTimeout(this.timer) }
  seek(minute) { this.minute = Math.max(0, Math.min(120, minute)); this.emitCurrentState() }
  setSpeed(x) {
    this.speed = x
    if (this.playing) { this.pause(); this.play() }
  }

  tick() {
    if (!this.playing || !this.data) return
    this.emitCurrentState()
    this.minute += 1
    if (this.minute >= this.data.rain.length) {
      this.minute = this.data.rain.length - 1
      this.pause()
      return
    }
    this.timer = setTimeout(() => this.tick(), 1000 / this.speed)
  }

  emitCurrentState() {
    if (!this.data) return
    const t = this.minute
    const ts = new Date().toISOString()
    
    const rain = this.data.rain[t] || 0
    this.onEvent({ v: 1, type: "rain_update", zone_id: "kolkata-amherst", ts, intensity_mm_hr: rain })

    for (const [nodeId, levels] of Object.entries(this.data.levels)) {
      const lvl = levels[t]
      if (lvl !== null && lvl !== undefined) {
        this.onEvent({ v: 1, type: "level_update", node_id: nodeId, ts, level_m: Number(lvl.toFixed(3)) })
      }
    }

    this.onEvent({ type: 'tick', time_min: t })

    // Find the latest detection
    let latestDet = null
    for (const d of this.data.detections || []) {
      if (d.minute <= t) {
        latestDet = d
      }
    }
    if (latestDet) {
      this.onEvent({
        v: 1, type: "detection",
        detection: latestDet.detection
      })
    }
  }
}

class LiveSource {
  constructor() {
    this.onEvent = null
  }
  subscribe(callback) { this.onEvent = callback }
  play() { }
  pause() { }
  seek(minute) { }
  setSpeed(x) { }
}

export function createDataSource(type, onEvent) {
  let source = null
  if (type === 'live') {
    source = new LiveSource()
  } else if (type === 'mock') {
    source = new MockSource(onEvent)
    source.init()
  } else {
    source = new ReplaySource(onEvent, type) // type is scenario_id here
    source.init()
  }
  return source
}
