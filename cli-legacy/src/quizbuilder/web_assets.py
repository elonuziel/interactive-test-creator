from __future__ import annotations

from pathlib import Path


ASSET_NAMES = ("index.html", "app.js", "style.css", "cropper.min.js", "cropper.min.css")


def list_assets(web_root: Path) -> dict[str, Path]:
    return {name: web_root / name for name in ASSET_NAMES if (web_root / name).is_file()}


def validate_assets(web_root: Path) -> list[str]:
    return [name for name in ("index.html", "app.js", "style.css") if not (web_root / name).is_file()]
