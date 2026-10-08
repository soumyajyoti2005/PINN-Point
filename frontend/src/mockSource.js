import { validateEvent } from './schemas'

class MockSource {
  constructor(onEvent) {
    this.onEvent = onEvent
    this.timer = null
    this.minute = 0
    this.playing = false
    this.speed = 1
    this.nodes = []
    this.blockedPipe = 'P-046-044' // A valid pipe from the mock fixture
    this.blockedUpstreamNode = 'MH-046'
  }

  // Basic mock fixture nodes initialization
  async init() {
    try {
      const net = await import('./mock/network.json')
      this.nodes = net.default.nodes.filter(n => n.has_sensor).map(n => n.id)
    } catch (e) {
      console.warn("MockSource failed to load mock network", e)
      this.nodes = ['MH-009', 'MH-022', 'MH-046'] // fallback
    }
  }

  subscribe(callback) {
    this.onEvent = callback
  }

  play() {
    if (this.playing) return
    this.playing = true
    this.tick()
  }

  pause() {
    this.playing = false
    if (this.timer) clearTimeout(this.timer)
  }

  seek(minute) {
    this.minute = Math.max(0, Math.min(120, minute))
    this.emitCurrentState()
  }

  setSpeed(x) {
    this.speed = x
    if (this.playing) {
      this.pause()
      this.play()
    }
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

    const delayMs = 1000 / this.speed
    this.timer = setTimeout(() => this.tick(), delayMs)
  }

  emitCurrentState() {
    const t = this.minute
    const ts = new Date().toISOString()
    
    // Triangular hyetograph: peaks at 60 mm/hr near min 30
    const rain = Math.max(0, 60 - Math.abs(t - 30)*2)
    
    const rainEvent = {
      v: 1, type: "rain_update",
      zone_id: "kolkata-amherst",
      ts,
      intensity_mm_hr: rain
    }
    
    if (validateEvent("rain_update", rainEvent)) {
      this.onEvent(rainEvent)
    }

    // Nodes
    this.nodes.forEach((nodeId, idx) => {
      // Fake expected level
      const scale = 0.5 + (idx % 5) * 0.1
      let exp = (rain / 60) * scale
      let obs = exp

      // Blockage injection
      if (nodeId === this.blockedUpstreamNode && t >= 15) {
        obs += Math.min(0.5, (t - 15) * 0.015)
      }

      const levelEvent = {
        v: 1, type: "level_update",
        node_id: nodeId,
        ts,
        level_m: Number(obs.toFixed(3))
      }
      
      if (validateEvent("level_update", levelEvent)) {
        this.onEvent(levelEvent)
      }
    })

    // Tick event (UI only)
    this.onEvent({ type: 'tick', time_min: t })

    // Detection every 5 steps
    if (t % 5 === 0) {
      // Confidence rises from 0.1 to 0.6 over the storm
      const conf = Math.min(0.99, 0.1 + (t / 120) * 0.5)
      
      const detectionEvent = {
        v: 1, type: "detection",
        detection: {
          detection_id: Date.now(),
          ts,
          top_pipe_id: this.blockedPipe,
          confidence: Number(conf.toFixed(3)),
          candidates: [
            { pipe_id: this.blockedPipe, score: Number(conf.toFixed(3)) },
            { pipe_id: "P-041-040", score: 0.15 },
            { pipe_id: "P-013-007", score: 0.10 },
            { pipe_id: "P-038-037", score: 0.05 },
            { pipe_id: "P-016-005", score: 0.02 }
          ],
          status: "new"
        }
      }
      if (validateEvent("detection", detectionEvent)) {
        this.onEvent(detectionEvent)
      }
    }
  }
}

class LiveSource {
  constructor() {
    this.onEvent = null
    this.wsUrl = import.meta.env.VITE_WS_URL
    this.token = import.meta.env.VITE_WS_TOKEN
    this.ws = null
  }

  subscribe(callback) {
    this.onEvent = callback
  }

  play() {
    console.log("LiveSource: connecting to", this.wsUrl)
    // Minimal placeholder
  }

  pause() {
    if (this.ws) this.ws.close()
  }

  seek(minute) { /* no-op for live */ }
  
  setSpeed(x) { /* no-op for live */ }
}

export function createDataSource(type, onEvent) {
  let source = null
  if (type === 'live') {
    source = new LiveSource()
  } else {
    source = new MockSource()
    source.init()
  }
  source.subscribe(onEvent)
  return source
}
