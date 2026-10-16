import json
import re

import pytest

from src.main import main


@pytest.fixture
def run(tmp_path, capsys):
    """Invoke the CLI against an isolated data dir; returns (exit_code, stdout, stderr)."""
    def _run(*argv):
        code = main(["--data-dir", str(tmp_path), *argv])
        captured = capsys.readouterr()
        return code, captured.out, captured.err
    return _run


def _created_id(out):
    m = re.search(r"\b((?:itm|grp)_[0-9a-f]{8})\b", out)
    assert m, out
    return m.group(1)


def test_add_and_status(run):
    code, out, _ = run("add", "Coding", "--tag", "Dev", "--tag", "dev")
    assert code == 0
    item_id = _created_id(out)
    assert item_id.startswith("itm_")

    code, out, _ = run("status")
    assert code == 0
    assert item_id in out and "Coding" in out and "stopped" in out
    # tags normalized + deduped, auto color rendered
    assert out.count("dev(#") == 1


def test_trigger_toggles_timed_item(run):
    _, out, _ = run("add", "Coding")
    item_id = _created_id(out)

    code, out, _ = run("trigger", "coding")  # by label, case-insensitive
    assert code == 0 and out.startswith(f'started {item_id}')
    _, out, _ = run("status")
    assert "running" in out

    code, out, _ = run("trigger", item_id)  # by id
    assert code == 0 and out.startswith(f'stopped {item_id}')
    _, out, _ = run("status")
    assert "stopped" in out


def test_trigger_counted_item_increments(run):
    _, out, _ = run("add", "Water", "--type", "counted")
    run("trigger", "Water")
    code, out, _ = run("trigger", "Water", "--source", "widget")
    assert code == 0 and out.strip().endswith("-> 2")
    _, out, _ = run("status", "--json")
    rows = json.loads(out)
    assert rows[0]["type"] == "counted" and rows[0]["count"] == 2


def test_group_auto_stop_message_order(run):
    _, out, _ = run("group", "add", "Work")
    grp = _created_id(out)
    _, out, _ = run("add", "Coding", "--group", "Work")
    coding = _created_id(out)
    _, out, _ = run("add", "Meeting", "--group", grp)
    meeting = _created_id(out)

    run("trigger", "Coding")
    code, out, _ = run("trigger", "Meeting")
    lines = out.strip().splitlines()
    assert code == 0
    assert lines[0] == f'stopped {coding} "Coding" (auto_group)'
    assert lines[1] == f'started {meeting} "Meeting"'

    _, out, _ = run("group", "list")
    assert grp in out and "Work" in out and "2" in out


def test_unknown_item_is_error(run):
    code, out, err = run("trigger", "nope")
    assert code == 1 and out == "" and "no item matching 'nope'" in err


def test_ambiguous_label_is_error(run):
    _, out, _ = run("add", "Same")
    a = _created_id(out)
    _, out, _ = run("add", "same")
    b = _created_id(out)
    code, _, err = run("trigger", "SAME")
    assert code == 1 and a in err and b in err


def test_unknown_group_is_error(run):
    code, _, err = run("add", "Coding", "--group", "ghost")
    assert code == 1 and "no group matching 'ghost'" in err


def test_tag_set_upsert_and_validation(run, tmp_path):
    code, _, err = run("tag", "set", "dev", "--color", "blue")
    assert code == 1 and "hex color" in err

    assert run("tag", "set", " Dev ", "--color", "#007AFF")[0] == 0
    assert run("tag", "set", "dev", "--color", "#FF0000", "--icon", "code")[0] == 0
    tags = json.loads((tmp_path / "tags.json").read_text())
    assert tags == [{"id": "dev", "color": "#FF0000", "icon": "code"}]

    run("add", "Coding", "--tag", "dev", "--tag", "misc")
    _, out, _ = run("status")
    assert "dev(#FF0000)" in out
    _, out, _ = run("tag", "list")
    assert "dev" in out and "code" in out and "misc" in out and "(auto)" in out


def test_status_json_shape(run):
    run("add", "Coding")
    run("trigger", "Coding")
    _, out, _ = run("status", "--json")
    rows = json.loads(out)
    assert len(rows) == 1
    row = rows[0]
    assert row["is_active"] is True
    assert row["total_seconds"] >= 0 and row["current_seconds"] == row["total_seconds"]
    assert row["group"] is None and row["tags"] == []


def test_log_filters_by_item_and_limit(run):
    _, out, _ = run("add", "A", "--type", "counted")
    a = _created_id(out)
    _, out, _ = run("add", "B", "--type", "counted")
    for _ in range(3):
        run("trigger", "A")
    run("trigger", "B")

    _, out, _ = run("log")
    assert out.count("evt_") == 4
    _, out, _ = run("log", "--item", a)
    assert out.count("evt_") == 3 and "B" not in out.splitlines()[1:]
    _, out, _ = run("log", "--limit", "2")
    assert out.count("evt_") == 2


def test_events_schema_fields(run, tmp_path):
    run("add", "Coding")
    run("trigger", "Coding")
    events = json.loads((tmp_path / "events.json").read_text())
    assert set(events[0]) == {"id", "item_id", "timestamp", "action", "source"}
    assert re.fullmatch(r"evt_[0-9a-f]{32}", events[0]["id"])
    assert events[0]["timestamp"].endswith("Z")
    items = json.loads((tmp_path / "items.json").read_text())
    assert set(items[0]) == {"id", "label", "type", "group_id", "tags", "created_at"}
