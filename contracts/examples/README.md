# Examples Validations

This directory contains examples of payloads that are verified against our JSON schemas.

- `mqtt_level_invalid.json`: Missing the required "v" field.
- `mqtt_rain_invalid.json`: Breaks the ISO 8601 UTC date-time format for "ts".
- `event_level_update_invalid.json`: Breaks the regex pattern `^[A-Za-z0-9_-]{1,50}$` for "node_id" (contains spaces and special characters).
- `event_rain_update_invalid.json`: Has an invalid "v" value (2 instead of const 1).
- `event_detection_invalid.json`: Contains a "confidence" score above 1.
