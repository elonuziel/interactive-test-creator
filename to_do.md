The next priorities are:

## 1. Run and stabilize Playwright tests

The tests are configured but not yet executed locally. Run:

```bash
npm install
npx playwright install chromium
npm run test:browser
```

Then fix any real browser issues they expose.

## 2. Fix a likely standalone-player test issue

The current test writes into `#quiz-data` and then reloads the page. A reload will lose that dynamically inserted data because it was never persisted into the HTML document.

A better test should either:

- Generate a real standalone HTML file and navigate to it, or
- Use Playwright’s `page.setContent()` with the player HTML and embedded data.

The first option is more valuable because it tests the real export path.

## 3. Add a committed browser fixture

Create a small fixture such as:

```text
test-suite/fixtures/questions.json
```

Use it in browser tests instead of constructing test data inline. This makes tests easier to inspect and reuse.

## 4. Improve export testing

Test that exported quizzes:

- Load with no `questions.json`
- Preserve question text containing `</script>`
- Preserve Hebrew and mixed English text
- Preserve embedded images
- Start and answer correctly
- Resume after refresh

## 5. Fix `test_runner.html`

It still duplicates production helper implementations. Load `quiz-core.js` and use the shared functions there. This prevents the in-browser test runner from drifting away from the actual application.

## 6. Make Python test results accurate

Report:

```text
7 passed, 3 skipped, 0 failed
```

instead of:

```text
7/10 tests passed
```

Also make missing optional fixtures explicit.

## 7. Add a real question validation UI

The validation currently blocks operations with an error. Improve it by:

- Showing an invalid-question count
- Highlighting affected cards
- Disabling export while invalid questions exist
- Showing errors next to the relevant question

## 8. Improve CI deployment separation

The deployment workflow currently performs browser testing and deployment in one job. Split it into:

```text
test → deploy
```

so deployment only occurs if all tests pass, with clearer failure reporting.

## 9. Address accessibility

High-value fixes:

- Replace clickable `<div class="option">` elements with buttons
- Add `aria-live` to status/feedback areas
- Preserve focus after question navigation
- Add visible keyboard focus styles
- Add labels/roles for dynamically generated controls

## Best next step

The most valuable immediate task is:

> Fix the Playwright standalone-player test to use a genuinely generated exported HTML file, then run the full browser suite.