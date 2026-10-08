import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { validateEvent } from '../src/validate.js';

test('Contracts validation', (t) => {
  const contractsDir = process.env.CONTRACTS_DIR;
  if (!contractsDir) {
    t.skip('CONTRACTS_DIR not set in environment');
    return;
  }

  const examplesDir = path.join(contractsDir, 'examples');
  if (!fs.existsSync(examplesDir)) {
    t.skip(`Examples directory not found at ${examplesDir}`);
    return;
  }

  const fileTypeMap = {
    'event_detection_invalid.json': 'detection',
    'event_detection_valid.json': 'detection',
    'event_level_update_invalid.json': 'level_update',
    'event_level_update_valid.json': 'level_update',
    'event_rain_update_invalid.json': 'rain_update',
    'event_rain_update_valid.json': 'rain_update',
  };

  const files = fs.readdirSync(examplesDir);
  const eventFiles = files.filter(f => f.startsWith('event_'));
  
  const mappingErrors = [];
  for (const file of eventFiles) {
    if (!fileTypeMap[file]) {
      mappingErrors.push(`Event example file has no mapping: ${file}`);
    }
  }
  assert.deepStrictEqual(mappingErrors, [], `Mapping errors found:\n${mappingErrors.join('\n')}`);

  const validationFailures = [];
  for (const file of eventFiles) {
    const raw = fs.readFileSync(path.join(examplesDir, file), 'utf8');
    const obj = JSON.parse(raw);
    const result = validateEvent(obj);
    
    if (file.includes('invalid')) {
      if (result.ok) {
        validationFailures.push(`Expected ${file} to fail validation`);
      }
    } else {
      if (!result.ok) {
        validationFailures.push(`Expected ${file} to pass validation, but failed with: ${result.error}`);
      } else if (result.type !== fileTypeMap[file]) {
        validationFailures.push(`Expected ${file} type to be ${fileTypeMap[file]}, got ${result.type}`);
      }
    }
  }
  
  assert.deepStrictEqual(validationFailures, [], `Validation failures found:\n${validationFailures.join('\n')}`);
});

test('Additional validation rules', () => {
  const baseEvent = {
    v: 1,
    type: 'level_update',
    node_id: 'MH-01',
    ts: '2023-10-27T10:00:00Z',
    level_m: 0.5
  };

  // level_m as string fails
  const strLevel = { ...baseEvent, level_m: '0.42' };
  assert.strictEqual(validateEvent(strLevel).ok, false);

  // date only ts fails
  const dateOnlyTs = { ...baseEvent, ts: '2023-10-27' };
  assert.strictEqual(validateEvent(dateOnlyTs).ok, false);

  // v=2 fails with unsupported version
  const v2Event = { ...baseEvent, v: 2 };
  const v2Res = validateEvent(v2Event);
  assert.strictEqual(v2Res.ok, false);
  assert.strictEqual(v2Res.error, 'unsupported version');

  // extra property fails
  const extraProp = { ...baseEvent, unexpected_key: true };
  assert.strictEqual(validateEvent(extraProp).ok, false);
  
  const validDetection = {
    v: 1,
    type: 'detection',
    detection: {
      detection_id: 1001,
      ts: "2023-10-27T10:05:00Z",
      top_pipe_id: "P-101",
      confidence: 0.85,
      candidates: [{ pipe_id: "P-101", score: 0.85 }]
    }
  };

  // detection with an empty candidates array fails
  const emptyCands = JSON.parse(JSON.stringify(validDetection));
  emptyCands.detection.candidates = [];
  assert.strictEqual(validateEvent(emptyCands).ok, false);
  
  // detection with a flat shape fails
  const flatDetection = {
    v: 1,
    type: 'detection',
    detection_id: 1001,
    ts: "2023-10-27T10:05:00Z",
    top_pipe_id: "P-101",
    confidence: 0.85,
    candidates: [{ pipe_id: "P-101", score: 0.85 }]
  };
  assert.strictEqual(validateEvent(flatDetection).ok, false);

  // detection_id as string fails
  const strIdDet = JSON.parse(JSON.stringify(validDetection));
  strIdDet.detection.detection_id = "1001";
  assert.strictEqual(validateEvent(strIdDet).ok, false);

  // candidates item with "confidence" instead of "score" fails
  const wrongCand = JSON.parse(JSON.stringify(validDetection));
  wrongCand.detection.candidates = [{ pipe_id: "P-101", confidence: 0.85 }];
  assert.strictEqual(validateEvent(wrongCand).ok, false);
});
