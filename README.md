# Interactive Hebrew Quiz & Study Guides

This repository contains a modern, interactive web-based quiz application tailored for Hebrew (RTL support) along with guides for study material processing.

## 🚀 Interactive Quiz Application

The web application (`index.html`, `app.js`, `style.css`) is a premium-designed, fully responsive, and accessible interactive quiz interface.

### Features
- **RTL & Hebrew Support**: Built from the ground up for right-to-left layout and Hebrew text.
- **Immediate Feedback Mode**: Optional toggle to check answers instantly.
- **Keyboard Navigation**:
  - `1` to `4` keys to select option answers.
  - Left (`←`) and Right (`→`) arrow keys to navigate questions.
  - `Esc` key to close image zoom.
- **Visual Progress Tracking**: Real-time progress bar and a question jump navigation bar.
- **Dynamic Question Order**: Answers are shuffled/randomized for each question run.
- **Auto-Save & Resume**: Save your progress automatically in LocalStorage to resume later if the tab is closed.
- **Rich Review Screen**: View your score and filter questions by All, Wrong Only, or Unanswered.
- **Responsive Theme**: Dark/Light mode support.

## 📚 Conversion and Extraction Guides

This repository also hosts comprehensive documentation on digitizing and extracting study materials:

1. **[LLM Runbook](LLM_RUNBOOK.md)**: The end-to-end workflow for turning Hebrew exam PDFs and answer keys into playable quiz folders.
2. **[Python Utilities](python_scripts/README.md)**: Script-by-script usage for the extraction pipeline.

## 📁 Adding New Tests & Drop Folder Workflow

To process and add tests (e.g., Test 1, Test 2, Test 3) to the interactive quiz workflow:

1. **Create a Test Directory**: Create a folder for your test under `tests/` (e.g., `tests/test_1/`, `tests/test_2/`, `tests/2022_moed_a/`).
2. **Drop Raw Input Files**: Place your raw source files directly into that test folder:
   - Exam PDF file (e.g., `tests/test_1/exam.pdf`)
   - Answer key Excel/CSV file (e.g., `tests/test_1/answers.csv` or `answers.xlsx`)
3. **Run Extraction Pipeline**: Follow the [LLM Runbook](LLM_RUNBOOK.md) to extract text/images and generate the final `questions.json` inside the test folder (alongside an optional `images/` folder).
4. **Git Protection**: The repository `.gitignore` includes `test*/`, meaning all raw test PDFs, answer key spreadsheets, and test directories created under `tests/` remain strictly local and will not be committed to GitHub.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
