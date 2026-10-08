import React from 'react'
import { Droplet } from './Droplet'

export default function Landing({ onStart }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      
      {/* Dark Band: Hero & Nav */}
      <div style={{ background: 'var(--bg)' }}>
        <div style={{ maxWidth: '1160px', margin: '0 auto', padding: '24px 16px' }}>
          
          <nav style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '64px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Droplet width={32} level={0.5} variant="solid" />
              <span style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>PINNpoint</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
              <a href="#how" className="text-muted" style={{ fontWeight: 600 }}>How it works</a>
              <a href="#proto" className="text-muted" style={{ fontWeight: 600 }}>The prototype</a>
              <button className="btn-filled" onClick={onStart}>Open dashboard</button>
            </div>
          </nav>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '48px', alignItems: 'center', paddingBottom: '64px' }}>
            <div style={{ flex: '1 1 500px' }}>
              <div className="pill-label" style={{ marginBottom: '24px' }}>Storm drain blockage finder</div>
              <h1 style={{ fontSize: 'clamp(40px, 5vw, 68px)', marginBottom: '24px', letterSpacing: '-0.02em' }}>
                Know which pipe is choking before the street floods.
              </h1>
              <p className="text-muted" style={{ fontSize: '1.125rem', marginBottom: '40px', maxWidth: '540px' }}>
                PINNpoint compares what the physics says each level sensor should read with what it actually reads, then ranks the pipe segments most likely to be blocked.
              </p>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <button className="btn-filled" onClick={onStart}>Watch a storm replay</button>
                <a href="#how" className="btn-outline" style={{ display: 'inline-flex', alignItems: 'center' }}>See how it works</a>
              </div>
            </div>

            <div style={{ 
              flex: '1 1 400px', 
              background: '#0d1f33', 
              borderRadius: '32px', 
              boxShadow: '0 0 0 1px var(--hairline)', 
              position: 'relative', 
              height: '400px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden'
            }}>
              <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                {/* Expanding ripple ellipse */}
                <svg style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '300px', height: '150px' }}>
                  <ellipse cx="150" cy="75" rx="140" ry="60" fill="none" stroke="var(--accent)" className="ripple-ellipse" strokeWidth="2" />
                </svg>

                {/* Droplets */}
                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}>
                   <Droplet level={0.62} width={120} glow />
                </div>
                
                <div style={{ position: 'absolute', top: '30%', left: '20%' }}>
                   <Droplet level={0.35} width={70} glow />
                </div>

                <div style={{ position: 'absolute', top: '60%', right: '20%' }}>
                   <Droplet level={0.80} width={90} glow />
                </div>

                {/* Falling droplet */}
                <div style={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)' }} className="falling-droplet">
                   <Droplet level={1} width={30} glow />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Light Band: How it works */}
      <div id="how" style={{ background: 'var(--light-band)', color: 'var(--light-text)', padding: '80px 16px' }}>
        <div style={{ maxWidth: '1160px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '2.5rem', marginBottom: '48px', textAlign: 'center' }}>Three steps, one ranked list</h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '32px' }}>
            {[
              { num: '1', title: 'Listen', desc: 'Level sensors in the manholes report water depth over MQTT while the rain falls.', color: '#8fe0ee' },
              { num: '2', title: 'Simulate', desc: 'A SWMM drainage model of the same network predicts what every sensor should read in that storm.', color: '#8fe0ee' },
              { num: '3', title: 'Rank', desc: 'The gaps between expected and observed levels point to pipe segments, listed with a confidence score.', color: '#ff9b7f' }
            ].map((step) => (
              <div key={step.num} style={{
                background: 'var(--light-card)',
                borderRadius: '24px',
                padding: '32px',
                boxShadow: '0 0 0 1px #c9d9e5, 0 14px 28px -18px rgba(15,34,54,.4)',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ position: 'relative', width: '48px', height: '48px' }}>
                    <Droplet level={1} variant="solid" width={48} style={{ position: 'absolute' }} />
                    <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: step.color, fontWeight: 'bold', fontSize: '1.25rem', zIndex: 10, marginTop: '8px' }}>{step.num}</span>
                  </div>
                  <h3 style={{ fontSize: '1.5rem', color: 'var(--light-text)' }}>{step.title}</h3>
                </div>
                <p style={{ color: 'var(--light-muted)', fontSize: '1.125rem' }}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Dark Band: Prototype */}
      <div id="proto" style={{ background: 'var(--bg)', padding: '80px 16px' }}>
        <div style={{ maxWidth: '1160px', margin: '0 auto' }}>
          
          <div style={{ 
            background: 'var(--teal-block)', 
            borderRadius: '32px', 
            padding: '48px', 
            boxShadow: '0 0 0 1px #1f5568',
            textAlign: 'center',
            maxWidth: '800px',
            margin: '0 auto 64px'
          }}>
            <h2 style={{ fontSize: '2.5rem', marginBottom: '24px', color: 'var(--text)' }}>A working prototype, honestly labelled</h2>
            <p className="text-muted" style={{ fontSize: '1.125rem', marginBottom: '32px', lineHeight: 1.6 }}>
              It runs on simulated storms over a synthetic drain network in the Amherst Street area of Kolkata. No camera images, only physics and sensor numbers.
            </p>
            <button className="btn-filled" onClick={onStart}>Open dashboard</button>
          </div>

          <footer style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '0.875rem' }}>
            PINNpoint prototype
          </footer>
        </div>
      </div>

    </div>
  )
}
