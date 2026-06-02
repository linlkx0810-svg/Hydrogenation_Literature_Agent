"""
config_loader.py
Loads and merges base_config.yaml + metal-specific config YAML.
All modules receive a single flat `cfg` dict.
"""

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(metal_config_path: str | Path) -> dict[str, Any]:
    """
    Load base_config.yaml and merge the metal-specific YAML on top.

    Parameters
    ----------
    metal_config_path : str or Path
        Path to a metal config file, e.g. ``config/Fe_H2_asymmetric_hydrogenation.yaml``.
        Relative paths are resolved against the project root.

    Returns
    -------
    dict
        Merged configuration dictionary.
    """
    project_root = Path(__file__).parent.parent
    metal_path = Path(metal_config_path)
    if not metal_path.is_absolute():
        metal_path = project_root / metal_path

    base_path = CONFIG_DIR / "base_config.yaml"

    with base_path.open(encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}

    with metal_path.open(encoding="utf-8") as f:
        metal = yaml.safe_load(f) or {}

    cfg = _deep_merge(base, metal)

    # Resolve output directories relative to project root
    for key in ("outputs_dir", "papers_api_dir", "papers_manual_dir", "logs_dir"):
        raw = cfg.get("output", {}).get(key, "")
        if raw and not Path(raw).is_absolute():
            cfg["output"][key] = str(project_root / raw)

    data_sub = cfg.get("output", {}).get("data_subdir", "")
    if data_sub and not Path(data_sub).is_absolute():
        cfg["output"]["data_subdir"] = str(project_root / data_sub)

    cfg["_project_root"] = str(project_root)
    cfg["_metal_config"] = str(metal_path)
    return cfg
