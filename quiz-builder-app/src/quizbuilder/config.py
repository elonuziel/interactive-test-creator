from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from .paths import scripts_root, tests_root


@dataclass
class ProviderConfig:
    freebuff_commands: tuple[str, ...] = ("freebuff", "freebuff-cli")
    open_browser: bool = True


@dataclass
class Config:
    workspace_root: Path
    scripts_root: Path = field(default_factory=scripts_root)
    default_form: str = "0"
    default_discard_pages: str = "std"
    auto_build: bool = True
    super_batch_workers: int = 2
    super_batch_ai_mode: str = "two_phase"
    provider: ProviderConfig = field(default_factory=ProviderConfig)

    @classmethod
    def defaults(cls, root: Path | None = None) -> "Config":
        return cls(workspace_root=root or tests_root())

    @classmethod
    def load(cls, path: Path | None = None, root: Path | None = None) -> "Config":
        config = cls.defaults(root)
        config_path = path or Path(os.environ["QUIZBUILDER_CONFIG"]) if "QUIZBUILDER_CONFIG" in os.environ else path
        if not config_path or not config_path.is_file():
            return config

        try:
            import tomllib
        except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
            import tomli as tomllib

        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        config.workspace_root = Path(data.get("workspace_root", config.workspace_root)).expanduser()
        if "scripts_root" in data:
            config.scripts_root = Path(data["scripts_root"]).expanduser()
        config.default_form = str(data.get("default_form", config.default_form))
        config.default_discard_pages = str(data.get("default_discard_pages", config.default_discard_pages))
        config.auto_build = bool(data.get("auto_build", config.auto_build))
        config.super_batch_workers = max(1, int(data.get("super_batch_workers", config.super_batch_workers)))
        config.super_batch_ai_mode = str(data.get("super_batch_ai_mode", config.super_batch_ai_mode))
        provider = data.get("provider", {})
        config.provider = ProviderConfig(
            freebuff_commands=tuple(provider.get("freebuff_commands", config.provider.freebuff_commands)),
            open_browser=bool(provider.get("open_browser", config.provider.open_browser)),
        )
        return config
