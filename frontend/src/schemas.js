import Ajv from 'ajv'
import addFormats from 'ajv-formats'
import detectionSchema from '../../contracts/events/detection.schema.json'
import levelUpdateSchema from '../../contracts/events/level_update.schema.json'
import rainUpdateSchema from '../../contracts/events/rain_update.schema.json'

const ajv = new Ajv({ strict: false })
addFormats(ajv)

// Compile validators
export const validateDetection = ajv.compile(detectionSchema)
export const validateLevelUpdate = ajv.compile(levelUpdateSchema)
export const validateRainUpdate = ajv.compile(rainUpdateSchema)

export function validateEvent(type, payload) {
  let valid = false
  let errors = null
  
  if (type === 'detection') {
    valid = validateDetection(payload)
    errors = validateDetection.errors
  } else if (type === 'level_update') {
    valid = validateLevelUpdate(payload)
    errors = validateLevelUpdate.errors
  } else if (type === 'rain_update') {
    valid = validateRainUpdate(payload)
    errors = validateRainUpdate.errors
  }
  
  if (!valid) {
    console.error(`Schema validation failed for ${type}:`, errors)
  }
  return valid
}
