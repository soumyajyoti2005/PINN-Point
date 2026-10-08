import React, { useId } from 'react'

export function Droplet({ level = 0, width = 100, variant = 'default', glow = false, style, className = '' }) {
  const id = useId()
  const clipId = `clip-${id}`
  const gradId = `grad-${id}`
  
  const h = 145
  const waterY = h * (1 - Math.max(0, Math.min(1, level)))
  
  // variant: default, alert, solid
  let stop1 = '#8fe0ee'
  let stop2 = '#2f86b5'
  if (variant === 'alert') {
    stop1 = '#ff9b7f'
    stop2 = '#ff7a59'
  } else if (variant === 'solid') {
    stop1 = '#0f2a44'
    stop2 = '#0f2a44'
  }
  
  let filter = 'drop-shadow(0 6px 8px rgba(0,0,0,.45))'
  if (glow) {
    filter += ' drop-shadow(0 0 16px rgba(94,200,216,.28))'
  }

  const path = "M50,0 C50,0 100,58 100,95 A50,50 0 0 1 0,95 C0,58 50,0 50,0Z"

  return (
    <svg 
      width={width} 
      viewBox="0 0 100 145" 
      style={{ filter, ...style }} 
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={`Droplet ${Math.round(level * 100)}%`}
    >
      <defs>
        <clipPath id={clipId}>
          <path d={path} />
        </clipPath>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stop1} />
          <stop offset="100%" stopColor={stop2} />
        </linearGradient>
      </defs>
      
      <path d={path} fill="var(--drop-body)" stroke="#4d86a8" strokeWidth="1.5" />
      <rect 
        x="0" 
        y={waterY} 
        width="100" 
        height={h} 
        fill={`url(#${gradId})`} 
        clipPath={`url(#${clipId})`} 
        style={{ transition: 'y 0.3s ease' }}
      />
    </svg>
  )
}

export function MapDroplet({ level = 0, variant = 'default', x, y, size = 1, selected = false, onClick }) {
  const k = 0.15 + 0.8 * Math.max(0, Math.min(1, level))
  const path = "M0,-16 C0,-16 11,-2 11,5 A11,11 0 0 1 -11,5 C-11,-2 0,-16 0,-16Z"
  
  let color = '#2f7fa3'
  if (variant === 'alert') {
    color = '#ff7a59'
  } else if (level > 0.6) {
    color = '#8fe0ee'
  } else if (level > 0.2) {
    color = '#4fb0cc'
  }

  return (
    <g 
      transform={`translate(${x},${y}) scale(${size})`} 
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
      role="button"
      tabIndex={0}
      aria-label={`Sensor map node ${Math.round(level*100)}%`}
      onKeyDown={(e) => { if(e.key==='Enter' && onClick) onClick() }}
    >
      {selected && (
        <circle r="18" fill="rgba(255,255,255,0.1)" stroke="var(--accent-bright)" strokeWidth="1.5" strokeDasharray="4 2" />
      )}
      <path d={path} fill="var(--drop-body)" stroke="#4d86a8" strokeWidth="1.5" />
      <path 
        d={path} 
        fill={color} 
        transform={`translate(0,16) scale(${k}) translate(0,-16)`} 
        style={{ transition: 'transform 0.3s ease, fill 0.3s ease' }}
      />
    </g>
  )
}
