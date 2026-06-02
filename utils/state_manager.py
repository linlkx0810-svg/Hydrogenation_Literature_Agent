"""
state_manager.py
Read/write PROJECT_STATE.json so interrupted runs can be resumed.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE = Path(__file__).parent.parent / "PROJECT_STATE.json"

STAGES = [
    "literature_search",
    "title_abstract_screening",
    "pdf_download",
    "fulltext_screening",
    "reaction_data_extraction",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectState:
    """
    Thin wrapper around PROJECT_STATE.json.

    Usage
    -----
    state = ProjectState()
    state.start_stage("literature_search", config="Fe_H2_asymmetric_hydrogenation.yaml")
    state.finish_stage("literature_search", records=85)
    if state.is_done("literature_search"):
        ...
    """

    def __init__(self, path: Path = STATE_FILE) -> None:
        self.path = path
        self._data = self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "version": "1.0",
            "created": _now(),
            "last_updated": _now(),
            "runs": {},
        }

    def save(self) -> None:
        self._data["last_updated"] = _now()
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── Run management ────────────────────────────────────────────────────────

    def _run(self, run_id: str) -> dict[str, Any]:
        return self._data["runs"].setdefault(run_id, {"stages": {}})

    def start_stage(self, run_id: str, stage: str, **meta: Any) -> None:
        """Mark a stage as started."""
        if stage not in STAGES:
            raise ValueError(f"Unknown stage: {stage}. Valid stages: {STAGES}")
        run = self._run(run_id)
        run["stages"][stage] = {
            "status": "running",
            "started": _now(),
            "finished": None,
            **meta,
        }
        self.save()

    def finish_stage(self, run_id: str, stage: str, **results: Any) -> None:
        """Mark a stage as successfully completed."""
        run = self._run(run_id)
        entry = run["stages"].setdefault(stage, {})
        entry.update({"status": "done", "finished": _now(), **results})
        self.save()

    def fail_stage(self, run_id: str, stage: str, error: str) -> None:
        """Mark a stage as failed."""
        run = self._run(run_id)
        entry = run["stages"].setdefault(stage, {})
        entry.update({"status": "failed", "finished": _now(), "error": error})
        self.save()

    def is_done(self, run_id: str, stage: str) -> bool:
        return self._run(run_id).get("stages", {}).get(stage, {}).get("status") == "done"

    def get_stage(self, run_id: str, stage: str) -> dict[str, Any]:
        return self._run(run_id).get("stages", {}).get(stage, {})

    def summary(self, run_id: str) -> str:
        stages = self._run(run_id).get("stages", {})
        lines = [f"Run: {run_id}"]
        for stage in STAGES:
            info = stages.get(stage, {})
            status = info.get("status", "not started")
            extra = ""
            if "records" in info:
                extra = f" | records={info['records']}"
            elif "downloaded" in info:
                extra = f" | downloaded={info['downloaded']}"
            lines.append(f"  {stage:<35} {status}{extra}")
        return "\n".join(lines)

    def list_runs(self) -> list[str]:
        return list(self._data["runs"].keys())


def make_run_id(config_name: str) -> str:
    """Generate a run ID from config name + timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = config_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"{safe}_{ts}"
