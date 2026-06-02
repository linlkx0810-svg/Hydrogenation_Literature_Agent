"""
modules/literature_search.py
────────────────────────────
Stage 1: keyword search across OpenAlex, Crossref, Semantic Scholar
         + citation chasing (backward and forward via OpenAlex).

Entry point
-----------
    from modules.literature_search import run
    stats = run(cfg)   # cfg from utils.load_config()
"""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

from utils import (
    load_config, log_event, ProjectState, make_run_id,
    clean_text, empty_record, http_get, normalize_doi,
    deduplicate, timestamp,
)
from utils.excel_io import export_records_xlsx
from utils.text_utils import LITERATURE_COLUMNS

OPENALEX_URL         = "https://api.openalex.org/works"
CROSSREF_URL         = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_FIELDS      = "title,authors,year,venue,url,externalIds,abstract,citationCount,referenceCount"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    words = [(pos, word) for word, positions in inverted_index.items() for pos in positions]
    return " ".join(w for _, w in sorted(words))


def _record_type(title: str, source_type: str = "") -> str:
    text = f"{title} {source_type}".lower()
    if "review" in text:
        return "review"
    if "book-chapter" in text or "book chapter" in text:
        return "book chapter"
    if source_type in {"article", "journal-article", "proceedings-article"}:
        return "primary"
    return "unknown"


def _log_entry(source: str, query: str, group: str, mode: str,
               results: int, status: str, notes: str = "") -> dict:
    return {
        "Timestamp UTC": timestamp(),
        "Source database": source,
        "Search query": query,
        "Search group": group,
        "Search mode": mode,
        "Results returned": str(results),
        "Status": status,
        "Notes": notes,
    }


# ── Source-specific searchers ─────────────────────────────────────────────────

def _search_openalex(all_queries: list[tuple[str, str]],
                     per_query: int, mailto: str = "") -> tuple[list[dict], list[dict]]:
    records, logs = [], []
    for group, query in all_queries:
        params = {"search": query, "per-page": per_query}
        if mailto:
            params["mailto"] = mailto
        try:
            resp = http_get(OPENALEX_URL, params=params)
            resp.raise_for_status()
            works = resp.json().get("results", [])
            logs.append(_log_entry("OpenAlex", query, group, "keyword search", len(works), "OK"))
            for work in works:
                primary = work.get("primary_location") or {}
                source  = primary.get("source") or {}
                rec = empty_record()
                rec.update({
                    "Title":         clean_text(work.get("title")),
                    "Authors":       "; ".join(
                        item.get("author", {}).get("display_name", "")
                        for item in work.get("authorships", []) if item.get("author")
                    ),
                    "Year":          str(work.get("publication_year") or ""),
                    "Journal":       source.get("display_name") or "",
                    "DOI":           normalize_doi(work.get("doi")),
                    "URL":           primary.get("landing_page_url") or work.get("doi") or "",
                    "Source database": "OpenAlex",
                    "Search query":  query,
                    "Record type: primary / review / book chapter / unknown":
                        _record_type(work.get("title") or "", work.get("type") or ""),
                    "Abstract":      _abstract(work.get("abstract_inverted_index")),
                    "OpenAlex ID":   work.get("id") or "",
                    "Referenced works": "|".join(work.get("referenced_works") or []),
                    "Cited by count": str(work.get("cited_by_count") or 0),
                })
                records.append(rec)
        except Exception as exc:
            logs.append(_log_entry("OpenAlex", query, group, "keyword search", 0, "ERROR", str(exc)))
    return records, logs


def _search_crossref(all_queries: list[tuple[str, str]],
                     per_query: int, mailto: str = "") -> tuple[list[dict], list[dict]]:
    records, logs = [], []
    for group, query in all_queries:
        params = {"query.bibliographic": query, "rows": per_query}
        if mailto:
            params["mailto"] = mailto
        try:
            resp = http_get(CROSSREF_URL, params=params)
            resp.raise_for_status()
            items = resp.json().get("message", {}).get("items", [])
            logs.append(_log_entry("Crossref", query, group, "keyword search", len(items), "OK"))
            for item in items:
                dates = item.get("published", {}).get("date-parts", [[]])
                authors = [
                    " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
                    for a in item.get("author", [])
                ]
                rec = empty_record()
                rec.update({
                    "Title":    clean_text((item.get("title") or [""])[0]),
                    "Authors":  "; ".join(filter(None, authors)),
                    "Year":     str(dates[0][0]) if dates and dates[0] else "",
                    "Journal":  clean_text((item.get("container-title") or [""])[0]),
                    "DOI":      normalize_doi(item.get("DOI")),
                    "URL":      item.get("URL") or "",
                    "Source database": "Crossref",
                    "Search query": query,
                    "Record type: primary / review / book chapter / unknown":
                        _record_type((item.get("title") or [""])[0], item.get("type") or ""),
                    "Referenced works": "|".join(
                        f"https://doi.org/{normalize_doi(ref.get('DOI'))}"
                        for ref in item.get("reference", []) if ref.get("DOI")
                    ),
                })
                records.append(rec)
        except Exception as exc:
            logs.append(_log_entry("Crossref", query, group, "keyword search", 0, "ERROR", str(exc)))
    return records, logs


def _search_semantic_scholar(all_queries: list[tuple[str, str]],
                              per_query: int, api_key: str = "") -> tuple[list[dict], list[dict]]:
    records, logs = [], []
    headers = {"x-api-key": api_key} if api_key else {}
    for group, query in all_queries:
        try:
            resp = http_get(SEMANTIC_SCHOLAR_URL,
                            params={"query": query, "limit": per_query, "fields": SEMANTIC_FIELDS},
                            headers=headers)
            if resp.status_code == 429:
                logs.append(_log_entry("Semantic Scholar", query, group, "keyword search",
                                       0, "RATE LIMITED", "Set SEMANTIC_SCHOLAR_API_KEY for improved coverage."))
                break
            resp.raise_for_status()
            papers = resp.json().get("data", [])
            logs.append(_log_entry("Semantic Scholar", query, group, "keyword search", len(papers), "OK"))
            for paper in papers:
                rec = empty_record()
                rec.update({
                    "Title":    clean_text(paper.get("title")),
                    "Authors":  "; ".join(a.get("name", "") for a in paper.get("authors", [])),
                    "Year":     str(paper.get("year") or ""),
                    "Journal":  paper.get("venue") or "",
                    "DOI":      normalize_doi((paper.get("externalIds") or {}).get("DOI")),
                    "URL":      paper.get("url") or "",
                    "Source database": "Semantic Scholar",
                    "Search query": query,
                    "Record type: primary / review / book chapter / unknown":
                        _record_type(paper.get("title") or ""),
                    "Abstract": paper.get("abstract") or "",
                    "Cited by count": str(paper.get("citationCount") or 0),
                })
                records.append(rec)
        except Exception as exc:
            logs.append(_log_entry("Semantic Scholar", query, group, "keyword search", 0, "ERROR", str(exc)))
    return records, logs


# ── Citation chasing ──────────────────────────────────────────────────────────

def _fetch_work_ids(ids: list[str], query: str, mode: str, cap: int = 100) -> tuple[list[dict], dict]:
    ids = [i for i in ids if i][:cap]
    if not ids:
        return [], _log_entry("OpenAlex", query, mode, "citation chasing", 0,
                              "SKIPPED", "No references exposed by source metadata.")
    records = []
    try:
        for start in range(0, len(ids), 50):
            batch = ids[start:start + 50]
            short_ids = [i.rsplit("/", 1)[-1] for i in batch]
            resp = http_get(OPENALEX_URL,
                            params={"filter": f"openalex:{'|'.join(short_ids)}", "per-page": 50})
            resp.raise_for_status()
            for work in resp.json().get("results", []):
                primary = work.get("primary_location") or {}
                source  = primary.get("source") or {}
                rec = empty_record()
                title = clean_text(work.get("title"))
                rec.update({
                    "Title":    title,
                    "Authors":  "; ".join(
                        item.get("author", {}).get("display_name", "")
                        for item in work.get("authorships", []) if item.get("author")
                    ),
                    "Year":     str(work.get("publication_year") or ""),
                    "Journal":  source.get("display_name") or "",
                    "DOI":      normalize_doi(work.get("doi")),
                    "URL":      primary.get("landing_page_url") or work.get("doi") or "",
                    "Source database": f"OpenAlex {mode}",
                    "Search query": query,
                    "Record type: primary / review / book chapter / unknown":
                        "review" if "review" in title.lower() else (
                            "primary" if work.get("type") in {"article", "preprint"} else "unknown"
                        ),
                    "Abstract":  _abstract(work.get("abstract_inverted_index")),
                    "OpenAlex ID": work.get("id") or "",
                    "Referenced works": "|".join(work.get("referenced_works") or []),
                    "Cited by count": str(work.get("cited_by_count") or 0),
                })
                records.append(rec)
        return records, _log_entry("OpenAlex", query, mode, "citation chasing", len(records), "OK")
    except Exception as exc:
        return records, _log_entry("OpenAlex", query, mode, "citation chasing",
                                   len(records), "ERROR", str(exc))


def _fetch_forward_citations(openalex_id: str, query: str, cap: int = 50) -> tuple[list[dict], dict]:
    if not openalex_id:
        return [], _log_entry("OpenAlex", query, "forward citations",
                              "citation chasing", 0, "SKIPPED", "No OpenAlex ID.")
    short_id = openalex_id.rsplit("/", 1)[-1]
    try:
        resp = http_get(OPENALEX_URL,
                        params={"filter": f"cites:{short_id}", "per-page": min(cap, 100)})
        resp.raise_for_status()
        records = []
        for work in resp.json().get("results", []):
            primary = work.get("primary_location") or {}
            source  = primary.get("source") or {}
            rec = empty_record()
            title = clean_text(work.get("title"))
            rec.update({
                "Title":    title,
                "Authors":  "; ".join(
                    item.get("author", {}).get("display_name", "")
                    for item in work.get("authorships", []) if item.get("author")
                ),
                "Year":     str(work.get("publication_year") or ""),
                "Journal":  source.get("display_name") or "",
                "DOI":      normalize_doi(work.get("doi")),
                "URL":      primary.get("landing_page_url") or work.get("doi") or "",
                "Source database": "OpenAlex forward citations",
                "Search query": query,
                "Record type: primary / review / book chapter / unknown":
                    "review" if "review" in title.lower() else "primary",
                "Abstract":  _abstract(work.get("abstract_inverted_index")),
                "OpenAlex ID": work.get("id") or "",
                "Referenced works": "|".join(work.get("referenced_works") or []),
                "Cited by count": str(work.get("cited_by_count") or 0),
            })
            records.append(rec)
        return records, _log_entry("OpenAlex", query, "forward citations",
                                   "citation chasing", len(records), "OK")
    except Exception as exc:
        return [], _log_entry("OpenAlex", query, "forward citations",
                              "citation chasing", 0, "ERROR", str(exc))


def _chase_citations(records: list[dict], max_reviews: int, max_primary: int) -> tuple[list[dict], list[dict]]:
    additions, logs = [], []
    reviews = [r for r in records if r.get("Record type: primary / review / book chapter / unknown") == "review"]
    reviews.sort(key=lambda r: int(r.get("Cited by count") or 0), reverse=True)
    for review in reviews[:max_reviews]:
        refs = [i for i in review.get("Referenced works", "").split("|")
                if i.startswith("https://openalex.org/")]
        found, entry = _fetch_work_ids(refs, review.get("Title", ""), "review reference list", cap=150)
        additions.extend(found)
        logs.append(entry)
    primaries = [
        r for r in records
        if r.get("Record type: primary / review / book chapter / unknown") == "primary"
        and any(t in f"{r.get('Title','')} {r.get('Abstract','')}".lower()
                for t in ["iron", " fe ", "cobalt", " co ", "manganese", " mn ", "nickel", " ni ",
                          "enantioselective", "asymmetric"])
    ]
    primaries.sort(key=lambda r: int(r.get("Cited by count") or 0), reverse=True)
    for primary in primaries[:max_primary]:
        refs = [i for i in primary.get("Referenced works", "").split("|")
                if i.startswith("https://openalex.org/")]
        backward, bl = _fetch_work_ids(refs, primary.get("Title", ""), "backward citations", cap=80)
        forward, fl  = _fetch_forward_citations(primary.get("OpenAlex ID", ""), primary.get("Title", ""), cap=50)
        additions.extend(backward)
        additions.extend(forward)
        logs.extend([bl, fl])
    return additions, logs


# ── Main run function ─────────────────────────────────────────────────────────

def run(cfg: dict) -> dict:
    """
    Execute Stage 1: literature search + citation chasing.

    Returns a stats dict:
        raw_records, citation_records, deduplicated_records, output_excel
    """
    prefix        = cfg["output"]["prefix"]
    outputs_dir   = Path(cfg["output"]["outputs_dir"])
    logs_dir      = Path(cfg["output"]["logs_dir"])
    data_dir      = Path(cfg["output"]["data_subdir"])
    master_excel  = outputs_dir / cfg["output"]["master_excel"]
    per_query     = cfg["search"].get("per_query", 12)
    max_reviews   = cfg["search"].get("max_reviews", 12)
    max_primary   = cfg["search"].get("max_primary", 12)
    mailto        = os.getenv("OPENALEX_EMAIL", cfg["search"].get("openalex_email", ""))
    ss_key        = os.getenv("SEMANTIC_SCHOLAR_API_KEY", cfg["search"].get("semantic_scholar_api_key", ""))

    for d in (outputs_dir, logs_dir, data_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Build flat query list from config groups
    query_groups = cfg["search"].get("query_groups", {})
    all_queries  = [(group, q) for group, qs in query_groups.items() for q in qs]

    print(f"[search] {prefix} — {len(all_queries)} queries across 3 sources")

    records, logs = [], []

    for source, fn in [
        ("OpenAlex",         lambda: _search_openalex(all_queries, per_query, mailto)),
        ("Crossref",         lambda: _search_crossref(all_queries, per_query, mailto)),
        ("Semantic Scholar", lambda: _search_semantic_scholar(all_queries, per_query, ss_key)),
    ]:
        try:
            new_records, new_logs = fn()
            records.extend(new_records)
            logs.extend(new_logs)
            print(f"  {source}: {len(new_records)} raw records")
        except Exception as exc:
            log_event(logs_dir / "pipeline.jsonl", "search_source_error",
                      source=source, error=str(exc))

    raw_count = len(records)
    records   = deduplicate(records, cfg["screening"].get("title_threshold", 0.94))
    print(f"  After deduplication: {len(records)}")

    # Citation chasing
    cit_records, cit_logs = _chase_citations(records, max_reviews, max_primary)
    records = deduplicate(records + cit_records, cfg["screening"].get("title_threshold", 0.94))
    logs.extend(cit_logs)
    print(f"  After citation chasing + dedup: {len(records)}")

    # Export
    log_columns = ["Timestamp UTC", "Source database", "Search query", "Search group",
                   "Search mode", "Results returned", "Status", "Notes"]
    export_records_xlsx(
        records, LITERATURE_COLUMNS, master_excel,
        sheet_name="all_records",
        extra_sheets={"search_log": logs},
        extra_sheet_columns={"search_log": log_columns},
    )
    (data_dir / "master_records.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "search_log.json").write_text(
        json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log_event(logs_dir / "pipeline.jsonl", "literature_search_complete",
              prefix=prefix, raw=raw_count, citation=len(cit_records), total=len(records))

    print(f"[search] Done. Output: {master_excel}")
    return {
        "raw_records":           raw_count,
        "citation_records":      len(cit_records),
        "deduplicated_records":  len(records),
        "output_excel":          str(master_excel),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1: Literature search")
    parser.add_argument("--config", required=True,
                        help="Path to metal config YAML, e.g. config/Fe_H2_asymmetric_hydrogenation.yaml")
    parser.add_argument("--per-query",   type=int)
    parser.add_argument("--max-reviews", type=int)
    parser.add_argument("--max-primary", type=int)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.per_query:
        cfg["search"]["per_query"] = args.per_query
    if args.max_reviews:
        cfg["search"]["max_reviews"] = args.max_reviews
    if args.max_primary:
        cfg["search"]["max_primary"] = args.max_primary

    state    = ProjectState()
    run_id   = make_run_id(cfg["project"]["name"])
    state.start_stage(run_id, "literature_search", config=args.config)
    try:
        stats = run(cfg)
        state.finish_stage(run_id, "literature_search", **stats)
        print(state.summary(run_id))
    except Exception as exc:
        state.fail_stage(run_id, "literature_search", str(exc))
        raise


if __name__ == "__main__":
    main()
