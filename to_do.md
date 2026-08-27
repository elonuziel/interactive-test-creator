# Project Priorities & Status

## ✅ Completed Tasks

- [x] **2. Standalone-player test real export generation**: Uses real standalone generated HTML (`writeStandaloneQuiz()`) navigated via `file://` instead of route interception.
- [x] **3. Committed browser fixture**: Created and standardized `test-suite/fixtures/questions.json` containing Hebrew/English mix, answers, and XSS script tags.
- [x] **4. Export safety & testing**: Escapes script tag terminators (`</script>`), preserves bilingual Hebrew/English text and options.
- [x] **5. In-browser `test_runner.html` synchronization**: Loads shared functions directly from `quiz-core.js` and `quiz-export.js`, removing duplicated/commented implementations and adding test coverage for validation, custom practice selection, and export injection.
- [x] **6. Accurate Python test reporting**: Reports explicit `[SKIP]` for missing optional fixtures and outputs `RESULT: X passed, Y skipped, Z failed`.
- [x] **7. Question validation UI**: Live validation summary banner showing invalid question and error counts, per-card highlighting (`is-invalid`), live per-question error messages, and disabled export/solve buttons while errors exist.
- [x] **8. CI deployment pipeline separation**: Split `.github/workflows/deploy-pages.yml` into a two-stage `test` -> `deploy` workflow with `needs: test`.
- [x] **9. Accessibility & keyboard navigation**:
  - Options rendered as `<button class="option">` elements with accessible labels and `data-key` hints
  - `aria-live="polite"` feedback & counter announcements
  - Question text focused on question change with `tabindex="-1"`
  - High-visibility keyboard `:focus-visible` styles
  - Jump bar with `aria-label` and `aria-current="step"`

---

## 📌 Ongoing / Environment Notes

### 1. Browser-level Playwright execution in CI
- Playwright tests are configured with system dependency provisioning (`npx playwright install --with-deps chromium`) in `.github/workflows/deploy-pages.yml` and run automatically on pull requests and deployments.
- Generated test fixture files (`test-suite/fixtures/generated-quiz.html`) are ignored in `.gitignore`.