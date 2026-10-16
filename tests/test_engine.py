import pytest
from src.core.engine import process_trigger, resolve_item_duration, resolve_item_state


@pytest.fixture
def sample_items():
    return [
        {
            "id": "itm_counted_1",
            "label": "Water Glass",
            "type": "counted",
            "group_id": None,
        },
        {
            "id": "itm_timed_1",
            "label": "Coding",
            "type": "timed",
            "group_id": "grp_work",
        },
        {
            "id": "itm_timed_2",
            "label": "Meeting",
            "type": "timed",
            "group_id": "grp_work",
        },
        {
            "id": "itm_timed_solo",
            "label": "Meditation",
            "type": "timed",
            "group_id": None,
        },
    ]


# --- State Resolution Tests ---

def test_resolve_item_state_empty_events():
    state = resolve_item_state("itm_timed_1", [])
    assert state["item_id"] == "itm_timed_1"
    assert state["event_count"] == 0
    assert state["is_active"] is False
    assert state["last_timestamp"] is None


def test_resolve_item_state_active_timer():
    events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"}
    ]
    state = resolve_item_state("itm_timed_1", events)
    assert state["event_count"] == 1
    assert state["is_active"] is True
    assert state["last_timestamp"] == "2026-10-14T10:00:00Z"


def test_resolve_item_state_stopped_timer():
    events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T11:00:00Z", "action": "stop"},
    ]
    state = resolve_item_state("itm_timed_1", events)
    assert state["event_count"] == 2
    assert state["is_active"] is False


# --- Trigger Processing Tests ---

def test_process_trigger_counted_item(sample_items):
    item = sample_items[0]
    new_events = process_trigger(item, sample_items, [], "2026-10-14T12:00:00Z", "widget")

    assert len(new_events) == 1
    assert new_events[0]["item_id"] == "itm_counted_1"
    assert new_events[0]["action"] == "count"
    assert new_events[0]["source"] == "widget"


def test_process_trigger_start_timed_item(sample_items):
    item = sample_items[1]
    new_events = process_trigger(item, sample_items, [], "2026-10-14T12:00:00Z", "manual_tap")

    assert len(new_events) == 1
    assert new_events[0]["item_id"] == "itm_timed_1"
    assert new_events[0]["action"] == "start"


def test_process_trigger_stop_active_timed_item(sample_items):
    item = sample_items[1]
    existing_events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"}
    ]

    new_events = process_trigger(item, sample_items, existing_events, "2026-10-14T11:00:00Z")

    assert len(new_events) == 1
    assert new_events[0]["item_id"] == "itm_timed_1"
    assert new_events[0]["action"] == "stop"


def test_process_trigger_auto_stop_grouped_timer(sample_items):
    coding_item = sample_items[1]
    meeting_item = sample_items[2]

    # "Coding" is currently active
    existing_events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"}
    ]

    # Trigger "Meeting" in the same group ("grp_work")
    new_events = process_trigger(meeting_item, sample_items, existing_events, "2026-10-14T11:00:00Z", "widget")

    # Should emit 2 events: 1 auto-stop for Coding, 1 start for Meeting
    assert len(new_events) == 2

    auto_stop_evt = new_events[0]
    assert auto_stop_evt["item_id"] == "itm_timed_1"
    assert auto_stop_evt["action"] == "stop"
    assert auto_stop_evt["source"] == "auto_group"

    start_evt = new_events[1]
    assert start_evt["item_id"] == "itm_timed_2"
    assert start_evt["action"] == "start"
    assert start_evt["source"] == "widget"


def test_process_trigger_ungrouped_timer_does_not_stop_others(sample_items):
    solo_item = sample_items[3]

    # "Coding" is active in grp_work
    existing_events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"}
    ]

    # Triggering an ungrouped timed item ("Meditation") should not stop Coding
    new_events = process_trigger(solo_item, sample_items, existing_events, "2026-10-14T11:00:00Z")

    assert len(new_events) == 1
    assert new_events[0]["item_id"] == "itm_timed_solo"
    assert new_events[0]["action"] == "start"


def test_filter_items_by_tag(sample_items):
    # Verify items can be queried by tag array
    sample_items[0]["tags"] = ["kids", "stars"]
    sample_items[1]["tags"] = ["kids", "homework"]

    kids_items = [i for i in sample_items if "kids" in i.get("tags", [])]
    assert len(kids_items) == 2

# --- Event ID uniqueness ---

def test_process_trigger_event_ids_unique(sample_items):
    counted = sample_items[0]
    ids = set()
    for _ in range(50):
        events = process_trigger(counted, sample_items, [], "2026-10-14T10:00:00Z")
        assert len(events) == 1
        assert events[0]["id"].startswith("evt_")
        ids.add(events[0]["id"])
    assert len(ids) == 50


def test_process_trigger_auto_stop_ids_distinct(sample_items):
    # Two siblings both running (only reachable via toggle-only clients); each auto-stop
    # must still get its own id.
    events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z", "action": "start"},
        {"item_id": "itm_timed_2", "timestamp": "2026-10-14T10:01:00Z", "action": "start"},
    ]
    third = {"id": "itm_timed_3", "label": "Review", "type": "timed", "group_id": "grp_work"}
    new = process_trigger(third, sample_items + [third], events, "2026-10-14T10:05:00Z")
    auto = [e for e in new if e["source"] == "auto_group"]
    assert len(auto) == 2
    assert auto[0]["id"] != auto[1]["id"]
    assert all(e["id"].startswith("evt_auto_") for e in auto)


# --- Duration Resolution ---

def test_resolve_item_duration_no_events():
    d = resolve_item_duration("itm_timed_1", [], "2026-10-14T12:00:00Z")
    assert d == {"item_id": "itm_timed_1", "total_seconds": 0.0, "current_seconds": 0.0, "is_active": False}


def test_resolve_item_duration_closed_intervals():
    events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:30:00Z"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T11:00:00Z"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T11:15:00Z"},
        {"item_id": "itm_other", "timestamp": "2026-10-14T09:00:00Z"},
    ]
    d = resolve_item_duration("itm_timed_1", events, "2026-10-14T12:00:00Z")
    assert d["total_seconds"] == 45 * 60
    assert d["current_seconds"] == 0.0
    assert d["is_active"] is False


def test_resolve_item_duration_open_interval_uses_now():
    events = [
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:00:00Z"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T10:10:00Z"},
        {"item_id": "itm_timed_1", "timestamp": "2026-10-14T11:00:00Z"},
    ]
    d = resolve_item_duration("itm_timed_1", events, "2026-10-14T11:20:00+00:00")
    assert d["is_active"] is True
    assert d["current_seconds"] == 20 * 60
    assert d["total_seconds"] == 30 * 60
