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


def send_to_provider(provider: Provider, command: str, prompt: Path) -> subprocess.Popen:
    if provider.kind != "freebuff" and provider.kind != "local":
        raise PromptError(f"Provider {provider.id} cannot receive stdin prompts.")
    with prompt.open("r", encoding="utf-8") as prompt_file:
        process = subprocess.Popen([command], stdin=prompt_file)
        return_code = process.wait()
    if return_code:
        raise PromptError(f"{provider.label} exited with status {return_code}.")
    return process
