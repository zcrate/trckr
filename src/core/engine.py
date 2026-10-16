import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from src.core.utils import get_auto_color

def resolve_item_state(item_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates the current state of a specific item from the event log.
    For timed items: odd number of events = running; even = stopped.
    For counted items: returns total count.
    """
    item_events = [e for e in events if e.get("item_id") == item_id]
    item_events.sort(key=lambda x: x["timestamp"])

    count = len(item_events)
    is_active = (count % 2 != 0)
    last_event = item_events[-1] if item_events else None

    return {
        "item_id": item_id,
        "event_count": count,
        "is_active": is_active,
        "last_timestamp": last_event["timestamp"] if last_event else None
    }


def _parse_timestamp(value: str) -> datetime:
    """Parses an ISO-8601 timestamp (accepting a trailing 'Z') into an aware UTC datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_item_duration(item_id: str, events: List[Dict[str, Any]], now: str) -> Dict[str, Any]:
    """
    Derives accumulated time for a timed item by pairing its events in timestamp order.
    Even-indexed events open an interval, odd-indexed events close it. An unpaired final
    event means the timer is running; that open interval is measured up to `now`.
    """
    item_events = [e for e in events if e.get("item_id") == item_id]
    item_events.sort(key=lambda x: x["timestamp"])

    total = 0.0
    current = 0.0
    is_active = False
    for i in range(0, len(item_events), 2):
        start = _parse_timestamp(item_events[i]["timestamp"])
        if i + 1 < len(item_events):
            end = _parse_timestamp(item_events[i + 1]["timestamp"])
        else:
            end = _parse_timestamp(now)
            is_active = True
        seconds = max(0.0, (end - start).total_seconds())
        total += seconds
        if is_active:
            current = seconds

    return {
        "item_id": item_id,
        "total_seconds": total,
        "current_seconds": current,
        "is_active": is_active,
    }


def process_trigger(
    item: Dict[str, Any],
    all_items: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    timestamp: str,
    source: str = "manual_tap"
) -> List[Dict[str, Any]]:
    """
    Processes an incoming trigger for an item, applying group auto-stop rules if necessary.
    Returns the new event(s) to be appended to the log stream.
    """
    new_events = []

    # Handle mutual exclusion for timed items in a group
    if item["type"] == "timed" and item.get("group_id"):
        group_id = item["group_id"]
        
        # Find all other timed items in the same group
        sibling_ids = [
            i["id"] for i in all_items 
            if i.get("group_id") == group_id and i["type"] == "timed" and i["id"] != item["id"]
        ]

        # Check if any sibling timer is currently running
        for sib_id in sibling_ids:
            state = resolve_item_state(sib_id, events)
            if state["is_active"]:
                # Auto-stop running timer in same group
                new_events.append({
                    "id": f"evt_auto_{uuid.uuid4().hex}",
                    "item_id": sib_id,
                    "timestamp": timestamp,
                    "action": "stop",
                    "source": "auto_group"
                })

    # Determine action for the triggered item
    current_state = resolve_item_state(item["id"], events)
    if item["type"] == "counted":
        action = "count"
    else:
        action = "stop" if current_state["is_active"] else "start"

    new_events.append({
        "id": f"evt_{uuid.uuid4().hex}",
        "item_id": item["id"],
        "timestamp": timestamp,
        "action": action,
        "source": source
    })

    return new_events


def enrich_item_tags(item: Dict[str, Any], tag_registry: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolves full tag metadata for an item, falling back to auto-generated hex colors
    if the tag is not explicitly customized in the registry.
    """
    item_tags = item.get("tags", [])
    registry_map = {t["id"]: t for t in tag_registry}
    
    enriched = []
    for tag_id in item_tags:
        if tag_id in registry_map:
            enriched.append(registry_map[tag_id])
        else:
            enriched.append({
                "id": tag_id,
                "label": tag_id.capitalize(),
                "color": get_auto_color(tag_id),
                "icon": None
            })
    return enriched