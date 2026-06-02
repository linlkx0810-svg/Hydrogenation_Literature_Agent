"""
text_utils.py
Pure-function text helpers shared by all modules.
No config dependency — safe to import anywhere.
"""

import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from typing import Any

import requests

USER_AGENT = "Hydrogenation-Literature-Agent/1.0 (research; contact via project README)"

LITERATURE_COLUMNS = [
    "Title", "Authors", "Year", "Journal", "DOI", "URL",
    "Source database", "Search query",
    "Record type: primary / review / book chapter / unknown",
    "Inclusion decision", "Exclusion reason", "Confidence score",
    "Abstract", "OpenAlex ID", "Referenced works", "Cited by count",
    "Notes",
]


# ── HTTP ──────────────────────────────────────────────────────────────────────

def http_get(url: str, **kwargs: Any) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return requests.get(url, headers=headers, timeout=kwargs.pop("timeout", 30), **kwargs)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def clean_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", unescape(value or "")).strip()
    return text


def normalize_doi(value: str | None) -> str:
    doi = (value or "").strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    return doi.removeprefix("doi:").strip()


def normalize_title(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def safe_filename(value: str, suffix: str = ".pdf") -> str:
    name = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    return (name[:140] or "paper") + suffix


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Record helpers ────────────────────────────────────────────────────────────

def empty_record() -> dict[str, str]:
    return {col: "" for col in LITERATURE_COLUMNS}


def append_unique(current: str, incoming: str, separator: str = "; ") -> str:
    values = [i.strip() for i in (current or "").split(separator) if i.strip()]
    for item in [i.strip() for i in (incoming or "").split(separator) if i.strip()]:
        if item not in values:
            values.append(item)
    return separator.join(values)


def merge_two(current: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    for key, value in incoming.items():
        value = str(value or "").strip()
        if not value:
            continue
        if key in {"Source database", "Search query", "Notes"}:
            current[key] = append_unique(current.get(key, ""), value)
        elif key == "Referenced works":
            current[key] = append_unique(current.get(key, ""), value, "|")
        elif not current.get(key):
            current[key] = value
    return current


def deduplicate(
    records: list[dict[str, str]],
    title_threshold: float = 0.94,
) -> list[dict[str, str]]:
    """Merge duplicate records by DOI and fuzzy title matching."""
    merged: list[dict[str, str]] = []
    doi_index: dict[str, int] = {}
    exact_title_index: dict[str, int] = {}
    title_buckets: dict[str, list[int]] = {}
    normalized_titles: list[str] = []

    for record in records:
        doi = normalize_doi(record.get("DOI"))
        record["DOI"] = doi
        title = normalize_title(record.get("Title"))

        match_index = doi_index.get(doi) if doi else None
        if match_index is None:
            match_index = exact_title_index.get(title) if title else None
        if match_index is None and title:
            bucket = " ".join(title.split()[:4])
            for idx in title_buckets.get(bucket, []):
                known = normalized_titles[idx]
                if title == known or (
                    min(len(title), len(known)) >= 24
                    and SequenceMatcher(None, title, known).ratio() >= title_threshold
                ):
                    match_index = idx
                    break

        if match_index is None:
            match_index = len(merged)
            merged.append(record)
            normalized_titles.append(title)
            if title:
                exact_title_index[title] = match_index
                title_buckets.setdefault(" ".join(title.split()[:4]), []).append(match_index)
        else:
            merge_two(merged[match_index], record)

        if doi:
            doi_index[doi] = match_index

    return merged


# ── JSON I/O ──────────────────────────────────────────────────────────────────

def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
