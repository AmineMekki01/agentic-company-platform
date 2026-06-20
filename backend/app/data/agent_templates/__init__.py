"""Agent template loader.

Templates are stored as static JSON files in this directory.
Each file is a self-contained agent definition that can be deployed
by an admin to create a fully configured agent + workflows.
"""

import json
from pathlib import Path
from typing import Any


_TEMPLATE_DIR = Path(__file__).parent


def load_all_templates() -> list[dict[str, Any]]:
    """Load every .json file in the templates directory."""
    templates: list[dict[str, Any]] = []
    for path in _TEMPLATE_DIR.glob("*.json"):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Derive id from filename if not present
            if "id" not in data:
                data["id"] = path.stem
            templates.append(data)
    # stable ordering
    templates.sort(key=lambda t: t.get("name", t.get("id", "")))
    return templates


def load_template(template_id: str) -> dict[str, Any] | None:
    """Load a single template by its id (filename stem)."""
    path = _TEMPLATE_DIR / f"{template_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "id" not in data:
        data["id"] = path.stem
    return data
