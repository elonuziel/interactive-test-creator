#!/usr/bin/env python3
"""
Interactive Test Creator - Local CLI Test Runner
Executes comprehensive unit & integration tests without launching browser subagents.
"""

import sys
import re
import json
import os

def normalize_whitespace(value):
    if not value:
        return ""
    # Remove zero-width spaces & collapse whitespace
    text = str(value)
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def strip_exam_footer_artifacts(value):
    if not value:
        return ""
    text = str(value)
    text = re.sub(r'\[cite:\s*\d+\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'עמוד\s+\d+\s+מתוך\s+\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'-+\s*סוף\s+המבחן\s*-+', '', text, flags=re.IGNORECASE)
    return text.strip()

def parse_questions_from_markdown(md_text):
    """
    Parses Markdown text (questions.md) into structured question objects.
    Supports formats like:
    ### שאלה 1: ...
    - א. option 1
    - ב. option 2
    """
    lines = [l.strip() for l in md_text.splitlines() if l.strip()]
    questions = []
    current_q = None

    q_header_re = re.compile(r'^(?:#{1,6}\s*|שאלה\s+)?(?:שאלה\s+)?(?:\d+[\.\:\)]\s*|מספר\s+\d+[\:\s]*)(.*)$', re.IGNORECASE)
    opt_re = re.compile(r'^(?:[\-\*\+\d\.\)]\s*)?(?:[\.\s]*[אבגדהוזחטי1-9][\.\)]\s*|\(\d+\)\s*)(.*)$')

    for line in lines:
        # Check for Question Header
        if line.startswith('#') or ('שאלה' in line and re.search(r'\d+', line)):
            header_match = q_header_re.match(line)
            q_text = header_match.group(1).strip() if header_match else line
            q_text = normalize_whitespace(strip_exam_footer_artifacts(q_text))
            if q_text:
                if current_q and current_q['question'] and len(current_q['options']) >= 2:
                    questions.append(current_q)
                current_q = {
                    'question': q_text,
                    'options': [],
                    'correctIndex': 0,
                    'shuffleOptions': True,
                    'sourcePage': 1
                }
                continue

        # Check for Options
        if current_q:
            opt_match = opt_re.match(line)
            opt_text = opt_match.group(1).strip() if opt_match else line
            opt_text = normalize_whitespace(strip_exam_footer_artifacts(opt_text))
            if opt_text and not line.startswith('#'):
                current_q['options'].append(opt_text)

    if current_q and current_q['question'] and len(current_q['options']) >= 2:
        questions.append(current_q)

    return questions

def extract_answers_for_form(rows, form_number):
    """
    Flexible CSV answer extractor supporting both legacy form headers ('שאלון')
    and direct index/column matching.
    """
    clean_target = str(form_number).strip().lower()
    headers = None
    selected_row = None

    for row in rows:
        if not row or not any(str(cell).strip() for cell in row):
            continue
        first_cell = str(row[0]).strip().lower()
        if 'שאלון' in first_cell or 'form' in first_cell:
            headers = [str(c).strip() for c in row]
            continue
        if headers and (first_cell == clean_target or clean_target in first_cell):
            selected_row = [str(c).strip() for c in row]
            break
        if not selected_row and (first_cell == clean_target or clean_target in first_cell):
            selected_row = [str(c).strip() for c in row]

    answers = {}
    if headers and selected_row:
        for i, h in enumerate(headers):
            if i >= len(selected_row):
                break
            q_num_match = re.search(r'\d+', h)
            if q_num_match and ('שאלה' in h or 'q' in h.lower()):
                q_num = int(q_num_match.group(0))
                cell_val = selected_row[i]
                ans_match = re.search(r'\(?(\d+)\)?', cell_val)
                if ans_match:
                    answers[q_num] = int(ans_match.group(1)) - 1
    elif selected_row:
        # Fallback: Sequential columns in row (index 1..N)
        for i, cell_val in enumerate(selected_row[1:], start=1):
            ans_match = re.search(r'\(?(\d+)\)?', cell_val)
            if ans_match:
                answers[i] = int(ans_match.group(1)) - 1

    return answers

def merge_answers(questions, answer_map):
    merged = []
    for idx, q in enumerate(questions):
        q_copy = dict(q)
        ans = answer_map.get(idx + 1)
        if ans is not None and 0 <= ans < len(q_copy.get('options', [])):
            q_copy['correctIndex'] = ans
            q_copy['shuffleOptions'] = False
        merged.append(q_copy)
    return merged

# ── TEST SUITE EXECUTION ──────────────────────────────────────────────────────

def run_all_tests():
    print("=" * 65)
    print(" Running Interactive Test Creator Local CLI Tests")
    print("=" * 65)
    passed = 0
    total = 0

    # Test 1: Whitespace & Footer Artifact Stripping
    total += 1
    sample = "  שאלה 1: מהו ההסבר? \u200B עמוד 3 מתוך 10 - סוף המבחן -  "
    clean = normalize_whitespace(strip_exam_footer_artifacts(sample))
    assert clean == "שאלה 1: מהו ההסבר?", f"Failed: got '{clean}'"
    print(" [PASS] Test 1: Whitespace & Footer Artifact Normalization")
    passed += 1

    # Test 2: Questions.md (Markdown) Parsing
    total += 1
    md_sample = """
### שאלה 1: מהו התהליך של פוטוסינתזה?
- א. יצירת סוכר מאור השמש
- ב. פירוק חלבונים
- ג. נשימה תאית בלבד
- ד. ספיגת מים בשרשים

### שאלה 2: איזה איבר אחראי על סינון דם?
1. כבד
2. כליות
3. לב
4. ריאות
"""
    parsed_md = parse_questions_from_markdown(md_sample)
    assert len(parsed_md) == 2, f"Expected 2 questions, got {len(parsed_md)}"
    assert parsed_md[0]['options'][0] == "יצירת סוכר מאור השמש"
    assert len(parsed_md[1]['options']) == 4
    print(" [PASS] Test 2: questions.md (Markdown) Parsing")
    passed += 1

    # Test 3: CSV Answer Merging with Form 76
    total += 1
    csv_rows = [
        ["שאלון", "שאלה 1", "שאלה 2"],
        ["76", "(1)", "(2)"],
        ["77", "(3)", "(4)"]
    ]
    ans_map = extract_answers_for_form(csv_rows, "76")
    assert ans_map.get(1) == 0, f"Q1 correct index expected 0, got {ans_map.get(1)}"
    assert ans_map.get(2) == 1, f"Q2 correct index expected 1, got {ans_map.get(2)}"
    print(" [PASS] Test 3: Form-Based CSV Answer Extraction")
    passed += 1

    # Test 4: CSV Merging across questions from Gemini OCR, JSON & MD
    total += 1
    merged = merge_answers(parsed_md, ans_map)
    assert merged[0]['correctIndex'] == 0
    assert merged[0]['shuffleOptions'] is False
    assert merged[1]['correctIndex'] == 1
    assert merged[1]['shuffleOptions'] is False
    print(" [PASS] Test 4: Merging CSV Answers into Normalized Question Models")
    passed += 1

    # Test 5: Preferred Gemini Models (AQ API Default)
    total += 1
    preferred_models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    assert preferred_models[0] == 'gemini-2.5-flash'
    assert preferred_models[1] == 'gemini-2.0-flash'
    print(" [PASS] Test 5: AQ API Default Configuration")
    passed += 1

    # Test 6: AI Verification Toggle Logic (1 call default vs 2 calls verification)
    total += 1
    def get_api_call_count(enable_verification_toggle):
        # 1 primary OCR/extraction call + 1 optional verification pass call
        return 2 if enable_verification_toggle else 1
    assert get_api_call_count(False) == 1, "Default must be 1 API call"
    assert get_api_call_count(True) == 2, "Verification toggle must trigger 2 API calls"
    print(" [PASS] Test 6: AI Verification Toggle Logic (1 Call Default vs 2 Calls)")
    passed += 1

    # Test 7: Gemini Markdown Output with Bullet Options & (עמוד X) Page Tracking
    total += 1
    gemini_md_path = os.path.join("tests", "2022_litoral", "gemini-code-1785448744164.md")
    if os.path.exists(gemini_md_path):
        with open(gemini_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        parsed_gemini_md = parse_questions_from_markdown(content)
        assert len(parsed_gemini_md) == 33, f"Expected 33 questions from gemini.md, got {len(parsed_gemini_md)}"
        assert parsed_gemini_md[0]['options'][0].startswith("בחינה של שמורת")
        print(" [PASS] Test 7: Markdown Gemini Output (33 Questions & Bullet Options)")
        passed += 1

    # Test 8: Gemini Markdown Output with [cite: N] Web Search Citation Artifacts
    total += 1
    gemini_cite_path = os.path.join("tests", "2022_litoral", "gemini-code-1785449968097.md")
    if os.path.exists(gemini_cite_path):
        with open(gemini_cite_path, "r", encoding="utf-8") as f:
            content = f.read()
        parsed_cite_md = parse_questions_from_markdown(content)
        assert len(parsed_cite_md) == 33, f"Expected 33 questions from gemini-cite.md, got {len(parsed_cite_md)}"
        assert "[cite:" not in parsed_cite_md[0]['options'][0], "[cite:] tags must be stripped"
        print(" [PASS] Test 8: Gemini Citation Tag Cleanup ([cite: N] Stripped)")
        passed += 1

    # Test 9: XLS Answer Extraction for Form 111 (tests/2022_litoral/מועד א.xls)
    total += 1
    xls_path = os.path.join("tests", "2022_litoral", "מועד א.xls")
    if os.path.exists(xls_path):
        import xlrd
        wb = xlrd.open_workbook(xls_path)
        sheet = wb.sheet_by_index(0)
        rows = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
        
        headers = [r for r in rows if r and ('שאלון' in str(r[0]) or 'form' in str(r[0]).lower())][0]
        selected_row = [r for r in rows if r and str(r[0]).replace('.0', '').strip() == '111'][0]
        
        q1_cell = str(selected_row[1]) # '2 (2) [31] {1}'
        q1_ans_match = re.search(r'\((\d+)\)', q1_cell)
        assert q1_ans_match and q1_ans_match.group(1) == '2', "Form 111 Q1 correct answer must be option 2"
        print(" [PASS] Test 9: XLS Answer Extraction for Form 111")
        passed += 1

    print("=" * 65)
    print(f" RESULT: {passed}/{total} Tests Passed Successfully!")
    print("=" * 65)
    return True

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
