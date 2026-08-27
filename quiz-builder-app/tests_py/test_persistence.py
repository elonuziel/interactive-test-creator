import json
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.persistence import write_json_atomic


def test_write_json_atomic_replaces_existing_file(tmp_path):
    output = tmp_path / "questions.json"
    output.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomic(output, [{"question": "שלום"}])

    assert json.loads(output.read_text(encoding="utf-8")) == [{"question": "שלום"}]
    assert list(tmp_path.glob(".questions.json.*.tmp")) == []
