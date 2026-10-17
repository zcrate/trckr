"""Command-line interface for trckr.

Wires the pure state engine (src.core.engine) to the JSON storage layer
(src.storage.json_db). Every command either appends events or derives a
view by replaying the event log; nothing stores "current state".
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.core.engine import (
    enrich_item_tags,
    process_trigger,
    resolve_item_duration,
    resolve_item_state,
)
from src.core.utils import get_auto_color, normalize_tag, normalize_tags
from src.storage.json_db import DATA_DIR, JSONStorage

SOURCES = ["manual_tap", "widget", "sensor", "shortcut"]
HEX_COLOR = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
MAX_LABEL = 100
MAX_TAG = 30


class CLIError(Exception):
    """A user-facing error; printed to stderr with exit code 1."""


# --- helpers ---------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str, existing: Iterable[str]) -> str:
    taken = set(existing)
    while True:
        candidate = f"{prefix}{uuid.uuid4().hex[:8]}"
        if candidate not in taken:
            return candidate


def _validate_label(label: str) -> str:
    label = label.strip()
    if not label:
        raise CLIError("label must not be empty")
    if len(label) > MAX_LABEL:
        raise CLIError(f"label must be at most {MAX_LABEL} characters")
    return label


def _validate_tags(raw: List[str]) -> List[str]:
    tags = normalize_tags(raw)
    for t in tags:
        if len(t) > MAX_TAG:
            raise CLIError(f"tag '{t}' is longer than {MAX_TAG} characters")
    return tags


def _find(kind: str, records: List[Dict[str, Any]], ref: str) -> Dict[str, Any]:
    for r in records:
        if r["id"] == ref:
            return r
    wanted = ref.strip().lower()
    matches = [r for r in records if r.get("label", "").strip().lower() == wanted]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CLIError(f"no {kind} matching '{ref}'")
    ids = ", ".join(m["id"] for m in matches)
    raise CLIError(f"'{ref}' matches several {kind}s; use an id: {ids}")


def _find_item(storage: JSONStorage, ref: str) -> Dict[str, Any]:
    return _find("item", storage.load_items(), ref)


def _find_group(storage: JSONStorage, ref: str) -> Dict[str, Any]:
    return _find("group", storage.load_groups(), ref)


def _fmt_duration(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _print_table(rows: List[List[str]], header: List[str]) -> None:
    if not rows:
        print("(none)")
        return
    widths = [len(h) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*header).rstrip())
    for row in rows:
        print(fmt.format(*row).rstrip())


# --- command handlers ------------------------------------------------------

def cmd_item_add(args: argparse.Namespace, storage: JSONStorage) -> int:
    label = _validate_label(args.label)
    group_id: Optional[str] = None
    if args.group:
        group_id = _find_group(storage, args.group)["id"]
    items = storage.load_items()
    item = {
        "id": _new_id("itm_", (i["id"] for i in items)),
        "label": label,
        "type": args.type,
        "group_id": group_id,
        "tags": _validate_tags(args.tags or []),
        "created_at": _now_iso(),
    }
    storage.save_item(item)
    print(f'created {item["id"]} "{label}" ({item["type"]})')
    return 0

def cmd_item_list(args: argparse.Namespace, storage: JSONStorage) -> int:
    rows = _status_rows(storage, _now_iso())
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    table = []
    for r in rows:
        if r["type"] == "counted":
            state = f'count {r["count"]}'
        elif r["is_active"]:
            state = f'running {_fmt_duration(r["current_seconds"])}  total {_fmt_duration(r["total_seconds"])}'
        else:
            state = f'stopped  total {_fmt_duration(r["total_seconds"])}'
        tags = " ".join(f'{t["id"]}({t["color"]})' for t in r["tags"])
        table.append([r["id"], r["label"], r["type"], r["group"] or "-", state, tags])
    _print_table(table, ["ID", "LABEL", "TYPE", "GROUP", "STATE", "TAGS"])
    return 0


def cmd_group_add(args: argparse.Namespace, storage: JSONStorage) -> int:
    label = _validate_label(args.label)
    groups = storage.load_groups()
    group = {
        "id": _new_id("grp_", (g["id"] for g in groups)),
        "label": label,
        "created_at": _now_iso(),
    }
    storage.save_group(group)
    print(f'created {group["id"]} "{label}"')
    return 0

def cmd_group_list(args: argparse.Namespace, storage: JSONStorage) -> int:
    items = storage.load_items()
    rows = []
    for g in storage.load_groups():
        members = sum(1 for i in items if i.get("group_id") == g["id"])
        rows.append([g["id"], g["label"], str(members)])
    _print_table(rows, ["ID", "LABEL", "ITEMS"])
    return 0


def cmd_tag_set(args: argparse.Namespace, storage: JSONStorage) -> int:
    tag_id = normalize_tag(args.tag)
    if not tag_id:
        raise CLIError("tag must not be empty")
    if len(tag_id) > MAX_TAG:
        raise CLIError(f"tag must be at most {MAX_TAG} characters")
    if not HEX_COLOR.match(args.color):
        raise CLIError(f"color '{args.color}' is not a hex color like #0A84FF")
    tag = {"id": tag_id, "color": args.color, "icon": args.icon}
    storage.save_tag(tag)
    print(f'set tag {tag_id} color {args.color}' + (f' icon {args.icon}' if args.icon else ""))
    return 0

def cmd_tag_list(args: argparse.Namespace, storage: JSONStorage) -> int:
    registry = {t["id"]: t for t in storage.load_tags()}
    seen = set()
    for item in storage.load_items():
        seen.update(item.get("tags", []))
    rows = []
    for tag_id in sorted(seen | set(registry)):
        if tag_id in registry:
            t = registry[tag_id]
            rows.append([tag_id, t["color"], t.get("icon") or "-", ""])
        else:
            rows.append([tag_id, get_auto_color(tag_id), "-", "(auto)"])
    _print_table(rows, ["TAG", "COLOR", "ICON", ""])
    return 0


def cmd_trigger(args: argparse.Namespace, storage: JSONStorage) -> int:
    items = storage.load_items()
    item = _find("item", items, args.item)
    events = storage.load_events()
    new_events = process_trigger(item, items, events, _now_iso(), args.source)
    storage.append_events(new_events)

    labels = {i["id"]: i["label"] for i in items}
    verbs = {"start": "started", "stop": "stopped", "count": "counted"}
    for e in new_events:
        verb = verbs.get(e.get("action"), e.get("action"))
        suffix = f' ({e["source"]})' if e.get("source") == "auto_group" else ""
        line = f'{verb} {e["item_id"]} "{labels.get(e["item_id"], "?")}"{suffix}'
        if e.get("action") == "count":
            total = resolve_item_state(e["item_id"], events + new_events)["event_count"]
            line += f" -> {total}"
        print(line)
    return 0

def cmd_log(args: argparse.Namespace, storage: JSONStorage) -> int:
    items = storage.load_items()
    events = storage.load_events()
    if args.item:
        item_id = _find("item", items, args.item)["id"]
        events = [e for e in events if e.get("item_id") == item_id]
    events.sort(key=lambda e: e["timestamp"])
    if args.limit is not None and args.limit >= 0:
        events = events[-args.limit:] if args.limit else []
    labels = {i["id"]: i["label"] for i in items}
    rows = [
        [
            e["timestamp"],
            e.get("action", "toggle"),
            labels.get(e["item_id"], e["item_id"]),
            e.get("source", "-"),
            e["id"],
        ]
        for e in events
    ]
    _print_table(rows, ["TIMESTAMP", "ACTION", "ITEM", "SOURCE", "EVENT"])
    return 0


def _status_rows(storage: JSONStorage, now: str) -> List[Dict[str, Any]]:
    events = storage.load_events()
    groups = {g["id"]: g["label"] for g in storage.load_groups()}
    registry = storage.load_tags()
    rows = []
    for item in storage.load_items():
        state = resolve_item_state(item["id"], events)
        row: Dict[str, Any] = {
            "id": item["id"],
            "label": item["label"],
            "type": item["type"],
            "group": groups.get(item.get("group_id")) if item.get("group_id") else None,
            "tags": [
                {"id": t["id"], "color": t["color"], "icon": t.get("icon")}
                for t in enrich_item_tags(item, registry)
            ],
        }
        if item["type"] == "counted":
            row["count"] = state["event_count"]
        else:
            dur = resolve_item_duration(item["id"], events, now)
            row["is_active"] = dur["is_active"]
            row["current_seconds"] = dur["current_seconds"]
            row["total_seconds"] = dur["total_seconds"]
        rows.append(row)
    return rows





# --- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trckr",
        description="Event-driven time and count tracker.",
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("TRCKR_DATA_DIR", str(DATA_DIR)),
        help="directory holding the JSON data files (env TRCKR_DATA_DIR; default: data)",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True
    
# --- ITEM MANAGEMENT ---
    i = sub.add_parser("item", help="Manage tracked items")
    isub = i.add_subparsers(dest="item_command", metavar="SUBCOMMAND")
    isub.required = True
    # item add
    p = isub.add_parser("add", help="Create a trackable item")
    p.add_argument("label")
    p.add_argument("--type", choices=["timed", "counted"], default="counted")
    p.add_argument("--group", metavar="REF", help="Optional auto-stop group id or label")
    p.add_argument("--tags", action="append", metavar="TAG", help="Optional item tag. Can be repeated.")
    p.set_defaults(func=cmd_item_add)
    # item list
    p = isub.add_parser("list", help="List all items")
    p.add_argument("--tag", metavar="TAG", help="Filter items by tag")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_item_list)

# --- GROUP MANAGEMENT ---
    g = sub.add_parser("group", help="Manage auto-stop groups")
    gsub = g.add_subparsers(dest="group_command", metavar="SUBCOMMAND")
    gsub.required = True
    # group add
    p = gsub.add_parser("add", help="Create an auto-stop group")
    p.add_argument("label")
    p.set_defaults(func=cmd_group_add)
    # group list
    p = gsub.add_parser("list", help="List auto-stop groups")
    p.set_defaults(func=cmd_group_list)

# --- TAG MANAGEMENT ---
    t = sub.add_parser("tag", help="Manage tag colors and icons")
    tsub = t.add_subparsers(dest="tag_command", metavar="SUBCOMMAND")
    tsub.required = True
    # tag set
    p = tsub.add_parser("set", help="Set a tag's color and icon")
    p.add_argument("tag")
    p.add_argument("--color", metavar="HEX", help="Hex color (e.g. #0A84FF)")
    p.add_argument("--icon", help="Icon identifier")
    p.set_defaults(func=cmd_tag_set)
    # tag list
    p = tsub.add_parser("list", help="List tags in use and in the registry")
    p.set_defaults(func=cmd_tag_list)

# --- OPERATIONAL EXECUTION ---
    p = sub.add_parser("trigger", aliases=["t"], help="Start/stop a timer or bump a counter")
    p.add_argument("item", metavar="REF", help="Item id or label")
    p.add_argument("--source", choices=SOURCES, default="manual_tap")
    p.set_defaults(func=cmd_trigger)

    p = sub.add_parser("log", aliases=["l"], help="List historical event log")
    p.add_argument("--item", metavar="REF", help="Only events for this item")
    p.add_argument("--tag", metavar="TAG", help="Only events for items matching this tag")
    p.add_argument("--limit", type=int, default=50, help="Newest N events (default 50)")
    p.set_defaults(func=cmd_log)

    return parser


def cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    storage = JSONStorage(Path(args.data_dir))
    try:
        return args.func(args, storage)
    except CLIError as exc:
        print(f"trckr: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
