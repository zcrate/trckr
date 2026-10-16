import pytest
from src.core.utils import (
    get_auto_color,
    normalize_tag,
    normalize_tags,
    slugify_tag,
)


def test_get_auto_color():
    assert get_auto_color("HomeWork") == get_auto_color("homework")
    assert get_auto_color("homework").startswith("#")


def test_normalize_tag():
    assert normalize_tag("  HomeWork  ") == "homework"


def test_normalize_tags():
    raw_tags = ["stars", "  KIDS  ", "stars", "homeWork ", "KIDS"]
    cleaned = normalize_tags(raw_tags)
    # Must be deduplicated and alphabetized
    assert cleaned == ["homework", "kids", "stars"]


def test_slugify_tag():
    raw_input = "  Work   Stuff! -1  "
    normalized = normalize_tag(raw_input)

    assert normalized == "work stuff! -1"
    assert slugify_tag(normalized) == "work_stuff_-1"
    assert slugify_tag("full-stack work") == "full-stack_work"