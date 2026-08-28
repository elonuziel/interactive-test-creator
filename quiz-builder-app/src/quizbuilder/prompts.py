from __future__ import annotations

from pathlib import Path
import subprocess

from .providers import Provider


class PromptError(RuntimeError):
    pass


def prompt_path(workspace: Path, provider_kind: str = "local") -> Path:
    filename = "prompt_web_ai.txt" if provider_kind == "web" else "prompt_local_agent.txt"
    return workspace / filename


def generate_prompt(runner, workspace: Path, test_name: str, form_number: str, has_answers: bool, kind: str) -> Path:
    output = prompt_path(workspace, kind)
    result = runner.run(
        "generate_prompts.py",
        str(workspace), test_name, str(form_number), "1" if has_answers else "0", kind,
    )
    if not result.ok or not output.is_file():
        detail = (result.stderr or result.stdout or "prompt generation failed").strip()
        raise PromptError(detail)
    return output


import re
import sys


def extract_markdown_from_response(text: str) -> str:
    """Extract markdown content from an LLM response if wrapped in code blocks or headers."""
    text = text.strip()
    match = re.search(r"```(?:markdown)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def send_to_provider(provider: Provider, command: str, prompt: Path, cwd: Path | None = None) -> str:
    if provider.kind not in {"freebuff", "local"}:
        raise PromptError(f"Provider {provider.id} cannot receive stdin prompts.")
    prompt_text = prompt.read_text(encoding="utf-8")
    cmd_list = [command]
    if "freebuff" in Path(command).name.lower() and cwd:
        cmd_list = [command, "--cwd", str(cwd)]
    try:
        process = subprocess.run(
            cmd_list,
            input=prompt_text,
            text=True,
            capture_output=True,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            errors="replace",
            shell=(sys.platform == "win32"),
        )
    except OSError as exc:
        raise PromptError(f"Could not execute '{command}': {exc}") from exc

    if process.returncode != 0:
        err = (process.stderr or process.stdout or f"status {process.returncode}").strip()
        raise PromptError(f"{provider.label} exited with status {process.returncode}: {err}")
    return process.stdout or ""
