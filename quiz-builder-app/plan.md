# GUI App — Bug Fixes, Stability & Polish

This plan covers every improvement identified after a full read of
`app.py`, `question_editor.py`, and `styles.py`.  
**Priority order: bugs/stability → UX flow → visual polish.**

---

## Proposed Changes

### 🐛 Bug Fixes (stability first)

#### [MODIFY] [app.py](file:///home/elonu/GitHub/interactive-test-creator/quiz-builder-app/src/quizbuilder/gui/app.py)

**Bug 1 — Fragile theme-button injection (line 99)**  
`self.layout().itemAt(0).widget().layout().addWidget(self.theme_button)` is
a raw index hack. If `_build_ui` order ever changes, this crashes.  
**Fix:** Add `self.theme_button` directly inside `_build_ui` as part of the
top-bar layout (alongside the existing choose/reload buttons).

**Bug 2 — Answer Matrix radio-button duplication (lines 985-1010)**  
The loop builds a `QButtonGroup` with radios, then throws it away and
builds *another* set of radios for the table cells. The orphaned
`QButtonGroup` leaks and the toggled signals fire twice.  
**Fix:** Remove the dead `btn_widget` / `btn_group` block; keep only the
per-column radio approach.

**Bug 3 — `select_all` uses a boolean argument but is called with no argument (lines 1264-1281)**  
`btn_select_all.clicked.connect(lambda: select_all(True))` is fine, but  
`btn_deselect_all.clicked.connect(lambda: select_all(False))` shadows the
`checked` parameter — the lambda captures the Qt "checked" signal arg and
passes it as `checked`, so deselect sometimes passes `True` if the button is
toggle-checked. Lambda needs explicit disambiguation.  
**Fix:** Use named lambdas with explicit values:  
`lambda _checked=None: select_all(True/False)`.

**Bug 4 — `save_test` shows a success dialog even when nothing changed**  
`save_test(show_message=True)` always pops `QMessageBox.information`. After
a successful auto-navigate (`next_export_button`), calling `save_active_question`
first then navigating is fine, but the save triggered via Ctrl+S when nothing
is dirty shows the "Changes saved." dialog unnecessarily.  
**Fix:** Only show the "Saved" dialog when `self.state["dirty"]` was True at
the start of the call.

---

### 🔄 UX Flow Improvements

#### [MODIFY] [app.py](file:///home/elonu/GitHub/interactive-test-creator/quiz-builder-app/src/quizbuilder/gui/app.py)

**UX 1 — Tab labels show live counts**  
Tab labels will update dynamically:
- `"Review questions (42)"` — question count
- `"Play or export (3 ready)"` — count of play_list items checked  
This gives instant context without switching tabs.

**UX 2 — Recent folders list (last 5 roots)**  
Add a `QMenu` on the "Choose exam folder..." button (or a small dropdown next
to it) listing the 5 most-recently opened roots, persisted in `QSettings`. 
One click opens a past root instantly — huge time saver.

**UX 3 — Worker progress: disable UI during operations & show spinner**  
Currently, buttons stay enabled during extraction/AI runs and a user can
double-trigger. Add a lightweight in-status-bar animated ellipsis (`…`)
or a `QProgressBar` in the status bar (indeterminate mode) while any
worker is active. Re-enable UI when the worker finishes or fails.

**UX 4 — Drag-and-drop reorder questions**  
Enable `QListWidget.DragDropMode.InternalMove` on `question_list`.
Handle the `model().rowsMoved` signal to sync reordering back to
`self.state["questions"]`. This replaces the clunky Up/Down buttons
(keep them as keyboard fallback, but drag is far faster).

**UX 5 — Question count badge on Review tab title**  
Auto-update `self.tabs.setTabText(1, f"Review questions ({total})")` 
whenever `refresh_question_list` runs.

**UX 6 — Auto-navigate to Review tab after successful extraction**  
When `process_selected_exam` finishes successfully (and questions were
found), automatically switch to tab index 1 after a 1-second delay. 
Teachers will no longer wonder "did it work? where did it go?"

**UX 7 — Keyboard navigation in question list**  
The `QListWidget` already responds to arrow keys, but `Alt+Up/Down` is  
bound to move_question — document this in a tooltip on the Up/Down buttons.  
Also add `Delete` key shortcut to delete the selected question (with confirm).

---

### 🎨 Visual Polish

#### [MODIFY] [styles.py](file:///home/elonu/GitHub/interactive-test-creator/quiz-builder-app/src/quizbuilder/gui/styles.py)

**Polish 1 — Primary action button style**  
Right now every button looks the same. Add an `QPushButton#primary` style
so key CTAs ("Extract questions from PDF", "Play quiz in browser",
"Save questions.md", "Start Super Batch") visually stand out with a blue
filled background in both themes.

**Polish 2 — Status bar as proper status strip**  
Style the status bar with a subtle left-colored border that changes
color: green for success, amber for in-progress, red for errors.
Achieved by setting `objectName` on the status label and adding
`QLabel#statusSuccess`, `QLabel#statusError`, `QLabel#statusBusy` styles.

**Polish 3 — Welcome dialog redesign**  
Replace the plain-text welcome with numbered steps that use bold headings
and emoji icons per step. Add a "Don't show again" checkbox (already exists
via `welcome_shown` setting — just expose it in the dialog).

#### [MODIFY] [app.py](file:///home/elonu/GitHub/interactive-test-creator/quiz-builder-app/src/quizbuilder/gui/app.py)

**Polish 4 — Mark primary buttons by name**  
Call `setObjectName("primary")` on the main action buttons so the stylesheet
rule applies automatically without changing logic.

**Polish 5 — Window title includes current exam name**  
`"Interactive Quiz Builder — ExamFolderName"` when an exam is selected.
This helps teachers who have multiple instances open.

---

## Verification Plan

### Automated Tests
```bash
cd /home/elonu/GitHub/interactive-test-creator/quiz-builder-app
python -m pytest tests_py/test_gui_offscreen.py -v
```
The existing offscreen GUI tests will catch any import or init breakage.

### Manual Verification
1. Launch `python gui_entry.py`, verify top-bar has theme toggle (not injected as afterthought).
2. Open a folder → select an exam → run extraction → confirm auto-navigate to Review tab.
3. Drag to reorder a question; verify the order persists after save.
4. Open Answer Matrix → confirm no duplicate radio events in console logs.
5. Ctrl+S with no changes → confirm no spurious "Saved" dialog.
6. Verify recent folders dropdown populates after opening 2 different roots.
7. Check tab label updates to `"Review questions (N)"` as questions load.
