from __future__ import annotations

import base64
import copy
import html
import json
import mimetypes
from pathlib import Path
from typing import Any, Iterable

from .markdown import load_questions
from .models import Workspace
from .paths import application_root
from .pipeline import PipelineRunner


def image_to_data_uri(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    mime = mime_type or "image/png"
    data = image_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def prepare_exam_payload(workspace: Workspace, embed_images: bool = True) -> dict[str, Any] | None:
    questions_file = workspace.questions_path
    if not questions_file.is_file():
        return None
    try:
        raw_questions = load_questions(questions_file)
    except Exception:
        return None
    if not raw_questions:
        return None

    questions: list[dict[str, Any]] = []
    for idx, q in enumerate(raw_questions, 1):
        item = copy.deepcopy(q)
        item["id"] = f"{workspace.name}::q{idx}"
        item["source_exam"] = workspace.name

        if embed_images:
            for field in ("image", "pageImage"):
                img_ref = item.get(field)
                if img_ref:
                    p = Path(img_ref)
                    if not p.is_absolute():
                        p = workspace.path / p
                    if p.is_file():
                        try:
                            item[field] = image_to_data_uri(p)
                        except Exception:
                            pass
        questions.append(item)

    import re
    name_str = workspace.name
    year_match = re.search(r"\b(20\d\d|19\d\d)\b", name_str)
    moed_match = re.search(r"[_ -]([ab]|א|ב)\b", name_str, re.IGNORECASE)

    year = getattr(workspace, "year", None) or (year_match.group(1) if year_match else "")
    variant = getattr(workspace, "variant", None) or (moed_match.group(1) if moed_match else "")
    test_number = getattr(workspace, "test_number", None) or workspace.name

    return {
        "id": workspace.name,
        "name": workspace.name,
        "test_number": test_number,
        "year": year,
        "variant": variant,
        "questionCount": len(questions),
        "questions": questions,
    }


def build_central_hub(
    root: Path,
    workspaces: Iterable[Workspace],
    output: Path | None = None,
    title: str = "מרכז המבחנים האינטראקטיבי",
) -> Path:
    """Compile a self-contained Centralized Quiz Hub embedding all exams and questions."""
    root = root.resolve()
    output_path = (output or (root / "quiz_hub.html")).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exams_data: list[dict[str, Any]] = []
    for ws in workspaces:
        exam = prepare_exam_payload(ws, embed_images=True)
        if exam:
            exams_data.append(exam)

    if not exams_data:
        raise ValueError(f"No valid questions.md found across the provided workspaces in {root}.")

    # Sort exams alphabetically or by year descending
    exams_data.sort(key=lambda x: str(x.get("name", "")))

    html_content = generate_hub_html(title=title, exams_data=exams_data)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def build_all_standalone_quizzes(
    workspaces: Iterable[Workspace],
    scripts_dir: Path | None = None,
) -> list[Path]:
    """Compile standalone quiz.html in each workspace folder that has questions.md."""
    from .exporter import build_standalone_quiz
    generated: list[Path] = []
    for ws in workspaces:
        if ws.questions_path.is_file():
            try:
                out = ws.path / "quiz.html"
                build_standalone_quiz(ws.path, scripts_dir=scripts_dir, output=out)
                generated.append(out)
            except Exception:
                continue
    return generated


def generate_hub_html(title: str, exams_data: list[dict[str, Any]]) -> str:
    exams_json = json.dumps(exams_data, ensure_ascii=False)
    safe_title = html.escape(title)

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --bg-input: #0f172a;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --primary-glow: rgba(59, 130, 246, 0.25);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.2);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.2);
            --warning: #f59e0b;
            --accent: #8b5cf6;
            --border: #334155;
            --border-subtle: #1e293b;
            --radius: 12px;
            --radius-sm: 8px;
            --radius-lg: 16px;
            --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            --font: \x27Rubik\x27, system-ui, -apple-system, sans-serif;
        }}

        [data-theme="light"] {{
            --bg-base: #f8fafc;
            --bg-card: #ffffff;
            --bg-hover: #f1f5f9;
            --bg-input: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --primary-glow: rgba(37, 99, 235, 0.15);
            --border: #e2e8f0;
            --border-subtle: #f1f5f9;
            --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--font);
        }}

        body {{
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}

        header {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}

        .logo-area {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            cursor: pointer;
        }}

        .logo-icon {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: white;
            width: 36px;
            height: 36px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            font-weight: 800;
        }}

        .logo-title {{
            font-size: 1.25rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .btn {{
            padding: 0.5rem 1rem;
            border-radius: var(--radius-sm);
            border: 1px solid transparent;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.15s ease;
            text-decoration: none;
        }}

        .btn-primary {{
            background: var(--primary);
            color: white;
        }}
        .btn-primary:hover {{
            background: var(--primary-hover);
            box-shadow: 0 0 15px var(--primary-glow);
        }}

        .btn-secondary {{
            background: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--border);
        }}
        .btn-secondary:hover {{
            background: var(--border);
        }}

        .btn-danger {{
            background: transparent;
            color: var(--danger);
            border-color: var(--danger);
        }}
        .btn-danger:hover {{
            background: var(--danger);
            color: white;
        }}

        .btn-icon {{
            padding: 0.5rem;
            width: 38px;
            height: 38px;
            justify-content: center;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
            width: 100%;
            flex: 1;
        }}

        /* STATS OVERVIEW */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            box-shadow: var(--shadow);
            position: relative;
            overflow: hidden;
        }}

        .stat-card::before {{
            content: \x27\x27;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--primary);
        }}

        .stat-card.stat-green::before {{ background: var(--success); }}
        .stat-card.stat-purple::before {{ background: var(--accent); }}
        .stat-card.stat-orange::before {{ background: var(--warning); }}

        .stat-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }}

        .stat-value {{
            font-size: 1.75rem;
            font-weight: 800;
            color: var(--text-primary);
        }}

        .stat-sub {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        /* SECTIONS */
        .hub-section {{
            margin-bottom: 2.5rem;
        }}

        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }}

        .section-title {{
            font-size: 1.35rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* MIXED PRACTICE CARD */
        .mixed-card {{
            background: linear-gradient(135deg, var(--bg-card) 60%, rgba(59, 130, 246, 0.1));
            border: 1px solid var(--primary);
            border-radius: var(--radius-lg);
            padding: 1.75rem;
            box-shadow: var(--shadow);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .config-row {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 1rem;
        }}

        .config-label {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
            min-width: 140px;
        }}

        .chips-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .chip-btn {{
            padding: 0.4rem 0.9rem;
            border-radius: 20px;
            border: 1px solid var(--border);
            background: var(--bg-base);
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .chip-btn:hover {{
            border-color: var(--primary);
            color: var(--text-primary);
        }}

        .chip-btn.active {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
            box-shadow: 0 0 10px var(--primary-glow);
        }}

        .number-input {{
            width: 70px;
            padding: 0.35rem 0.5rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--bg-base);
            color: var(--text-primary);
            font-weight: 600;
            text-align: center;
        }}

        .radio-options {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .radio-label {{
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.9rem;
            cursor: pointer;
            color: var(--text-secondary);
        }}

        .radio-label input:checked + span {{
            color: var(--text-primary);
            font-weight: 600;
        }}

        /* EXAM CARDS GRID */
        .exams-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
            gap: 1.25rem;
        }}

        .exam-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.25rem;
            box-shadow: var(--shadow);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 1rem;
            transition: transform 0.15s, border-color 0.15s;
        }}

        .exam-card:hover {{
            transform: translateY(-2px);
            border-color: var(--primary);
        }}

        .exam-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.5rem;
        }}

        .exam-name {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .badge {{
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            background: var(--bg-hover);
            color: var(--text-secondary);
        }}

        .badge-blue {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .badge-green {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .progress-bar-wrap {{
            background: var(--bg-base);
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
            margin: 0.4rem 0;
        }}

        .progress-bar-fill {{
            background: linear-gradient(90deg, var(--primary), var(--accent));
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
        }}

        /* ACTIVE QUIZ SCREEN */
        .hidden {{ display: none !important; }}

        .quiz-view {{
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }}

        .quiz-top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 0.75rem 1.25rem;
            border-radius: var(--radius);
        }}

        .jump-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 0.75rem;
            border-radius: var(--radius);
            max-height: 120px;
            overflow-y: auto;
        }}

        .jump-btn {{
            width: 32px;
            height: 32px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-base);
            color: var(--text-secondary);
            font-size: 0.8rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.1s;
        }}

        .jump-btn.current {{
            border-color: var(--primary);
            color: var(--primary);
            box-shadow: 0 0 8px var(--primary-glow);
        }}

        .jump-btn.answered-correct {{
            background: var(--success);
            color: white;
            border-color: var(--success);
        }}

        .jump-btn.answered-incorrect {{
            background: var(--danger);
            color: white;
            border-color: var(--danger);
        }}

        .jump-btn.answered-neutral {{
            background: var(--bg-hover);
            color: var(--text-primary);
        }}

        .question-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 2rem;
            box-shadow: var(--shadow);
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }}

        .q-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        .q-text {{
            font-size: 1.25rem;
            font-weight: 600;
            line-height: 1.6;
            color: var(--text-primary);
            white-space: pre-wrap;
        }}

        .q-image-container {{
            max-width: 100%;
            text-align: center;
            background: var(--bg-base);
            padding: 0.5rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
        }}

        .q-image {{
            max-width: 100%;
            max-height: 400px;
            object-fit: contain;
            border-radius: var(--radius-sm);
            cursor: zoom-in;
        }}

        .options-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .option-item {{
            background: var(--bg-base);
            border: 1.5px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem 1.25rem;
            display: flex;
            align-items: flex-start;
            gap: 0.85rem;
            cursor: pointer;
            transition: all 0.15s ease;
            user-select: none;
        }}

        .option-item:hover:not(.locked) {{
            border-color: var(--primary);
            background: var(--bg-hover);
        }}

        .option-key {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            width: 28px;
            height: 28px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
            flex-shrink: 0;
        }}

        .option-content {{
            font-size: 1.05rem;
            line-height: 1.5;
            color: var(--text-primary);
            flex: 1;
        }}

        .option-item.selected {{
            border-color: var(--primary);
            background: rgba(59, 130, 246, 0.1);
        }}

        .option-item.correct {{
            border-color: var(--success);
            background: var(--success-glow);
        }}

        .option-item.incorrect {{
            border-color: var(--danger);
            background: var(--danger-glow);
        }}

        .explanation-box {{
            background: rgba(59, 130, 246, 0.08);
            border: 1px solid rgba(59, 130, 246, 0.2);
            padding: 1.25rem;
            border-radius: var(--radius);
            line-height: 1.6;
        }}

        .quiz-actions {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
        }}

        /* SUMMARY VIEW */
        .summary-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 2.5rem;
            text-align: center;
            box-shadow: var(--shadow);
            max-width: 650px;
            margin: 2rem auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1.5rem;
        }}

        .score-circle {{
            width: 140px;
            height: 140px;
            border-radius: 50%;
            border: 8px solid var(--primary);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 2.25rem;
            font-weight: 800;
        }}

        /* MODAL */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }}

        .modal-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 2rem;
            max-width: 480px;
            width: 90%;
            box-shadow: var(--shadow);
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}
    </style>
</head>
<body>
    <header>
        <div class="logo-area" onclick="QuizHub.showHub()">
            <div class="logo-icon">Q</div>
            <div class="logo-title">{safe_title}</div>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary btn-icon" onclick="QuizHub.toggleTheme()" title="החלף ערכת נושא">🌓</button>
        </div>
    </header>

    <main class="container">
        <!-- HUB VIEW -->
        <div id="hub-view">
            <!-- STATS OVERVIEW -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">סך הכל מבחנים</div>
                    <div class="stat-value" id="stat-total-exams">0</div>
                    <div class="stat-sub">במאגר המבחנים</div>
                </div>
                <div class="stat-card stat-purple">
                    <div class="stat-label">סך הכל שאלות</div>
                    <div class="stat-value" id="stat-total-questions">0</div>
                    <div class="stat-sub">בכל המבחנים הזמינים</div>
                </div>
                <div class="stat-card stat-green">
                    <div class="stat-label">שאלות שנענו</div>
                    <div class="stat-value" id="stat-answered">0</div>
                    <div class="stat-sub" id="stat-answered-pct">0% מהמאגר</div>
                </div>
                <div class="stat-card stat-orange">
                    <div class="stat-label">דיוק והצלחה</div>
                    <div class="stat-value" id="stat-accuracy">0%</div>
                    <div class="stat-sub" id="stat-correct-count">0 תשובות נכונות</div>
                </div>
            </div>

            <!-- MIXED PRACTICE CONFIG -->
            <div class="hub-section">
                <div class="section-header">
                    <div class="section-title">🎯 תרגול מעורב ומותאם אישית</div>
                    <button class="btn btn-danger" onclick="QuizHub.promptResetMastery()">🗑️ איפוס התקדמות</button>
                </div>

                <div class="mixed-card">
                    <div class="config-row">
                        <div class="config-label">מספר שאלות:</div>
                        <div class="chips-group" id="count-chips">
                            <button class="chip-btn" data-count="10">10</button>
                            <button class="chip-btn" data-count="20">20</button>
                            <button class="chip-btn active" data-count="30">30 (מומלץ)</button>
                            <button class="chip-btn" data-count="50">50</button>
                            <button class="chip-btn" data-count="all">כל השאלות</button>
                            <div style="display:flex;align-items:center;gap:0.3rem;">
                                <input type="number" id="custom-count-input" class="number-input" min="1" max="500" placeholder="אחר">
                            </div>
                        </div>
                    </div>

                    <div class="config-row">
                        <div class="config-label">סנן שאלות:</div>
                        <div class="radio-options">
                            <label class="radio-label">
                                <input type="radio" name="practice-filter" value="all" checked>
                                <span>כל השאלות הזמינות</span>
                            </label>
                            <label class="radio-label">
                                <input type="radio" name="practice-filter" value="unanswered">
                                <span>שאלות שטרם נענו בלבד ⭐</span>
                            </label>
                            <label class="radio-label">
                                <input type="radio" name="practice-filter" value="mistakes">
                                <span>חזרה על שגיאות בלבד ⚠️</span>
                            </label>
                        </div>
                    </div>

                    <div class="config-row">
                        <div class="config-label">אפשרויות:</div>
                        <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
                            <label class="radio-label">
                                <input type="checkbox" id="shuffle-questions-check" checked>
                                <span>ערבב סדר שאלות</span>
                            </label>
                            <label class="radio-label">
                                <input type="checkbox" id="shuffle-options-check" checked>
                                <span>ערבב סדר תשובות (א-ד)</span>
                            </label>
                            <label class="radio-label">
                                <input type="checkbox" id="immediate-feedback-check" checked>
                                <span>משוב והסבר מיידי בכל שאלה</span>
                            </label>
                        </div>
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.5rem;padding-top:1rem;border-top:1px solid var(--border);">
                        <div style="color:var(--text-secondary);font-size:0.9rem;" id="mixed-pool-estimate">נבחרו 30 שאלות מתוך כל המאגר</div>
                        <button class="btn btn-primary" style="padding:0.75rem 1.75rem;font-size:1.05rem;" onclick="QuizHub.startMixedPractice()">🚀 התחל תרגול מעורב</button>
                    </div>
                </div>
            </div>

            <!-- EXAM CATALOG -->
            <div class="hub-section">
                <div class="section-header">
                    <div class="section-title">📚 מבחנים לפי שנים ומועדים</div>
                    <div style="display:flex;gap:0.5rem;">
                        <input type="text" id="exam-search" placeholder="חיפוש מבחן..." style="padding:0.4rem 0.8rem;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--bg-card);color:var(--text-primary);font-size:0.9rem;" oninput="QuizHub.filterExamsList()">
                    </div>
                </div>

                <div class="exams-grid" id="exams-grid"></div>
            </div>
        </div>

        <!-- ACTIVE QUIZ VIEW -->
        <div id="quiz-view" class="quiz-view hidden">
            <div class="quiz-top-bar">
                <button class="btn btn-secondary" onclick="QuizHub.exitQuiz()">← חזרה למרכז המבחנים</button>
                <div style="font-weight:700;color:var(--primary);" id="active-quiz-title">מבחן</div>
                <div style="display:flex;align-items:center;gap:0.75rem;">
                    <span id="quiz-timer" style="font-weight:700;font-variant-numeric:tabular-nums;">⏱️ 00:00</span>
                </div>
            </div>

            <div class="jump-bar" id="jump-bar"></div>

            <div class="question-card" id="question-card">
                <div class="q-meta">
                    <span class="badge badge-blue" id="q-source-badge">מבחן</span>
                    <span id="q-counter-badge">שאלה 1 מתוך X</span>
                </div>

                <div class="q-text" id="q-text">טוען שאלה...</div>

                <div class="q-image-container hidden" id="q-img-wrap">
                    <img class="q-image" id="q-img" src="" alt="תמונת שאלה" onclick="window.open(this.src)">
                </div>

                <div class="options-list" id="options-list"></div>

                <div class="explanation-box hidden" id="explanation-box"></div>

                <div class="quiz-actions">
                    <button class="btn btn-secondary" id="prev-q-btn" onclick="QuizHub.prevQuestion()">← לשאלה הקודמת</button>
                    <button class="btn btn-primary" id="next-q-btn" onclick="QuizHub.nextQuestion()">לשאלה הבאה →</button>
                </div>
            </div>
        </div>

        <!-- SUMMARY VIEW -->
        <div id="summary-view" class="hidden">
            <div class="summary-card">
                <h1 style="font-size:1.75rem;font-weight:800;">🎉 המבחן הושלם!</h1>
                <div class="score-circle" id="summary-score">0%</div>
                <div id="summary-details" style="color:var(--text-secondary);line-height:1.6;"></div>
                <div style="display:flex;gap:1rem;flex-wrap:wrap;justify-content:center;margin-top:1rem;">
                    <button class="btn btn-primary" onclick="QuizHub.showHub()">🏠 חזרה למרכז המבחנים</button>
                    <button class="btn btn-secondary" id="retry-mistakes-btn" onclick="QuizHub.retryCurrentMistakes()">⚠️ תרגול טעויות בלבד</button>
                </div>
            </div>
        </div>
    </main>

    <!-- RESET MODAL -->
    <div id="reset-modal" class="modal-overlay hidden">
        <div class="modal-box">
            <h2 style="font-size:1.25rem;">איפוס היסטוריית התקדמות?</h2>
            <p style="color:var(--text-secondary);font-size:0.95rem;line-height:1.5;">פעולה זו תאפס את כל התשובות שנענו, המעקב והסטטיסטיקות במכשיר זה. לא ניתן לבטל פעולה זו.</p>
            <div style="display:flex;justify-content:flex-end;gap:0.75rem;margin-top:0.5rem;">
                <button class="btn btn-secondary" onclick="QuizHub.closeResetModal()">ביטול</button>
                <button class="btn btn-danger" onclick="QuizHub.confirmResetMastery()">כן, אפס נתונים</button>
            </div>
        </div>
    </div>

    <script>
        const EXAMS_DATA = {exams_json};
        const STORAGE_KEY = "interactive_quiz_mastery_v1";

        const QuizHub = {{
            exams: EXAMS_DATA,
            mastery: {{}},
            activeSession: null,
            timerInterval: null,
            timerSeconds: 0,

            init() {{
                this.loadMastery();
                this.initTheme();
                this.renderStats();
                this.renderExamsGrid();
                this.setupChips();
                this.updateEstimate();
            }},

            loadMastery() {{
                try {{
                    const raw = localStorage.getItem(STORAGE_KEY);
                    this.mastery = raw ? JSON.parse(raw) : {{}};
                }} catch (e) {{
                    this.mastery = {{}};
                }}
            }},

            saveMastery() {{
                try {{
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.mastery));
                }} catch (e) {{}}
            }},

            initTheme() {{
                const saved = localStorage.getItem("quiz_theme") || "dark";
                document.documentElement.setAttribute("data-theme", saved);
            }},

            toggleTheme() {{
                const current = document.documentElement.getAttribute("data-theme") || "dark";
                const next = current === "dark" ? "light" : "dark";
                document.documentElement.setAttribute("data-theme", next);
                localStorage.setItem("quiz_theme", next);
            }},

            getAllQuestions() {{
                const list = [];
                for (const exam of this.exams) {{
                    for (const q of exam.questions) {{
                        list.push(q);
                    }}
                }}
                return list;
            }},

            renderStats() {{
                const totalExams = this.exams.length;
                const allQ = this.getAllQuestions();
                const totalQ = allQ.length;

                let answeredCount = 0;
                let correctCount = 0;

                for (const q of allQ) {{
                    const record = this.mastery[q.id];
                    if (record && record.answered) {{
                        answeredCount++;
                        if (record.isCorrect) correctCount++;
                    }}
                }}

                document.getElementById("stat-total-exams").textContent = totalExams;
                document.getElementById("stat-total-questions").textContent = totalQ;
                document.getElementById("stat-answered").textContent = answeredCount;
                const answeredPct = totalQ > 0 ? Math.round((answeredCount / totalQ) * 100) : 0;
                document.getElementById("stat-answered-pct").textContent = `${{answeredPct}}% מכלל השאלות`;

                const accuracy = answeredCount > 0 ? Math.round((correctCount / answeredCount) * 100) : 0;
                document.getElementById("stat-accuracy").textContent = `${{accuracy}}%`;
                document.getElementById("stat-correct-count").textContent = `${{correctCount}} מתוך ${{answeredCount}} נכונות`;
            }},

            renderExamsGrid() {{
                const grid = document.getElementById("exams-grid");
                grid.innerHTML = "";

                for (const exam of this.exams) {{
                    let answered = 0;
                    for (const q of exam.questions) {{
                        if (this.mastery[q.id] && this.mastery[q.id].answered) answered++;
                    }}
                    const pct = exam.questionCount > 0 ? Math.round((answered / exam.questionCount) * 100) : 0;

                    const card = document.createElement("div");
                    card.className = "exam-card";
                    card.dataset.name = exam.name.toLowerCase();
                    card.innerHTML = `
                        <div class="exam-header">
                            <div>
                                <div class="exam-name">${{exam.name}}</div>
                                <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">
                                    ${{exam.year || \x27\x27}} ${{exam.variant ? \x27· \x27 + exam.variant : \x27\x27}}
                                </div>
                            </div>
                            <span class="badge badge-blue">${{exam.questionCount}} שאלות</span>
                        </div>
                        <div>
                            <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-muted);">
                                <span>התקדמות</span>
                                <span>${{answered}} / ${{exam.questionCount}} (${{pct}}%)</span>
                            </div>
                            <div class="progress-bar-wrap">
                                <div class="progress-bar-fill" style="width: ${{pct}}%;"></div>
                            </div>
                        </div>
                        <button class="btn btn-secondary" style="width:100%;justify-content:center;" onclick="QuizHub.startExam(\x27${{exam.id}}\x27)">
                            התחל מבחן זה
                        </button>
                    `;
                    grid.appendChild(card);
                }}
            }},

            filterExamsList() {{
                const query = document.getElementById("exam-search").value.trim().toLowerCase();
                const cards = document.querySelectorAll(".exam-card");
                for (const card of cards) {{
                    const name = card.dataset.name || "";
                    card.style.display = name.includes(query) ? "flex" : "none";
                }}
            }},

            setupChips() {{
                const chips = document.querySelectorAll("#count-chips .chip-btn");
                const customInput = document.getElementById("custom-count-input");

                chips.forEach(chip => {{
                    chip.addEventListener("click", () => {{
                        chips.forEach(c => c.classList.remove("active"));
                        chip.classList.add("active");
                        customInput.value = "";
                        this.updateEstimate();
                    }});
                }});

                customInput.addEventListener("input", () => {{
                    if (customInput.value) {{
                        chips.forEach(c => c.classList.remove("active"));
                        this.updateEstimate();
                    }}
                }});

                document.querySelectorAll("input[name=\x27practice-filter\x27]").forEach(radio => {{
                    radio.addEventListener("change", () => this.updateEstimate());
                }});
            }},

            getSelectedCount() {{
                const custom = parseInt(document.getElementById("custom-count-input").value);
                if (!isNaN(custom) && custom > 0) return custom;
                const active = document.querySelector("#count-chips .chip-btn.active");
                if (active) {{
                    const val = active.dataset.count;
                    return val === "all" ? 99999 : parseInt(val);
                }}
                return 30;
            }},

            updateEstimate() {{
                const count = this.getSelectedCount();
                const filter = document.querySelector("input[name=\x27practice-filter\x27]:checked").value;
                const allQ = this.getAllQuestions();

                let pool = allQ;
                if (filter === "unanswered") {{
                    pool = allQ.filter(q => !this.mastery[q.id] || !this.mastery[q.id].answered);
                }} else if (filter === "mistakes") {{
                    pool = allQ.filter(q => this.mastery[q.id] && this.mastery[q.id].answered && !this.mastery[q.id].isCorrect);
                }}

                const available = pool.length;
                const actual = Math.min(count, available);
                document.getElementById("mixed-pool-estimate").textContent = 
                    `נבחרו ${{actual}} שאלות מתוך ${{available}} זמינות (${{filter === \x27unanswered\x27 ? \x27טרם נענו\x27 : (filter === \x27mistakes\x27 ? \x27שגיאות\x27 : \x27הכל\x27)}})`;
            }},

            startExam(examId) {{
                const exam = this.exams.find(e => e.id === examId);
                if (!exam) return;
                const questions = copyQuestions(exam.questions);
                if (document.getElementById("shuffle-options-check").checked) {{
                    shuffleOptionsInPlace(questions);
                }}
                this.launchQuizSession(exam.name, questions);
            }},

            startMixedPractice() {{
                const count = this.getSelectedCount();
                const filter = document.querySelector("input[name=\x27practice-filter\x27]:checked").value;
                const allQ = this.getAllQuestions();

                let pool = allQ;
                if (filter === "unanswered") {{
                    pool = allQ.filter(q => !this.mastery[q.id] || !this.mastery[q.id].answered);
                }} else if (filter === "mistakes") {{
                    pool = allQ.filter(q => this.mastery[q.id] && this.mastery[q.id].answered && !this.mastery[q.id].isCorrect);
                }}

                if (pool.length === 0) {{
                    alert(filter === "unanswered" ? "כל השאלות במאגר כבר נענו!" : "אין שגיאות קודמות לתרגול!");
                    return;
                }}

                let selected = copyQuestions(pool);
                if (document.getElementById("shuffle-questions-check").checked) {{
                    shuffleArray(selected);
                }}
                if (selected.length > count) {{
                    selected = selected.slice(0, count);
                }}
                if (document.getElementById("shuffle-options-check").checked) {{
                    shuffleOptionsInPlace(selected);
                }}

                const title = `תרגול מעורב (${{selected.length}} שאלות)`;
                this.launchQuizSession(title, selected);
            }},

            launchQuizSession(title, questions) {{
                this.activeSession = {{
                    title: title,
                    questions: questions,
                    currentIndex: 0,
                    userAnswers: {{}},
                    startTime: Date.now()
                }};

                document.getElementById("hub-view").classList.add("hidden");
                document.getElementById("summary-view").classList.add("hidden");
                document.getElementById("quiz-view").classList.remove("hidden");
                document.getElementById("active-quiz-title").textContent = title;

                this.startTimer();
                this.renderJumpBar();
                this.renderCurrentQuestion();
            }},

            startTimer() {{
                clearInterval(this.timerInterval);
                this.timerSeconds = 0;
                const el = document.getElementById("quiz-timer");
                this.timerInterval = setInterval(() => {{
                    this.timerSeconds++;
                    const m = String(Math.floor(this.timerSeconds / 60)).padStart(2, \x270\x27);
                    const s = String(this.timerSeconds % 60).padStart(2, \x270\x27);
                    el.textContent = `⏱️ ${{m}}:${{s}}`;
                }}, 1000);
            }},

            stopTimer() {{
                clearInterval(this.timerInterval);
            }},

            renderJumpBar() {{
                const bar = document.getElementById("jump-bar");
                bar.innerHTML = "";
                const total = this.activeSession.questions.length;
                for (let i = 0; i < total; i++) {{
                    const btn = document.createElement("button");
                    btn.className = "jump-btn";
                    btn.textContent = i + 1;
                    btn.onclick = () => {{
                        this.activeSession.currentIndex = i;
                        this.renderCurrentQuestion();
                    }};
                    bar.appendChild(btn);
                }}
                this.updateJumpBarState();
            }},

            updateJumpBarState() {{
                const btns = document.querySelectorAll(".jump-btn");
                btns.forEach((btn, idx) => {{
                    btn.classList.remove("current", "answered-correct", "answered-incorrect", "answered-neutral");
                    if (idx === this.activeSession.currentIndex) {{
                        btn.classList.add("current");
                    }}
                    const ans = this.activeSession.userAnswers[idx];
                    if (ans !== undefined) {{
                        const q = this.activeSession.questions[idx];
                        if (ans === q.correctIndex) btn.classList.add("answered-correct");
                        else btn.classList.add("answered-incorrect");
                    }}
                }});
            }},

            renderCurrentQuestion() {{
                const s = this.activeSession;
                const q = s.questions[s.currentIndex];
                const total = s.questions.length;

                document.getElementById("q-counter-badge").textContent = `שאלה ${{s.currentIndex + 1}} מתוך ${{total}}`;
                document.getElementById("q-source-badge").textContent = q.source_exam || "מבחן";
                document.getElementById("q-text").textContent = q.question;

                // Image handling
                const imgWrap = document.getElementById("q-img-wrap");
                const img = document.getElementById("q-img");
                const imgSrc = q.image || q.pageImage;
                if (imgSrc) {{
                    img.src = imgSrc;
                    imgWrap.classList.remove("hidden");
                }} else {{
                    imgWrap.classList.add("hidden");
                }}

                // Options list
                const optList = document.getElementById("options-list");
                optList.innerHTML = "";

                const answered = s.userAnswers[s.currentIndex] !== undefined;
                const selectedIdx = s.userAnswers[s.currentIndex];
                const immediate = document.getElementById("immediate-feedback-check").checked;

                const keys = ["א", "ב", "ג", "ד", "ה", "ו"];
                q.options.forEach((optText, optIdx) => {{
                    const item = document.createElement("div");
                    item.className = "option-item";
                    if (answered) item.classList.add("locked");

                    if (answered) {{
                        if (optIdx === q.correctIndex && immediate) item.classList.add("correct");
                        else if (optIdx === selectedIdx && optIdx !== q.correctIndex && immediate) item.classList.add("incorrect");
                        else if (optIdx === selectedIdx) item.classList.add("selected");
                    }}

                    item.innerHTML = `
                        <div class="option-key">${{keys[optIdx] || optIdx + 1}}</div>
                        <div class="option-content">${{optText}}</div>
                    `;

                    item.onclick = () => {{
                        if (s.userAnswers[s.currentIndex] !== undefined) return;
                        this.selectAnswer(s.currentIndex, optIdx);
                    }};

                    optList.appendChild(item);
                }});

                // Explanation
                const expBox = document.getElementById("explanation-box");
                if (answered && immediate && q.explanation) {{
                    expBox.textContent = `💡 הסבר: ${{q.explanation}}`;
                    expBox.classList.remove("hidden");
                }} else {{
                    expBox.classList.add("hidden");
                }}

                // Navigation buttons
                document.getElementById("prev-q-btn").disabled = (s.currentIndex === 0);
                const nextBtn = document.getElementById("next-q-btn");
                if (s.currentIndex === total - 1) {{
                    nextBtn.textContent = "סיום מבחן 🏁";
                }} else {{
                    nextBtn.textContent = "לשאלה הבאה →";
                }}

                this.updateJumpBarState();
            }},

            selectAnswer(qIndex, choiceIndex) {{
                const s = this.activeSession;
                s.userAnswers[qIndex] = choiceIndex;
                const q = s.questions[qIndex];
                const isCorrect = (choiceIndex === q.correctIndex);

                // Update localStorage mastery record
                this.mastery[q.id] = {{
                    answered: true,
                    isCorrect: isCorrect,
                    selectedIndex: choiceIndex,
                    timestamp: Date.now()
                }};
                this.saveMastery();

                this.renderCurrentQuestion();
            }},

            prevQuestion() {{
                if (this.activeSession.currentIndex > 0) {{
                    this.activeSession.currentIndex--;
                    this.renderCurrentQuestion();
                }}
            }},

            nextQuestion() {{
                const s = this.activeSession;
                if (s.currentIndex < s.questions.length - 1) {{
                    s.currentIndex++;
                    this.renderCurrentQuestion();
                }} else {{
                    this.finishQuiz();
                }}
            }},

            finishQuiz() {{
                this.stopTimer();
                const s = this.activeSession;
                const total = s.questions.length;
                let correct = 0;
                for (let i = 0; i < total; i++) {{
                    if (s.userAnswers[i] === s.questions[i].correctIndex) correct++;
                }}

                const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
                document.getElementById("quiz-view").classList.add("hidden");
                document.getElementById("summary-view").classList.remove("hidden");

                document.getElementById("summary-score").textContent = `${{pct}}%`;
                const m = String(Math.floor(this.timerSeconds / 60)).padStart(2, \x270\x27);
                const sec = String(this.timerSeconds % 60).padStart(2, \x270\x27);

                document.getElementById("summary-details").innerHTML = `
                    <p style="font-size:1.1rem;font-weight:600;color:var(--text-primary);margin-bottom:0.5rem;">
                        ענית נכון על <b>${{correct}}</b> מתוך <b>${{total}}</b> שאלות.
                    </p>
                    <p>זמן כולל: ${{m}}:${{sec}}</p>
                `;

                this.renderStats();
            }},

            retryCurrentMistakes() {{
                const s = this.activeSession;
                const mistakes = [];
                for (let i = 0; i < s.questions.length; i++) {{
                    if (s.userAnswers[i] !== s.questions[i].correctIndex) {{
                        mistakes.push(s.questions[i]);
                    }}
                }}
                if (mistakes.length === 0) {{
                    alert("כל הכבוד! ענית נכון על כל השאלות.");
                    return;
                }}
                this.launchQuizSession(`חזרה על טעויות (${{mistakes.length}} שאלות)`, copyQuestions(mistakes));
            }},

            exitQuiz() {{
                if (confirm("האם ברצונך לצאת חזרה למרכז המבחנים?")) {{
                    this.stopTimer();
                    this.showHub();
                }}
            }},

            showHub() {{
                this.stopTimer();
                document.getElementById("quiz-view").classList.add("hidden");
                document.getElementById("summary-view").classList.add("hidden");
                document.getElementById("hub-view").classList.remove("hidden");
                this.renderStats();
                this.renderExamsGrid();
                this.updateEstimate();
            }},

            promptResetMastery() {{
                document.getElementById("reset-modal").classList.remove("hidden");
            }},

            closeResetModal() {{
                document.getElementById("reset-modal").classList.add("hidden");
            }},

            confirmResetMastery() {{
                this.mastery = {{}};
                this.saveMastery();
                this.closeResetModal();
                this.renderStats();
                this.renderExamsGrid();
                this.updateEstimate();
            }}
        }};

        function copyQuestions(arr) {{
            return JSON.parse(JSON.stringify(arr));
        }}

        function shuffleArray(arr) {{
            for (let i = arr.length - 1; i > 0; i--) {{
                const j = Math.floor(Math.random() * (i + 1));
                [arr[i], arr[j]] = [arr[j], arr[i]];
            }}
        }}

        function shuffleOptionsInPlace(questions) {{
            for (const q of questions) {{
                if (!q.options || q.options.length < 2) continue;
                const correctText = q.options[q.correctIndex];
                const indexed = q.options.map((text, idx) => ({{ text, isCorrect: idx === q.correctIndex }}));
                shuffleArray(indexed);
                q.options = indexed.map(item => item.text);
                q.correctIndex = indexed.findIndex(item => item.isCorrect);
            }}
        }}

        document.addEventListener("DOMContentLoaded", () => QuizHub.init());
    </script>
</body>
</html>"""
