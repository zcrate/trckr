import re
import unicodedata
import hashlib
from typing import List

PALETTE = [
    "#FF3B30", "#FF9500", "#FFCC00", "#34C759", 
    "#00C7BE", "#30B0C7", "#32ADE6", "#007AFF", 
    "#5856D6", "#AF52DE", "#FF2D55", "#A2845E"
]

def get_auto_color(tag_id: str) -> str:
    """Generates a consistent, deterministic hex color for any normalized tag string."""
    clean_tag = normalize_tag(tag_id)
    hash_val = int(hashlib.md5(clean_tag.encode()).hexdigest(), 16)
    return PALETTE[hash_val % len(PALETTE)]


def normalize_tag(tag: str) -> str:
    """
    Normalizes a tag string for storage:
    - Unicode NFC normalization
    - Lowercase & trim
    - Single internal spacing
    Example: '  Work   Stuff! -1  ' -> 'work stuff! -1'
    """
    if not tag:
        return ""
    tag = unicodedata.normalize("NFC", tag)
    return " ".join(tag.strip().lower().split())


def normalize_tags(tags: List[str]) -> List[str]:
    """Normalizes, deduplicates, and alphabetizes a list of tag strings."""
    seen = set()
    cleaned = []

    for t in tags:
        norm = normalize_tag(t)
        if norm and norm not in seen:
            seen.add(norm)
            cleaned.append(norm)

    return sorted(cleaned)


def slugify_tag(tag: str) -> str:
    """
    Converts a normalized tag into a URL/CLI safe slug:
    - Converts spaces to underscores
    - Preserves internal hyphens
    - Removes special punctuation
    """
    norm = normalize_tag(tag)
    # Remove special characters except alphanumeric, whitespace, hyphens, and underscores
    clean = re.sub(r"[^\w\s-]", "", norm)
    # Replace whitespace sequences with a single underscore
    slug = re.sub(r"\s+", "_", clean)
    # Collapse multiple consecutive underscores while preserving hyphens
    return re.sub(r"_+", "_", slug).strip("_")