from datetime import datetime
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
                    "id": f"evt_auto_{int(datetime.now().timestamp())}",
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
        "id": f"evt_{int(datetime.now().timestamp())}",
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