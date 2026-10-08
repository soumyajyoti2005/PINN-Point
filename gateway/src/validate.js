export function validateEvent(obj) {
  if (typeof obj !== 'object' || obj === null) {
    return { ok: false, error: "Event must be an object" };
  }

  if (obj.v !== 1) {
    return { ok: false, error: "unsupported version" };
  }

  if (!["level_update", "rain_update", "detection"].includes(obj.type)) {
    return { ok: false, error: "Unknown event type" };
  }

  const idPattern = /^[A-Za-z0-9_-]{1,50}$/;
  const tsRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

  let expectedKeys = ['v', 'type'];

  if (obj.type === 'level_update') {
    expectedKeys.push('ts', 'node_id', 'level_m');
    if ('battery' in obj) expectedKeys.push('battery');
    
    if (typeof obj.ts !== 'string' || !tsRegex.test(obj.ts) || isNaN(Date.parse(obj.ts))) {
      return { ok: false, error: "ts must be a valid ISO 8601 date-time string with time part" };
    }
    if (typeof obj.node_id !== 'string' || !idPattern.test(obj.node_id)) {
      return { ok: false, error: "node_id must match ID pattern" };
    }
    if (typeof obj.level_m !== 'number' || obj.level_m < 0) {
      return { ok: false, error: "level_m must be a non-negative number" };
    }
    if ('battery' in obj && (typeof obj.battery !== 'number' || obj.battery < 0)) {
      return { ok: false, error: "battery must be a non-negative number" };
    }
  } else if (obj.type === 'rain_update') {
    expectedKeys.push('ts', 'zone_id', 'intensity_mm_hr');
    
    if (typeof obj.ts !== 'string' || !tsRegex.test(obj.ts) || isNaN(Date.parse(obj.ts))) {
      return { ok: false, error: "ts must be a valid ISO 8601 date-time string with time part" };
    }
    if (typeof obj.zone_id !== 'string' || !idPattern.test(obj.zone_id)) {
      return { ok: false, error: "zone_id must match ID pattern" };
    }
    if (typeof obj.intensity_mm_hr !== 'number' || obj.intensity_mm_hr < 0) {
      return { ok: false, error: "intensity_mm_hr must be a non-negative number" };
    }
  } else if (obj.type === 'detection') {
    expectedKeys.push('detection');
    if (!obj.detection || typeof obj.detection !== 'object' || Array.isArray(obj.detection)) {
      return { ok: false, error: "detection property must be an object" };
    }
    
    const d = obj.detection;
    let expectedDKeys = ['detection_id', 'ts', 'top_pipe_id', 'confidence', 'candidates'];
    if ('status' in d) expectedDKeys.push('status');
    
    if (Object.keys(d).length !== expectedDKeys.length || !expectedDKeys.every(k => k in d)) {
      return { ok: false, error: "detection object has missing or extra properties" };
    }
    
    if (!Number.isInteger(d.detection_id)) {
      return { ok: false, error: "detection_id must be an integer" };
    }
    if (typeof d.ts !== 'string' || !tsRegex.test(d.ts) || isNaN(Date.parse(d.ts))) {
      return { ok: false, error: "detection ts must be a valid ISO 8601 date-time string" };
    }
    if (typeof d.top_pipe_id !== 'string' || !idPattern.test(d.top_pipe_id)) {
      return { ok: false, error: "top_pipe_id must match ID pattern" };
    }
    if (typeof d.confidence !== 'number' || d.confidence < 0 || d.confidence > 1) {
      return { ok: false, error: "confidence must be a number between 0 and 1" };
    }
    
    if (!Array.isArray(d.candidates) || d.candidates.length < 1) {
      return { ok: false, error: "candidates must be an array with at least 1 item" };
    }
    
    for (const c of d.candidates) {
      if (typeof c !== 'object' || c === null || Array.isArray(c)) {
        return { ok: false, error: "candidate must be an object" };
      }
      const cKeys = Object.keys(c);
      if (cKeys.length !== 2 || !('pipe_id' in c) || !('score' in c)) {
        return { ok: false, error: "candidate must have exactly pipe_id and score" };
      }
      if (typeof c.pipe_id !== 'string' || !idPattern.test(c.pipe_id)) {
        return { ok: false, error: "candidate pipe_id must match ID pattern" };
      }
      if (typeof c.score !== 'number' || c.score < 0 || c.score > 1) {
        return { ok: false, error: "candidate score must be a number between 0 and 1" };
      }
    }
    
    if ('status' in d) {
      if (!["new", "confirmed", "false_alarm", "resolved"].includes(d.status)) {
        return { ok: false, error: "status must be one of new/confirmed/false_alarm/resolved" };
      }
    }
  }

  if (Object.keys(obj).length !== expectedKeys.length || !expectedKeys.every(k => k in obj)) {
    return { ok: false, error: "Event has missing or extra properties" };
  }

  return { ok: true, type: obj.type };
}
