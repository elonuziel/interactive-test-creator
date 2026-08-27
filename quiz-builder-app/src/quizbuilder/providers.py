from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import shutil
import subprocess
import webbrowser


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    kind: str
    commands: tuple[str, ...] = ()
    url: str | None = None

    def detect(self, lookup=shutil.which) -> str | None:
        for command in self.commands:
            found = lookup(command)
            if found:
                return found
        return None


WEB_PROVIDERS = (
    Provider("chatgpt", "ChatGPT", "web", url="https://chatgpt.com"),
    Provider("gemini-web", "Gemini Web", "web", url="https://gemini.google.com"),
    Provider("claude-web", "Claude Web", "web", url="https://claude.ai"),
    Provider("ai-studio", "Google AI Studio", "web", url="https://aistudio.google.com"),
    Provider("freebuff-web", "Freebuff Chat", "web", url="https://freebuff.com/chat"),
)


def local_providers(freebuff_commands=("freebuff", "freebuff-cli")):
    return (
        Provider("agy", "Antigravity (agy)", "local", commands=("agy",)),
        Provider("freebuff", "Freebuff CLI", "freebuff", commands=tuple(freebuff_commands)),
        Provider("claude", "Claude Code CLI", "local", commands=("claude",)),
        Provider("chatgpt", "ChatGPT CLI", "local", commands=("chatgpt", "sgpt", "openai")),
        Provider("gemini", "Gemini CLI", "local", commands=("gemini",)),
        Provider("ollama", "Ollama CLI", "local", commands=("ollama",)),
        Provider("llm", "LLM CLI", "local", commands=("llm",)),
    )


def detect_freebuff_command(path_lookup=shutil.which, command_names=("freebuff", "freebuff-cli")) -> str | None:
    for name in command_names:
        command_path = path_lookup(name)
        if command_path:
            return command_path
    return None


def detect_providers(freebuff_commands=("freebuff", "freebuff-cli"), lookup=shutil.which):
    detected = []
    for provider in local_providers(freebuff_commands):
        command = provider.detect(lookup)
        if command:
            detected.append((provider, command))
    return detected


def send_prompt_to_command(command: str, prompt_path: Path) -> subprocess.Popen:
    """Run a provider command and report failures with actionable context."""
    with prompt_path.open("r", encoding="utf-8") as prompt_file:
        process = subprocess.Popen([command], stdin=prompt_file)
        return_code = process.wait()
    if return_code:
        logging.getLogger(__name__).error("Provider command %s exited with status %s", command, return_code)
        raise RuntimeError(f"Provider command exited with status {return_code}. Check that the provider is installed and logged in.")
    return process


def open_web_provider(provider: Provider) -> bool:
    return bool(provider.url and webbrowser.open(provider.url))
