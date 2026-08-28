from __future__ import annotations

from pathlib import Path
import json

from quizbuilder.hub import build_central_hub, build_all_standalone_quizzes, prepare_exam_payload
from quizbuilder.models import Workspace
from quizbuilder.runs import assemble_run, write_run_questions
from quizbuilder.markdown import write_questions

def _make_sample_workspace(tmp_path: Path, name: str, q_count: int = 5) -> Workspace:
    ws_dir = tmp_path / name
    ws_dir.mkdir(parents=True, exist_ok=True)
    pdf = ws_dir / f"{name}.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample")
    
    questions = []
    for i in range(1, q_count + 1):
        questions.append({
            "number": i,
            "question": f"Question {i} for {name}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correctIndex": (i % 4),
            "explanation": f"Explanation for Q{i}",
        })
    q_file = ws_dir / "questions.md"
    write_questions(q_file, questions)

    return Workspace(
        name=name,
        path=ws_dir,
        source_pdf=pdf,
    )

def test_prepare_exam_payload(tmp_path):
    ws = _make_sample_workspace(tmp_path, "exam_2020_a", q_count=3)
    payload = prepare_exam_payload(ws, embed_images=False)
    assert payload is not None
    assert payload["id"] == "exam_2020_a"
    assert payload["questionCount"] == 3
    assert len(payload["questions"]) == 3
    assert payload["questions"][0]["source_exam"] == "exam_2020_a"
    assert payload["questions"][0]["id"] == "exam_2020_a::q1"

def test_build_central_hub(tmp_path):
    ws1 = _make_sample_workspace(tmp_path, "exam_2020_a", q_count=10)
    ws2 = _make_sample_workspace(tmp_path, "exam_2021_b", q_count=15)
    
    hub_path = build_central_hub(tmp_path, [ws1, ws2], output=tmp_path / "quiz_hub.html", title="Test Hub")
    assert hub_path.is_file()
    content = hub_path.read_text(encoding="utf-8")
    assert "Test Hub" in content
    assert "exam_2020_a" in content
    assert "exam_2021_b" in content
    assert "interactive_quiz_mastery_v1" in content
    assert "startMixedPractice" in content

def test_assemble_run_with_limits(tmp_path):
    ws1 = _make_sample_workspace(tmp_path, "exam_1", q_count=20)
    ws2 = _make_sample_workspace(tmp_path, "exam_2", q_count=20)

    # Mixed with limit=30
    run_30 = assemble_run([ws1, ws2], mix=True, limit=30, shuffle=True)
    assert len(run_30.questions) == 30
    assert len(run_30.sources) == 2

    # Mixed with all (no limit)
    run_all = assemble_run([ws1, ws2], mix=True, limit=None, shuffle=True)
    assert len(run_all.questions) == 40

    # Write run payload
    run_json = tmp_path / "run.json"
    write_run_questions(run_30, run_json)
    assert run_json.is_file()
    data = json.loads(run_json.read_text(encoding="utf-8"))
    assert len(data) == 30
