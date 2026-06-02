# Setup Instructions — Hydrogenation Literature Agent

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | https://python.org — add to PATH during install |
| Google Chrome | For browser-mode PDF download (institutional access) |
| Internet access | For API searches and OA PDF downloads |
| Institutional VPN | Recommended for publisher access |

---

## Quick Start (Windows)

### 1. Clone the repository

```bat
git clone https://github.com/YOUR_USERNAME/Hydrogenation_Literature_Agent.git
cd Hydrogenation_Literature_Agent
```

### 2. First-time setup

Double-click **`setup.bat`** or run in Command Prompt from the repository root:

```bat
setup.bat
```

This will:
- Create a `.venv` virtual environment
- Install all Python dependencies
- Install Playwright Chromium
- Create output directories (`outputs/`, `data/`, `papers/`)

### 3. Run the pipeline for Fe (default)

```bat
run_search.bat
run_screening.bat
run_download.bat                                                   rem open-access PDFs
run_download.bat config\Fe_H2_asymmetric_hydrogenation.yaml browser  rem institutional
run_extraction.bat
```

### 4. Run for a different metal (e.g. Cobalt)

```bat
run_search.bat      config\Co_H2_asymmetric_hydrogenation.yaml
run_screening.bat   config\Co_H2_asymmetric_hydrogenation.yaml
run_download.bat    config\Co_H2_asymmetric_hydrogenation.yaml
run_extraction.bat  config\Co_H2_asymmetric_hydrogenation.yaml
```

---

## Environment Variables (Optional)

Copy `.env.example` to `.env` and fill in your credentials:

```bat
copy .env.example .env
```

Or set them inline for the current session:

```bat
set OPENALEX_EMAIL=your@email.com           rem polite pool: faster rate limits
set SEMANTIC_SCHOLAR_API_KEY=your_key       rem higher rate limits
set UNPAYWALL_EMAIL=your@email.com          rem required for Unpaywall OA lookup
```

To persist across sessions, add to Windows System Environment Variables
(Control Panel → System → Advanced → Environment Variables).

---

## Mac / Linux

The `.bat` scripts are Windows-only. Invoke modules directly:

```bash
source .venv/bin/activate   # or: python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

python -m modules.literature_search    --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.title_abstract_screening --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.pdf_download         --config config/Fe_H2_asymmetric_hydrogenation.yaml --mode api
python -m modules.fulltext_screening   --config config/Fe_H2_asymmetric_hydrogenation.yaml
python -m modules.reaction_data_extraction --config config/Fe_H2_asymmetric_hydrogenation.yaml
```

---

## Browser PDF Download (Institutional Access)

For papers behind paywalls, use browser mode:

```bat
run_download.bat config\Fe_H2_asymmetric_hydrogenation.yaml browser
```

Or test a single row first (row numbers are 1-based):

```bat
run_download.bat config\Fe_H2_asymmetric_hydrogenation.yaml browser 5
```

**What happens:**
1. A visible Chrome window opens.
2. The script navigates to each paper's DOI URL.
3. If a **Cloudflare / Anubis / CAPTCHA** challenge appears — complete it, then press ENTER.
4. If a **login** page appears — log in via your institutional SSO, navigate back to the article, then press ENTER.
5. The PDF is downloaded and saved to `papers/manual_access/`.
6. The browser session (cookies) is saved to `~/.cache/hla_browser_session/` and reused on subsequent runs.

> **Security note:** This directory stores your institutional login cookies.
> Never commit or share it — the `.gitignore` excludes it automatically.
> Delete the directory to revoke saved sessions (e.g. when leaving an
> institution or using a shared machine).

---

## Adding a New Metal

1. Copy `templates/config_template.yaml`
2. Save as `config/<Metal>_H2_asymmetric_hydrogenation.yaml`
3. Fill in all `METAL_NAME`, `SYMBOL`, `REGEX` placeholders
4. Run: `run_search.bat config\<Metal>_H2_asymmetric_hydrogenation.yaml`

---

## Resuming an Interrupted Run

Each stage reads from the previous stage's JSON output. If a stage fails:
1. Check `outputs/logs/pipeline.jsonl` for error details.
2. Re-run the failed stage's BAT file — it re-runs that stage from scratch,
   reading from the last successful stage's JSON output.

---

## Output Files Reference

| File | Stage | Contents |
|------|-------|----------|
| `outputs/<prefix>_Master_Literature.xlsx` | 1 | All raw + citation-chased records |
| `outputs/<prefix>_Title_Abstract_Screened.xlsx` | 2 | Screened records with decisions |
| `outputs/<prefix>_Strict_H2_Only.xlsx` | 2 | Only records with explicit H₂ evidence |
| `outputs/<prefix>_Download_Log.xlsx` | 3 | PDF download attempt log |
| `outputs/<prefix>_Fulltext_Screening.xlsx` | 4 | Classified: A/B/C + evidence |
| `outputs/<prefix>_Reaction_Data.xlsx` | 5 | Extracted catalytic data (verify manually!) |
| `data/<prefix>/master_records.json` | 1 | Machine-readable records |
| `data/<prefix>/strict_h2_records.json` | 2 | Machine-readable H₂-filtered records |
| `data/<prefix>/fulltext_screening.json` | 4 | Machine-readable classifications |
| `data/<prefix>/reaction_data.json` | 5 | Machine-readable extracted data |
| `outputs/logs/pipeline.jsonl` | all | Structured event log |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: yaml` | Run `setup.bat` to install dependencies |
| `pypdf` not found | `pip install pypdf` or run `setup.bat` |
| Browser opens but no Chrome | Install Chrome from https://google.com/chrome |
| Cloudflare blocks all papers | Your IP may be flagged; try using university VPN |
| Empty Stage 1 output | Check internet; verify API endpoints are reachable |
| Low Stage 2 yield | Broaden search queries in config YAML |
