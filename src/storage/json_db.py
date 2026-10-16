import json
from pathlib import Path
from typing import Dict, List, Any

DATA_DIR = Path("data")

class JSONStorage:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.groups_file = self.data_dir / "groups.json"
        self.tags_file = self.data_dir / "tags.json"
        self.items_file = self.data_dir / "items.json"
        self.events_file = self.data_dir / "events.json"

        self._init_files()

    def _init_files(self):
        for path in [self.groups_file, self.tags_file, self.items_file, self.events_file]:
            if not path.exists():
                with open(path, "w") as f:
                    json.dump([], f, indent=2)

    def load_groups(self) -> List[Dict[str, Any]]:
        with open(self.groups_file, "r") as f:
            return json.load(f)

    def load_tags(self) -> List[Dict[str, Any]]:
        with open(self.tags_file, "r") as f:
            return json.load(f)

    def load_items(self) -> List[Dict[str, Any]]:
        with open(self.items_file, "r") as f:
            return json.load(f)

    def load_events(self) -> List[Dict[str, Any]]:
        with open(self.events_file, "r") as f:
            return json.load(f)

    def append_events(self, new_events: List[Dict[str, Any]]):
        events = self.load_events()
        events.extend(new_events)
        with open(self.events_file, "w") as f:
            json.dump(events, f, indent=2)

    def save_item(self, item: Dict[str, Any]):
        items = self.load_items()
        items.append(item)
        with open(self.items_file, "w") as f:
            json.dump(items, f, indent=2)

    def save_tag(self, tag: Dict[str, Any]):
        tags = self.load_tags()
        # Replace existing tag entry or append new one
        tags = [t for t in tags if t["id"] != tag["id"]]
        tags.append(tag)
        with open(self.tags_file, "w") as f:
            json.dump(tags, f, indent=2)

    def save_group(self, group: Dict[str, Any]):
        groups = self.load_groups()
        groups.append(group)
        with open(self.groups_file, "w") as f:
            json.dump(groups, f, indent=2)