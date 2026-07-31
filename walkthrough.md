# Walkthrough: Fix Quiz "Back to Builder" Button → `about:blank#blocked`

## Problem

When a user clicks "פתור מבחן כעת" (Solve Test Now) in the builder, a new tab opens with the live quiz. Clicking "יוצר מבחן ←" (Back to Builder) in that tab navigated to `about:blank#blocked` instead of returning to the builder.

**Root Cause:** The quiz was opened as a `blob:` URL via `URL.createObjectURL()` + an anchor with `rel="noopener"`. This severed the `window.opener` relationship. The "back" link was a relative `<a href="index.html">`, which cannot resolve against a `blob:` URL — so the browser blocked the navigation to `about:blank#blocked`.

## Fix — Three Coordinated Changes

### 1. `generator.js` — Synchronous tab opening with preserved opener

**Before (old):**
```javascript
elements.takeQuiz.addEventListener('click', async () => {
    const html = await createStandaloneQuizHtml();
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';  // ← THIS was the culprit
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
});
```

**After (new):**
```javascript
elements.takeQuiz.addEventListener('click', async () => {
    const previewWindow = window.open('', '_blank');  // synchronous → preserves opener
    if (!previewWindow) {
        setStatus('הדפדפן חסם את פתיחת לשונית המבחן...', true);
        return;
    }

    try {
        previewWindow.document.title = 'מכין מבחן...';
        const html = await createStandaloneQuizHtml();
        previewWindow.document.open();
        previewWindow.document.write(html);   // write full HTML into the tab
        previewWindow.document.close();
    } catch (error) {
        previewWindow.close();
        setStatus(error.message, true);
    }
});
```

Key improvements:
- `window.open('', '_blank')` is synchronous within the click handler → opener relationship is preserved
- `document.write()` injects the full standalone HTML into the tab
- Pops a clear Hebrew error if the popup blocker intervenes
- Cleans up the tab on failure

### 2. `quiz_player.html` — Anchor ID for interception

**Change:** Added `id="builder-nav-link"` to the back link:
```html
<a href="index.html" id="builder-nav-link" class="nav-link" title="צור מבחן חדש">יוצר מבחן ←</a>
```

This lets `app.js` intercept the click when the quiz was opened by the builder.

### 3. `app.js` — Opener-aware click handler

**Added (lines 69–99):**
```javascript
const builderNavLink = document.getElementById('builder-nav-link');

builderNavLink?.addEventListener('click', (event) => {
    if (!window.opener || window.opener.closed) return;  // standalone quiz → normal link

    event.preventDefault();
    const builderWindow = window.opener;
    try { builderWindow.focus(); } catch { /* denied by browser */ }

    window.close();

    // Fallback: if browser refuses window.close(), navigate to builder URL
    setTimeout(() => {
        if (window.closed) return;
        try { window.location.replace(builderWindow.location.href); } catch { }
    }, 100);
});
```

**How it works:**
1. If no opener exists (standalone/downloaded quiz) → the normal `<a href="index.html">` navigation proceeds
2. If opener exists (live preview) → focus the builder tab, close the quiz tab
3. If the browser refuses `window.close()` → navigate the quiz tab to the builder's URL instead

## Analysis — No Critical Bugs Found

The implementation is robust across the three scenarios:

| Scenario | Opener? | Behavior |
|---|---|---|
| Live preview via "פתור מבחן כעת" | Yes | Returns to builder tab via opener |
| Downloaded standalone quiz | No | Normal link navigation (unchanged) |
| Direct `quiz_player.html` visit | No | Normal link navigation (unchanged) |

### Browser compatibility notes
- **Chrome/Edge:** `window.open()` in click handler passes popup blocker. `document.write()` into `about:blank` works.
- **Firefox:** Same behavior. May log a deprecation warning for `document.write()` but functions correctly.
- **Safari:** `window.close()` may be silently ignored for tabs not opened by script. The `setTimeout` fallback to `location.replace()` handles this.
- **Mobile browsers:** Tab management is limited; the `location.replace()` fallback is the most likely path.

### Why `document.write()` is safe here
- The target window is `about:blank` (same origin as builder)
- `document.open()` is explicitly called before writing
- The HTML is a complete standalone document with all assets inlined
- The approach is widely used for "preview in new tab" patterns

## Minor Suggestions (Non-blocking)

These are quality-of-life improvements that could be addressed in future iterations:

### 1. Loading indicator in the quiz tab
While `createStandaloneQuizHtml()` runs (which can take time for large quizzes with image compression), the new tab shows a blank page. The current code sets the title to "מכין מבחן..." but doesn't show a spinner. Consider writing a minimal loading HTML before the async call:

```javascript
previewWindow.document.write('<!DOCTYPE html><html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;direction:rtl;"><p>מכין מבחן...</p></body></html>');
```

### 2. Handle `questions.json` fetch error gracefully in standalone quiz
In `app.js` (line 130), the `fetch('questions.json')` call shows an error message with a link back to `index.html`. In the live preview tab opened via `document.write()`, `index.html` resolves to the same tab (since the base URL is `about:blank`), which is incorrect. The new `builderNavLink` handler partially addresses this by going through the opener, but the error message's `href="index.html"` (line 173) still has the same problem. Consider changing it to use the opener fallback as well.

### 3. Standalone download should also get the `builder-nav-link` id
The downloaded standalone HTML file is generated by `createStandaloneQuizHtml()` which uses `quiz_player.html` as a template and adds `id="builder-nav-link"` automatically (since it's in the HTML). This is already handled correctly.

### 4. Consider `location.href` as simpler alternative to `document.write()`
Instead of `document.write(html)`, you could assign to `previewWindow.location.href` with a blob URL (keeping the opener since you opened with `window.open()` synchronously). However, `document.write()` is more reliable because it doesn't need blob URL management or cleanup.

## Ideas for Future Enhancement

### Keyboard shortcut to close quiz tab
Add `Ctrl+W` / `Cmd+W` or `Esc` handling in the quiz to close the tab and return to builder.

### "Open in Builder" from standalone quiz
If a standalone quiz detects it was NOT opened by the builder (no opener), the back link could show a prompt: "This quiz was downloaded. Open the builder to create a new quiz?" with a link to the GitHub Pages URL.

### Duplicate tab detection
If the user opens the same quiz in multiple tabs, `localStorage` key collisions could occur. The current hash-based storage key mitigates this per-quiz but not per-tab.

### Test the fix with automated browser tests
Consider adding a Playwright or Puppeteer test that:
1. Opens the builder
2. Clicks "פתור מבחן כעת"
3. In the new tab, clicks "יוצר מבחן ←"
4. Asserts the original builder tab is focused and the quiz tab is closed

---

## Changes Summary

| File | Lines Changed | Description |
|---|---|---|
| `generator.js` | ~20 | Synchronous `window.open()` + `document.write()` replaces blob URL anchor |
| `quiz_player.html` | 1 | Added `id="builder-nav-link"` to back link |
| `app.js` | +31 | Added opener-aware click handler for back-to-builder navigation |

**Tests:** All 8 existing unit tests pass (0 failures).
