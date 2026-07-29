import argparse
import csv
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ANSWER_PATTERN = re.compile(r'\((\d+)\)')


def load_rows(input_path):
    suffix = input_path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required to read Excel answer files. Install pandas and openpyxl, or convert the file to CSV.") from exc

        frame = pd.read_excel(input_path, header=None)
        return frame.fillna("").astype(str).values.tolist()

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def find_header_row(rows):
    for index, row in enumerate(rows):
        normalized = [str(cell).strip() for cell in row]
        if any(cell == "שאלון" for cell in normalized) and any(cell.startswith("שאלה") for cell in normalized):
            return index, normalized
    return None, []


def parse_answer_cell(cell_value):
    text = str(cell_value).strip()

    if not text:
        return None

    if "מבוטל" in text or "והת" in text:
        return None

    match = ANSWER_PATTERN.search(text)
    if match:
        return int(match.group(1))

    if text.isdigit():
        return int(text)

    return None


def main():
    parser = argparse.ArgumentParser(description="Extract correct answers from a CSV or Excel file based on the form number.")
    parser.add_argument("csv_file", help="Path to the CSV or Excel file")
    parser.add_argument("form_num", help="Test form number (e.g. '76', '32', or '0' for Form Zero)")
    parser.add_argument("-o", "--output", help="Output JSON file", default="answers.json")
    
    args = parser.parse_args()

    input_path = Path(args.csv_file)
    if input_path.is_dir():
        candidates = list(input_path.glob("*.xlsx")) + list(input_path.glob("*.xls")) + list(input_path.glob("*.csv"))
        if candidates:
            input_path = candidates[0]

    form_str = str(args.form_num).strip().lstrip('0')
    if not form_str:
        form_str = '0'

    is_form_zero = (form_str in {'0', 'zero', '00', '000'})
    answers_map = {}

    if input_path.exists():
        try:
            rows = load_rows(input_path)
            header_row_index, headers = find_header_row(rows)

            if is_form_zero and header_row_index is not None:
                # Form Zero extraction from bracket metadata [Z] {W} across all student rows
                form0_q_pattern = re.compile(r'\[(\d+)\]')
                form0_ans_pattern = re.compile(r'\{(\d+)\}')
                for row in rows[header_row_index + 1:]:
                    for cell in row:
                        cell_str = str(cell).strip()
                        q_match = form0_q_pattern.search(cell_str)
                        ans_match = form0_ans_pattern.search(cell_str)
                        if q_match and ans_match:
                            answers_map[q_match.group(1)] = int(ans_match.group(1))

            elif header_row_index is not None:
                target_row = None
                available_forms = []
                for row in rows[header_row_index + 1:]:
                    if not row:
                        continue

                    for cell in row[:3]:
                        cell_val = str(cell).strip()
                        if cell_val.replace('.', '').isdigit():
                            val = str(int(float(cell_val))) if '.' in cell_val else cell_val
                            val = val.lstrip('0')
                            if not val:
                                val = '0'
                            if val not in available_forms and val != '0':
                                available_forms.append(val)

                    if any(str(cell).strip().lstrip('0') == form_str for cell in row[:3]):
                        target_row = row
                        break

                if target_row is None and len(available_forms) == 1:
                    target_form = available_forms[0]
                    print(f"NOTE: Form '{args.form_num}' not found in spreadsheet, but file contains a single Form '{target_form}'. Auto-selecting Form {target_form}.")
                    for row in rows[header_row_index + 1:]:
                        if any(str(cell).strip().lstrip('0') == target_form for cell in row[:3]):
                            target_row = row
                            break

                if target_row is not None:
                    for column_index, header_text in enumerate(headers):
                        if not header_text.startswith("שאלה"):
                            continue

                        q_num_match = re.search(r"\d+", header_text)
                        if not q_num_match:
                            continue

                        q_num = q_num_match.group(0)
                        if column_index >= len(target_row):
                            continue

                        parsed_answer = parse_answer_cell(target_row[column_index])
                        if parsed_answer is not None:
                            answers_map[q_num] = parsed_answer
                        elif any(token in str(target_row[column_index]) for token in ("והת", "מבוטל")):
                            answers_map[q_num] = None

                else:
                    if available_forms:
                        print(f"No answers found for form '{args.form_num}'. Available form(s) in this file: {', '.join(available_forms)}")
                    else:
                        print(f"No answers found for form '{args.form_num}'. Check if the form number exists in the file.")
                    return 1

        except Exception as e:
            print(f"Warning/Error reading answers file: {e}")

    # Fallback for Form Zero: default questions 1..50 to answer 1 (the first option)
    if is_form_zero:
        max_q = max([int(k) for k in answers_map.keys()], default=50)
        for i in range(1, max_q + 1):
            q_key = str(i)
            if q_key not in answers_map or answers_map[q_key] is None:
                answers_map[q_key] = 1

    if not answers_map:
        print(f"No answers found for form {args.form_num}. Check if the form number exists in the CSV.")
        return 1

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(answers_map.items(), key=lambda item: int(item[0]))), f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted {len(answers_map)} answers to {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
