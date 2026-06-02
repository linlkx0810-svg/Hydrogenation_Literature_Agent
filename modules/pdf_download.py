"""
modules/pdf_download.py
───────────────────────
Stage 3: PDF acquisition.

Two complementary strategies:
  A) API/OA download  — tries OpenAlex, Unpaywall, Crossref OA links (no login needed).
  B) Browser download — headful Playwright + system Chrome for institutional access.
                        Pauses for manual login / Cloudflare / Anubis challenges.

Entry points
------------
    from modules.pdf_download import run_api, run_browser
    stats_a = run_api(cfg)      # automated, no interaction required
    stats_b = run_browser(cfg)  # interactive, must be run from your own terminal
"""

import argparse
import asyncio
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import pandas as pd

from utils import load_config, log_event, ProjectState, make_run_id
from utils.text_utils import http_get, normalize_doi, safe_filename, timestamp, load_json
from utils.excel_io import append_log_xlsx

# Fix Windows terminal encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

OPENALEX_URL   = "https://api.openalex.org/works"
UNPAYWALL_URL  = "https://api.unpaywall.org/v2"
CROSSREF_URL   = "https://api.crossref.org/works"

DOWNLOAD_LOG_COLUMNS = [
    "Row", "DOI", "Title", "Year", "Authors", "Tier",
    "Status", "PDF_path", "Notes", "Timestamp",
]

# ── Challenge / bot-protection keywords ──────────────────────────────────────
CHALLENGE_KEYWORDS = {
    "anubis":     ["anubis", "techaro", "proof of work", "拒绝访问", "哎呀糟糕了", "bot protection"],
    "cloudflare": ["cloudflare", "ray id:", "请稍候", "just a moment",
                   "checking your browser", "正在进行安全验证"],
    "captcha":    ["captcha", "i am not a robot", "recaptcha", "hcaptcha", "verify you are human"],
}
PAYWALL_PATTERNS = [
    "purchase access", "buy this article", "buy article", "subscribe to read",
    "subscribe for access", "you do not have access", "full text is not available",
    "content is not available", "access denied", "full access required",
    "rent or buy", "get full access",
]
LOGIN_SELECTORS = [
    "input[type='password']",
    "form[action*='login' i]",
    "form[action*='signin' i]",
    "[id*='loginForm' i]",
    "[class*='login-form' i]",
]
PDF_LINK_SELECTORS = [
    "a[data-track-action='download pdf' i]",
    "a[data-track-action='pdf download' i]",
    "a[data-article-url$='.pdf']",
    "a[href$='.pdf']",
    "a[href*='/pdf/'][href*='doi']",
    "a[href*='/pdf/']",
    "a[title='Download PDF' i]",
    "a[title='PDF' i]",
    "a[aria-label*='Download PDF' i]",
    "a[aria-label*='PDF' i]",
    "[class*='c-pdf-download'] a",
    "[class*='pdf-download'] a",
    "[class*='download-pdf'] a",
    "a:text-is('PDF')",
    "a:text-matches('^Download PDF$', 'i')",
    "a:text-matches('Full.?Text PDF', 'i')",
    "a:text-matches('View PDF', 'i')",
    "a:text-matches('Open PDF', 'i')",
]
SUPPLEMENTARY_KEYWORDS = [
    "suppl_file", "suppl/", "supplementary", "_si_", "_si.", "-si.", "-si_",
    "supporting_information", "supporting-information", "supp_", "/supp.",
    "esm", "/esm.", "s1.pdf", "s2.pdf", "s3.pdf",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Part A: API / OA download (automated)
# ═══════════════════════════════════════════════════════════════════════════════

def _oa_urls_openalex(doi: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    resp = http_get(f"{OPENALEX_URL}/https://doi.org/{quote(doi, safe='')}", timeout=20)
    if resp.status_code == 404:
        return urls
    resp.raise_for_status()
    payload = resp.json()
    for loc in [payload.get("best_oa_location")] + (payload.get("locations") or []):
        if loc and loc.get("pdf_url"):
            entry = ("OpenAlex OA", loc["pdf_url"].strip())
            if entry not in urls:
                urls.append(entry)
    return urls


def _oa_urls_unpaywall(doi: str, email: str) -> list[tuple[str, str]]:
    if not email:
        return []
    urls: list[tuple[str, str]] = []
    resp = http_get(f"{UNPAYWALL_URL}/{quote(doi, safe='')}", params={"email": email}, timeout=20)
    if resp.status_code == 404:
        return urls
    resp.raise_for_status()
    payload = resp.json()
    for loc in [payload.get("best_oa_location")] + (payload.get("oa_locations") or []):
        if loc and loc.get("url_for_pdf"):
            entry = ("Unpaywall OA", loc["url_for_pdf"].strip())
            if entry not in urls:
                urls.append(entry)
    return urls


def _oa_urls_crossref(doi: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    resp = http_get(f"{CROSSREF_URL}/{quote(doi, safe='')}", timeout=20)
    if resp.status_code == 404:
        return urls
    resp.raise_for_status()
    for link in (resp.json().get("message") or {}).get("link") or []:
        if "pdf" in str(link.get("content-type") or "").lower() and link.get("URL"):
            entry = ("Crossref PDF link", link["URL"].strip())
            if entry not in urls:
                urls.append(entry)
    return urls


def _download_raw(url: str, dest: Path, min_bytes: int = 15_000) -> tuple[bool, str]:
    resp = http_get(url, allow_redirects=True, timeout=45)
    resp.raise_for_status()
    ct = resp.headers.get("content-type", "").lower()
    if not resp.content.startswith(b"%PDF") and "application/pdf" not in ct:
        return False, f"Not a PDF: {ct}"
    if len(resp.content) < min_bytes:
        return False, f"File too small: {len(resp.content)} bytes"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True, f"{len(resp.content) // 1024} KB"


def _build_filename(record: dict) -> str:
    year = str(int(record.get("Year") or 0)) if record.get("Year") else "XXXX"
    authors = str(record.get("Authors") or "")
    if authors and authors != "nan":
        last = authors.split(";")[0].strip().split()[-1]
        first_author = re.sub(r"[^\w-]", "", last)[:20] or "Unknown"
    else:
        first_author = "Unknown"
    title = str(record.get("Title") or "Untitled")
    short = re.sub(r"[^\w\s-]", "", title)
    short = "_".join(short.split()[:4])[:45].strip("_") or "paper"
    return f"{year}_{first_author}_{short}.pdf"


def run_api(cfg: dict) -> dict:
    """
    Automated OA PDF download via APIs (OpenAlex, Unpaywall, Crossref).
    Does NOT require browser interaction.
    """
    prefix      = cfg["output"]["prefix"]
    outputs_dir = Path(cfg["output"]["outputs_dir"])
    logs_dir    = Path(cfg["output"]["logs_dir"])
    data_dir    = Path(cfg["output"]["data_subdir"])
    papers_dir  = Path(cfg["output"]["papers_api_dir"])
    log_excel   = outputs_dir / cfg["output"]["download_log_excel"]
    min_bytes   = cfg["pdf_download"].get("min_pdf_bytes", 15_000)
    email       = os.getenv("UNPAYWALL_EMAIL", "")

    papers_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load records from Stage 2
    records_path = data_dir / "strict_h2_records.json"
    if not records_path.exists():
        raise FileNotFoundError(f"Stage 2 output not found: {records_path}")
    records = load_json(records_path, [])

    success, failed, skipped = 0, 0, 0

    for idx, record in enumerate(records, 1):
        doi   = normalize_doi(record.get("DOI"))
        title = record.get("Title", "")[:60]
        dest  = papers_dir / safe_filename(doi.replace("/", "_"))

        log_row = {
            "Row": idx, "DOI": doi, "Title": title,
            "Year": record.get("Year", ""), "Authors": str(record.get("Authors", ""))[:60],
            "Tier": record.get("Original tier", ""), "Status": "", "PDF_path": "",
            "Notes": "", "Timestamp": timestamp(),
        }

        if dest.exists():
            log_row.update({"Status": "REUSED", "PDF_path": str(dest)})
            append_log_xlsx(log_row, DOWNLOAD_LOG_COLUMNS, log_excel)
            skipped += 1
            continue

        urls = []
        for fn in (_oa_urls_openalex, _oa_urls_crossref):
            try:
                urls.extend(fn(doi))
            except Exception:
                pass
        try:
            urls.extend(_oa_urls_unpaywall(doi, email))
        except Exception:
            pass

        if not urls:
            log_row.update({"Status": "NO_OA_URL", "Notes": "No OA PDF URL found"})
            append_log_xlsx(log_row, DOWNLOAD_LOG_COLUMNS, log_excel)
            failed += 1
            continue

        downloaded = False
        for source, url in urls:
            try:
                ok, note = _download_raw(url, dest, min_bytes)
                if ok:
                    log_row.update({"Status": "SUCCESS", "PDF_path": str(dest),
                                    "Notes": f"{source}: {note}"})
                    success += 1
                    downloaded = True
                    break
            except Exception as exc:
                pass

        if not downloaded:
            log_row.update({"Status": "DOWNLOAD_FAILED",
                            "Notes": f"Tried {len(urls)} OA URLs, none succeeded"})
            failed += 1

        append_log_xlsx(log_row, DOWNLOAD_LOG_COLUMNS, log_excel)
        print(f"  [{idx}/{len(records)}] {doi[:40]:<42} {log_row['Status']}")

    log_event(logs_dir / "pipeline.jsonl", "pdf_api_download_complete",
              prefix=prefix, success=success, failed=failed, skipped=skipped)
    print(f"[pdf_download:api] {prefix} — success={success}, failed={failed}, reused={skipped}")
    return {"success": success, "failed": failed, "reused": skipped}


# ═══════════════════════════════════════════════════════════════════════════════
# Part B: Browser download (Playwright / institutional access)
# ═══════════════════════════════════════════════════════════════════════════════

def _pause(msg: str) -> None:
    print()
    print("=" * 65)
    print(msg)
    print("=" * 65)
    input("  >>> Press ENTER when you are ready to continue... ")
    print()


def _is_supplementary(url: str) -> bool:
    u = url.lower()
    return any(kw in u for kw in SUPPLEMENTARY_KEYWORDS)


def _acs_main_pdf(page_url: str) -> str | None:
    if "pubs.acs.org" not in page_url:
        return None
    m = re.search(r"(10\.\d{4,}/\S+)", page_url)
    if m:
        doi_part = m.group(1).split("?")[0]
        return f"https://pubs.acs.org/doi/pdf/{doi_part}"
    return None


async def _get_page_text(page) -> str:
    try:
        return (await page.inner_text("body")).lower()
    except Exception:
        return ""


async def _detect_challenge(page) -> str | None:
    body  = await _get_page_text(page)
    title = (await page.title()).lower()
    for challenge, keywords in CHALLENGE_KEYWORDS.items():
        if any(kw in body or kw in title for kw in keywords):
            return challenge
    return None


async def _detect_login(page) -> bool:
    for sel in LOGIN_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True
        except Exception:
            pass
    return False


async def _detect_paywall(page) -> bool:
    body = await _get_page_text(page)
    return any(p in body for p in PAYWALL_PATTERNS)


async def _find_pdf_url(page) -> str | None:
    if page.url.lower().endswith(".pdf") and not _is_supplementary(page.url):
        return page.url
    acs = _acs_main_pdf(page.url)
    if acs:
        return acs
    candidates: list[tuple[str, str]] = []
    for sel in PDF_LINK_SELECTORS:
        try:
            for el in await page.query_selector_all(sel):
                try:
                    if not await el.is_visible():
                        continue
                except Exception:
                    continue
                href = await el.get_attribute("href") or ""
                resolved = urljoin(page.url, href.strip()) if href.strip() else None
                if resolved:
                    candidates.append((resolved, sel))
        except Exception:
            continue
    main = [(u, s) for u, s in candidates if not _is_supplementary(u)]
    chosen = main or candidates
    return chosen[0][0] if chosen else None


async def _download_pdf_browser(page, pdf_url: str, dest: Path) -> bool:
    from playwright.async_api import TimeoutError as PwTimeout
    # Strategy 1: expect download event
    try:
        async with page.expect_download(timeout=60_000) as dl_info:
            await page.goto(pdf_url, wait_until="domcontentloaded", timeout=60_000)
            await asyncio.sleep(3)
        download = await dl_info.value
        await download.save_as(dest)
        return True
    except (PwTimeout, Exception):
        pass
    # Strategy 2: navigate and check content-type
    try:
        resp = await page.goto(pdf_url, wait_until="domcontentloaded", timeout=60_000)
        await asyncio.sleep(3)
        ct = (resp.headers.get("content-type") or "") if resp else ""
        if "pdf" in ct.lower() or page.url.lower().endswith(".pdf"):
            pdf_bytes = await page.pdf()
            dest.write_bytes(pdf_bytes)
            return True
    except Exception:
        pass
    # Strategy 3: browser request context fetch
    try:
        response = await page.request.get(pdf_url, timeout=60_000)
        ct = response.headers.get("content-type", "")
        if response.ok and "pdf" in ct.lower():
            body = await response.body()
            if body[:5] == b"%PDF-":
                dest.write_bytes(body)
                return True
    except Exception:
        pass
    return False


async def _process_one_browser(row_idx: int, record: dict, context,
                                papers_dir: Path, log_excel: Path,
                                min_bytes: int, delay_load: float,
                                delay_manual: float) -> dict:
    doi     = normalize_doi(record.get("DOI"))
    url     = str(record.get("URL") or "").strip()
    nav_url = url if url.startswith("http") else (f"https://doi.org/{doi}" if doi else None)
    title   = str(record.get("Title") or "")[:60]

    log_row = {
        "Row": row_idx, "DOI": doi, "Title": title,
        "Year": record.get("Year", ""), "Authors": str(record.get("Authors") or "")[:60],
        "Tier": record.get("Original tier", ""), "Status": "FAIL",
        "PDF_path": "", "Notes": "", "Timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    if not nav_url:
        log_row.update({"Status": "SKIP", "Notes": "No DOI or URL"})
        return log_row

    from playwright.async_api import TimeoutError as PwTimeout
    page = await context.new_page()
    try:
        print(f"\n  [{row_idx}] {doi}")
        try:
            await page.goto(nav_url, wait_until="domcontentloaded", timeout=45_000)
        except PwTimeout:
            log_row.update({"Status": "TIMEOUT", "Notes": "Page load timeout"})
            return log_row
        await asyncio.sleep(delay_load)

        # Challenge checks
        challenge = await _detect_challenge(page)
        if challenge:
            _pause(
                f"[{challenge.upper()} CHALLENGE] Row {row_idx} — {doi}\n"
                f"  Complete the challenge in the browser, then press ENTER."
            )
            await asyncio.sleep(delay_manual)
            if await _detect_challenge(page):
                log_row.update({"Status": "CHALLENGE_UNRESOLVED",
                                "Notes": f"{challenge} challenge not cleared"})
                return log_row

        if await _detect_login(page):
            _pause(
                f"[LOGIN REQUIRED] Row {row_idx} — {doi}\n"
                f"  Log in via your institutional account, navigate back to the\n"
                f"  article page, then press ENTER."
            )
            await asyncio.sleep(delay_manual)
            if await _detect_login(page):
                log_row.update({"Status": "LOGIN_REQUIRED",
                                "Notes": "Login wall still present after manual attempt"})
                return log_row

        if await _detect_paywall(page):
            log_row.update({"Status": "ACCESS_DENIED",
                            "Notes": "Paywall — no institutional access"})
            print(f"    ACCESS DENIED")
            return log_row

        pdf_url = await _find_pdf_url(page)
        if not pdf_url:
            log_row.update({"Status": "NO_PDF_LINK", "Notes": f"No PDF link at {page.url}"})
            print(f"    No PDF link found")
            return log_row

        print(f"    PDF: {pdf_url[:70]}")
        filename = _build_filename(record)
        dest     = papers_dir / filename

        success = await _download_pdf_browser(page, pdf_url, dest)
        if dest.exists() and dest.stat().st_size >= min_bytes:
            with open(dest, "rb") as f:
                header = f.read(5)
            if header == b"%PDF-":
                log_row.update({"Status": "SUCCESS", "PDF_path": str(dest),
                                "Notes": f"Downloaded from {pdf_url}"})
                print(f"    [OK] {dest.name}  ({dest.stat().st_size // 1024} KB)")
            else:
                dest.unlink()
                log_row.update({"Status": "INVALID_FILE", "Notes": "Not a valid PDF"})
        else:
            if dest.exists():
                dest.unlink()
            log_row.update({"Status": "DOWNLOAD_FAILED", "Notes": "No valid file produced"})

    finally:
        await page.close()
    return log_row


async def _browser_main(cfg: dict, row: int | None = None) -> dict:
    from playwright.async_api import async_playwright
    prefix      = cfg["output"]["prefix"]
    outputs_dir = Path(cfg["output"]["outputs_dir"])
    logs_dir    = Path(cfg["output"]["logs_dir"])
    data_dir    = Path(cfg["output"]["data_subdir"])
    papers_dir  = Path(cfg["output"]["papers_manual_dir"])
    log_excel   = outputs_dir / cfg["output"]["download_log_excel"]
    min_bytes   = cfg["pdf_download"].get("min_pdf_bytes", 15_000)
    delay_load  = cfg["pdf_download"].get("delay_after_load", 3.0)
    delay_manual= cfg["pdf_download"].get("delay_after_manual", 4.0)
    inter_delay = cfg["pdf_download"].get("inter_paper_delay", 5.0)
    chrome_exe  = cfg["pdf_download"].get("system_chrome_windows", "")
    session_dir = Path(cfg["pdf_download"].get("browser_session_dir", "~/.cache/hla_browser_session")).expanduser()

    papers_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    records_path = data_dir / "strict_h2_records.json"
    if not records_path.exists():
        raise FileNotFoundError(f"Stage 2 output not found: {records_path}")
    records = load_json(records_path, [])

    if row is not None:
        to_process = [(row, records[row])]
    else:
        to_process = list(enumerate(records))

    print("=" * 65)
    print(f"  {prefix} Browser PDF Downloader")
    print(f"  Papers dir : {papers_dir}")
    print(f"  Log        : {log_excel}")
    print(f"  Session    : {session_dir}")
    print("=" * 65)
    print("  A VISIBLE Chrome window will open.")
    print("  Complete any challenges / logins manually when prompted.")
    print()

    chrome_path = chrome_exe if os.path.exists(chrome_exe) else None

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(session_dir),
            headless=False,
            executable_path=chrome_path,
            slow_mo=500,
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        success, failed = 0, 0
        try:
            for row_idx, record in to_process:
                result = await _process_one_browser(
                    row_idx, record, context, papers_dir, log_excel,
                    min_bytes, delay_load, delay_manual,
                )
                append_log_xlsx(result, DOWNLOAD_LOG_COLUMNS, log_excel)
                if result["Status"] == "SUCCESS":
                    success += 1
                    if row is None:
                        await asyncio.sleep(inter_delay)
                else:
                    failed += 1
        finally:
            await context.close()

    log_event(logs_dir / "pipeline.jsonl", "pdf_browser_download_complete",
              prefix=prefix, success=success, failed=failed)
    if row is not None:
        print(f"\n[pdf_download:browser] Single-row test complete. Status: {result['Status']}")
    else:
        print(f"\n[pdf_download:browser] Done. success={success}, failed={failed}")
    return {"success": success, "failed": failed}


def run_browser(cfg: dict, row: int | None = None) -> dict:
    """Browser-based PDF download. Must be run from an interactive terminal."""
    return asyncio.run(_browser_main(cfg, row=row))


def run_api_wrapper(cfg: dict) -> dict:
    return run_api(cfg)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: PDF download")
    parser.add_argument("--config",  required=True)
    parser.add_argument("--mode",    choices=["api", "browser"], default="api",
                        help="api = automated OA download; browser = institutional Playwright download")
    parser.add_argument("--row",     type=int, default=None,
                        help="Browser mode: test a single row index (default: all)")
    args = parser.parse_args()

    cfg    = load_config(args.config)
    state  = ProjectState()
    run_id = make_run_id(cfg["project"]["name"])
    state.start_stage(run_id, "pdf_download", config=args.config, mode=args.mode)
    try:
        if args.mode == "api":
            stats = run_api(cfg)
        else:
            stats = run_browser(cfg, row=args.row)
        state.finish_stage(run_id, "pdf_download", **stats)
    except Exception as exc:
        state.fail_stage(run_id, "pdf_download", str(exc))
        raise


if __name__ == "__main__":
    main()
