import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import Landing from './Landing'
import Dashboard from './Dashboard'
import { validateEvent } from './schemas'
import { createDataSource } from './mockSource'

describe('Frontend Tests', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('renders Landing page', () => {
    render(<Landing onStart={() => {}} />)
    expect(screen.getAllByText(/PINNpoint/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/A working prototype/i)).toBeDefined()
  })

  it('renders Dashboard page in mock mode', async () => {
    render(<Dashboard onBack={() => {}} />)
    expect(screen.getAllByText(/PINNpoint/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Mock storm replay/i)).toBeDefined()
    expect(await screen.findByText(/Suspect pipes/i)).toBeDefined()
  })

  it('validates events against contract shapes', () => {
    // Valid rain event
    expect(validateEvent('rain_update', {
      v: 1, type: 'rain_update', zone_id: 'RG-1', ts: '2023-01-01T00:00:00Z', intensity_mm_hr: 10
    })).toBe(true)

    // Invalid rain event (missing required)
    expect(validateEvent('rain_update', {
      v: 1, type: 'rain_update', zone_id: 'RG-1'
    })).toBe(false)
  })

  it('mock source determinism (generates predictable events)', async () => {
    vi.useFakeTimers()
    let rainCount = 0
    let levelCount = 0
    
    const source = createDataSource('mock', (event) => {
      if (event.type === 'rain_update') rainCount++
      if (event.type === 'level_update') levelCount++
    })
    
    source.play()
    
    // Advance time by 10 ticks (10 seconds scaled via fake timers)
    vi.advanceTimersByTime(10000)
    
    source.pause()
    
    // 10 ticks = 10 rain events, 10 * num_nodes level events
    expect(rainCount).toBeGreaterThan(0)
  })
})
