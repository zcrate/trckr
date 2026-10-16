# State Resolution & Event Rules

## 1. Counted Items
- **Formula**: `Count = COUNT(events WHERE item_id = X AND timestamp BETWEEN start AND end)`
- **Properties**: Instantaneous; single event generated per trigger.

## 2. Timed Items
- **State Check**: Sort events by `timestamp` ascending.
  - **Odd count**: Timer is currently `ACTIVE` (last event is `start`).
  - **Even count**: Timer is currently `STOPPED`.
- **Duration Calculation**: $\text{Duration} = \sum (\text{timestamp}_{\text{stop}} - \text{timestamp}_{\text{start}})$

## 3. Group Mutual Exclusion
When starting a `timed` item ($I_A$) belonging to group $G$:
1. Query active timers within group $G$.
2. For any active item ($I_B$), emit an automatic event:
   ```json
   {
     "id": "evt_auto_...",
     "item_id": "itm_B",
     "timestamp": "<trigger_timestamp>",
     "action": "stop",
     "source": "auto_group"
   }
   ```
3. Append the new `start` event for $I_A$.