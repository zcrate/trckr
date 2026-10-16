# Integration API Spec

## Minimal Event Trigger Payload
External callers (widgets, hardware triggers, webhooks) do NOT need to evaluate state or generate UUIDs. They emit a lightweight JSON payload to the ingestion endpoint:

```json
{
  "item_id": "itm_102",
  "timestamp": "2026-10-14T10:54:00Z",
  "source": "widget"
}
```

### Supported Sources
- `widget`: Home screen / lock screen widget
- `manual_tap`: In-app button tap
- `sensor`: NFC tag, Bluetooth beacon, or hardware button
- `shortcut`: iOS Shortcut or Android Routine
- `auto_group`: System-generated auto-stop event