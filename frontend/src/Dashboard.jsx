import React, { useState, useEffect, useMemo } from 'react'
import { Droplet, MapDroplet } from './Droplet'
import { createDataSource } from './mockSource'

export default function Dashboard({ onBack }) {
  const [network, setNetwork] = useState({ nodes: [], pipes: [] })
  const [levels, setLevels] = useState({})
  const [rain, setRain] = useState(0)
  const [timeStep, setTimeStep] = useState(0) // 0 to 120
  const [detection, setDetection] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  
  // Player state
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1) // 1x, 4x, 16x

  const [scenarios, setScenarios] = useState([])
  const [selectedScenario, setSelectedScenario] = useState('mock')

  // Map coordinate scaling
  const [bounds, setBounds] = useState({ minX: 0, maxX: 100, minY: 0, maxY: 100 })

  const [source, setSource] = useState(null)

  useEffect(() => {
    // Load network
    const loadNetwork = async () => {
      const apiUrl = import.meta.env.VITE_API_URL
      let data
      try {
        if (apiUrl) {
          const res = await fetch(`${apiUrl}/api/v1/network`)
          data = await res.json()
          
          try {
            const scenRes = await fetch(`${apiUrl}/api/v1/scenarios`)
            const scenData = await scenRes.json()
            if (scenData && scenData.length > 0) {
              setScenarios(scenData)
              setSelectedScenario(scenData[0].scenario_id)
            }
          } catch (e) {
            console.warn("Could not load scenarios", e)
          }
        } else {
          const mockNet = await import('./mock/network.json')
          data = mockNet.default
        }
        
        setNetwork(data)

        const lons = data.nodes.map(n => n.lon)
        const lats = data.nodes.map(n => n.lat)
        setBounds({
          minX: Math.min(...lons), maxX: Math.max(...lons),
          minY: Math.min(...lats), maxY: Math.max(...lats)
        })
      } catch (err) {
        console.error("Could not fetch network", err)
      }
    }
    loadNetwork()
  }, [sourceType])

  useEffect(() => {
    const s = createDataSource(selectedScenario, (event) => {
      if (event.type === 'tick') {
        setTimeStep(Math.floor(event.time_min || 0))
      } else if (event.type === 'rain_update') {
        setRain(event.intensity_mm_hr)
      } else if (event.type === 'level_update') {
        setLevels(prev => ({ ...prev, [event.node_id]: event.level_m }))
      } else if (event.type === 'detection') {
        setDetection(event.detection)
      }
    })
    
    setSource(s)
    s.setSpeed(speed)
    if (playing) s.play()

    return () => s.pause()
  }, [selectedScenario])

  useEffect(() => {
    if (!source) return
    source.setSpeed(speed)
    if (playing) {
      source.play()
    } else {
      source.pause()
    }
  }, [playing, speed, source])

  const handleSeek = (e) => {
    const val = parseInt(e.target.value)
    if (source) source.seek(val)
  }

  // Coordinate projection
  const pad = 0.1
  const mapW = 800
  const mapH = 600
  const dx = bounds.maxX - bounds.minX
  const dy = bounds.maxY - bounds.minY
  const projX = (lon) => {
    if (dx === 0) return mapW/2;
    return mapW * pad + (lon - bounds.minX) / dx * mapW * (1 - 2*pad)
  }
  const projY = (lat) => {
    if (dy === 0) return mapH/2;
    // lat increases UP, SVG y increases DOWN
    return mapH * pad + (bounds.maxY - lat) / dy * mapH * (1 - 2*pad)
  }

  const topPipe = detection?.candidates?.[0]
  const hasBlockageFlagged = topPipe && topPipe.score >= 0.3

  // Line chart data for selected sensor
  // For the prototype, we don't have historical data accumulated in state,
  // we just simulate a smooth curve in the component based on current timestep
  const renderChart = () => {
    if (!selectedNode) return null
    const ptsObserved = []
    const ptsExpected = []
    const nodeObj = network.nodes.find(n => n.id === selectedNode)
    const isMockBlockedUpstream = selectedNode === 'MH-034' // just a hardcoded mock node for chart
    
    for (let t = 0; t <= 120; t+=5) {
      const rainShape = Math.max(0, 60 - Math.abs(t - 30)*2) / 60
      let exp = rainShape * 0.8
      let obs = exp
      if (t >= 15 && isMockBlockedUpstream) {
         obs += Math.min(0.4, (t-15)*0.01) // ramps up
      }
      
      const px = (t / 120) * 100
      const ey = 50 - (exp * 40)
      const oy = 50 - (obs * 40)
      
      ptsExpected.push(`${px},${ey}`)
      ptsObserved.push(`${px},${oy}`)
    }

    return (
      <svg width="100%" height="100" viewBox="0 0 100 50" preserveAspectRatio="none">
         <polyline points={ptsExpected.join(' ')} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="2" />
         <polyline points={ptsObserved.join(' ')} fill="none" stroke="var(--accent-bright)" strokeWidth="1.5" />
      </svg>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* Header */}
      <header style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--panel)', borderBottom: '1px solid var(--hairline)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Droplet width={24} level={0.5} variant="solid" />
            <span style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>PINNpoint</span>
          </div>
            {scenarios.length > 0 && (
              <select 
                value={selectedScenario} 
                onChange={e => setSelectedScenario(e.target.value)}
                style={{ marginLeft: '16px', padding: '4px 8px', borderRadius: '4px', background: 'var(--well)', border: '1px solid var(--hairline)', color: 'var(--text)' }}
              >
                <option value="mock">Mock storm replay</option>
                {scenarios.map(s => (
                  <option key={s.scenario_id} value={s.scenario_id}>{s.description}</option>
                ))}
              </select>
            )}
            {scenarios.length === 0 && (
              <span className="pill-label">Mock data</span>
            )}
        </div>
        <button className="btn-outline" onClick={onBack}>Back</button>
      </header>

      {/* Main Content */}
      <div style={{ padding: '24px', flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
        
        {/* LEFT COLUMN: Map + Replay controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', gridColumn: 'span 2' }}>
          
          <div className="well" style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--hairline)' }}>
              <h2 style={{ fontSize: '1.25rem' }}>Drain network</h2>
            </div>
            
            <div style={{ flex: 1, minHeight: '500px', position: 'relative', overflow: 'hidden' }}>
              <svg width="100%" height="100%" viewBox={`0 0 ${mapW} ${mapH}`} style={{ display: 'block' }} aria-label="Network Map">
                
                {/* Pipes: channel effect */}
                {network.pipes?.map(p => {
                  const n1 = network.nodes.find(n => n.id === p.from_node)
                  const n2 = network.nodes.find(n => n.id === p.to_node)
                  if (!n1 || !n2) return null
                  const x1 = projX(n1.lon), y1 = projY(n1.lat)
                  const x2 = projX(n2.lon), y2 = projY(n2.lat)
                  
                  const isSuspect = hasBlockageFlagged && topPipe.pipe_id === p.id

                  return (
                    <g key={p.id}>
                      {/* Base stroke */}
                      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1b3a55" strokeWidth="12" strokeLinecap="round" />
                      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2d5878" strokeWidth="6" strokeLinecap="round" />
                      
                      {/* Blocked pipe */}
                      {isSuspect && (
                        <>
                          <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--alert)" strokeWidth="7" strokeLinecap="round" />
                          <circle cx={(x1+x2)/2} cy={(y1+y2)/2} r="12" fill="none" stroke="var(--alert)" className="pulse-ring" />
                          <text x={(x1+x2)/2} y={(y1+y2)/2 - 16} fill="var(--alert)" fontSize="12" textAnchor="middle" fontWeight="bold">
                            {p.id}
                          </text>
                        </>
                      )}
                    </g>
                  )
                })}

                {/* Nodes */}
                {network.nodes?.map(n => {
                  const x = projX(n.lon), y = projY(n.lat)
                  const lvl = levels[n.id] || 0
                  const isSelected = selectedNode === n.id

                  if (n.is_outfall) {
                    return (
                      <g key={n.id} transform={`translate(${x},${y})`}>
                        <rect x="-10" y="-10" width="20" height="20" rx="4" fill="var(--muted)" />
                        <text x="0" y="22" fill="var(--muted)" fontSize="10" textAnchor="middle">Outfall</text>
                      </g>
                    )
                  }

                  if (n.has_sensor) {
                    return (
                      <MapDroplet 
                        key={n.id} 
                        x={x} 
                        y={y} 
                        level={lvl} 
                        selected={isSelected} 
                        onClick={() => setSelectedNode(n.id)} 
                      />
                    )
                  }

                  return <circle key={n.id} cx={x} cy={y} r="6" fill="#3b5a75" />
                })}
              </svg>
            </div>

            {/* Map Legend */}
            <div style={{ padding: '16px', display: 'flex', gap: '24px', borderTop: '1px solid var(--hairline)', background: 'var(--panel)', borderBottomLeftRadius: '12px', borderBottomRightRadius: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}>
                <MapDroplet x={10} y={10} level={0.5} size={0.8} />
                <span style={{ marginLeft: '12px' }}>Droplet fill = water level</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}>
                <circle cx="6" cy="6" r="6" fill="#3b5a75" />
                <span>Grey dot = no sensor</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}>
                <div style={{ width: '16px', height: '4px', background: 'var(--alert)', borderRadius: '2px' }}></div>
                <span>Coral = likely blockage</span>
              </div>
            </div>
          </div>

          {/* Replay Bar */}
          <div className="panel" style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <button className="btn-filled" style={{ padding: '8px 16px' }} onClick={() => setPlaying(!playing)}>
              {playing ? 'Pause' : 'Play'}
            </button>
            <div style={{ display: 'flex', gap: '8px' }}>
              {[1, 4, 16].map(s => (
                <button 
                  key={s} 
                  className={speed === s ? 'btn-filled' : 'btn-outline'} 
                  style={{ padding: '4px 12px', fontSize: '0.9rem' }}
                  onClick={() => setSpeed(s)}
                >
                  {s}x
                </button>
              ))}
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '16px' }}>
              <input 
                type="range" 
                min="0" 
                max="120" 
                value={timeStep} 
                onChange={handleSeek}
                style={{ flex: 1, cursor: 'pointer' }} 
                aria-label="Replay timeline"
              />
              <span className="text-muted" style={{ fontVariantNumeric: 'tabular-nums' }}>{timeStep} / 120 min</span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          <div className="panel">
            <h3 style={{ marginBottom: '16px' }}>Suspect pipes</h3>
            {!detection ? (
              <p className="text-muted">Listening. No blockage flagged yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {detection.candidates.slice(0, 5).map((c, i) => {
                  const isTop = i === 0 && c.score >= 0.3
                  const pVal = Math.round(c.score * 100)
                  return (
                    <div key={c.pipe_id} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ 
                        width: '28px', height: '28px', 
                        borderRadius: '50% 50% 50% 0', transform: 'rotate(-45deg)',
                        background: isTop ? 'var(--alert)' : 'var(--drop-body)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.5)'
                      }}>
                        <span style={{ transform: 'rotate(45deg)', fontSize: '0.8rem', fontWeight: 'bold', color: isTop ? '#08121e' : 'var(--text)' }}>
                          {i + 1}
                        </span>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.95rem' }}>
                          <span style={{ fontWeight: 600 }}>{c.pipe_id}</span>
                          <span style={{ fontWeight: 600, color: isTop ? 'var(--alert-text)' : 'inherit' }}>{pVal}%</span>
                        </div>
                        <div style={{ height: '6px', background: '#08121e', borderRadius: '3px', boxShadow: '0 0 0 1px var(--hairline)', overflow: 'hidden' }}>
                          <div style={{ width: `${pVal}%`, height: '100%', background: isTop ? 'var(--alert)' : 'var(--accent)' }}></div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="panel">
            <h3 style={{ marginBottom: '16px' }}>Rain intensity</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
              <Droplet width={76} level={rain / 100} glow />
              <div>
                <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>{rain.toFixed(1)} <span style={{ fontSize: '1rem', fontWeight: 400, color: 'var(--muted)' }}>mm/hr</span></div>
                <div className="text-muted" style={{ fontSize: '0.9rem' }}>Storm minute {timeStep} of 120</div>
              </div>
            </div>
          </div>

          <div className="panel">
            <h3 style={{ marginBottom: '16px' }}>Selected sensor</h3>
            {!selectedNode ? (
              <p className="text-muted" style={{ fontSize: '0.9rem' }}>Click a droplet on the map to view levels.</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600 }}>{selectedNode}</span>
                  <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--accent-bright)' }}>— Observed</span>
                    <span style={{ color: 'var(--muted)' }}>-- Expected</span>
                  </div>
                </div>
                <div style={{ height: '100px', background: 'var(--well)', borderRadius: '8px', padding: '8px' }}>
                  {renderChart()}
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
