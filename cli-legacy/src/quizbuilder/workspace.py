from __future__ import annotations

from pathlib import Path

from .models import SourceFiles, Workspace


class WorkspaceError(RuntimeError):
    pass


SCRATCH_NAMES = {
    "raw_text.md", "pdf_type_result.txt", "page_map.json",
    "prompt_local_agent.txt", "prompt_local_agent_enhanced.txt",
    "prompt_web_ai.txt", "prompt_web_ai_enhanced.txt",
    "prompt_proofread.txt", "prompt_proofread_local.txt", "prompt_proofread_web.txt",
    "final_questions.json", "output.json", "response.json", "data.json",
}


def list_workspaces(root: Path) -> list[Workspace]:
    root.mkdir(parents=True, exist_ok=True)
    return [
        Workspace(path.name, path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if path.is_dir()
    ]


def create_workspace(root: Path, name: str) -> Workspace:
    safe_name = name.strip().replace(" ", "_")
    if not safe_name or safe_name in {".", ".."}:
        raise WorkspaceError("Workspace name cannot be empty.")
    path = (root / safe_name).resolve()
    if root.resolve() not in path.parents:
        raise WorkspaceError("Workspace must remain inside the workspace root.")
    path.mkdir(parents=True, exist_ok=True)
    return Workspace(safe_name, path)


def discover_sources(workspace: Workspace) -> SourceFiles:
    files = list(workspace.path.iterdir()) if workspace.path.is_dir() else []
    pdfs = sorted((item for item in files if item.suffix.lower() == ".pdf"), key=lambda p: p.name.lower())
    docx = tuple(sorted((item for item in files if item.suffix.lower() == ".docx"), key=lambda p: p.name.lower()))
    answers = tuple(sorted((item for item in files if item.suffix.lower() in {".csv", ".xls", ".xlsx"}), key=lambda p: p.name.lower()))
    return SourceFiles(
        pdf=workspace.source_pdf or (pdfs[0] if pdfs else None),
        docx=docx,
        answer_keys=workspace.source_answer_keys or answers,
    )


def clean_scratch(workspace: Workspace, include_generated_prompts: bool = True) -> list[Path]:
    removed = []
    names = SCRATCH_NAMES if include_generated_prompts else SCRATCH_NAMES - {
        "prompt_local_agent.txt", "prompt_local_agent_enhanced.txt",
        "prompt_web_ai.txt", "prompt_web_ai_enhanced.txt",
        "prompt_proofread.txt", "prompt_proofread_local.txt", "prompt_proofread_web.txt",
    }
    for name in names:
        path = workspace.path / name
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed
