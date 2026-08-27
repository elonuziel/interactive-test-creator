# Freebuff Chat Option — Product/Implementation Specification

## 1. Summary

Add a branded **Freebuff** button/option to the prompt-composer area of the chat page at `https://freebuff.com/chat`.

The control should become available after a prompt has been generated successfully. Clicking it opens Freebuff Chat in a new browser tab. Add a small **“i” information control** that explains the feature through an interaction accessible by hover, keyboard focus, and click/tap.

This document is a specification only. No implementation changes are included here.

## 2. Context

- The requested destination is the hosted Freebuff chat page: `https://freebuff.com/chat`.
- The inspected repository is a Hebrew/RTL static web project with existing button conventions, light/dark theme support, keyboard focus styling, and reusable help/info controls.
- Existing local patterns include compact rounded controls, `help-btn` styling, explanatory popups, and accessible `button` elements.
- The target chat page itself is not represented in the repository, so the eventual implementation should first identify the chat page’s actual prompt-composer DOM, styling system, branding assets, and test harness.

## 3. User story

As a user who has generated a prompt in Freebuff, I want a clearly branded Freebuff option beside the prompt composer so I can open Freebuff Chat in a separate tab and continue my workflow without losing the current page.

As a user who is unfamiliar with the option, I want an “i” explainer available through hover, keyboard focus, and click/tap so I can understand the feature before using it.

## 4. Scope

### In scope

1. Add a Freebuff-branded button/option in the prompt-composer area.
2. Make the control available only after successful prompt generation with usable, non-empty prompt content.
3. Open `https://freebuff.com/chat` in a new tab when activated.
4. Add an adjacent “i” information control.
5. Support explainer discovery/activation by:
   - Mouse hover.
   - Keyboard focus.
   - Click/tap, including touch devices.
6. Match the existing chat page’s UI conventions for spacing, shape, typography, colors, theme, and button behavior.
7. Add automated browser tests for the primary interaction states.

### Out of scope

- Automatically transferring the generated prompt into Freebuff Chat.
- Encoding the prompt into a URL parameter.
- Copying the prompt to the clipboard automatically.
- Navigating away from the current page.
- Adding a user preference for same-tab versus new-tab behavior.
- Redesigning the surrounding chat composer.
- Changing prompt-generation logic itself.

## 5. Functional requirements

### FR-1: Placement

- Place the Freebuff control in or directly beside the existing prompt composer.
- It should be visually associated with the generated prompt action area rather than appearing as an unrelated global navigation item.
- The information control should be adjacent to the Freebuff control and clearly associated with it.

### FR-2: Label and branding

- Use a Freebuff icon/brand treatment plus visible text.
- The visible text should identify the action as Freebuff; preferred presentation is an icon plus the text **“Freebuff”**.
- The control should remain understandable if the icon fails to load.
- Use the page’s existing UI conventions rather than introducing an unrelated visual language.

### FR-3: Visibility and state

- Do not show the Freebuff control before prompt generation has succeeded.
- Show it only when generated prompt content is available and non-empty.
- Keep it hidden when generation fails or produces no usable prompt.
- Do not expose a misleading enabled state while generation is in progress.
- If the page has an existing generated-prompt state model, derive visibility from that state rather than duplicating generation logic.

### FR-4: Activation

- Clicking/tapping the Freebuff button must open exactly:
  - `https://freebuff.com/chat`
- Open the destination in a **new tab**.
- Preserve the current chat page and its generated prompt state.
- Use safe external-link behavior where applicable, such as `noopener`/`noreferrer` semantics if implemented through an anchor or equivalent safe window-opening behavior.
- The generated prompt must not be automatically transferred, URL-encoded, placed in query parameters, or copied to the clipboard.

### FR-5: Information explainer

- Add a compact circular **“i”** control adjacent to the Freebuff action.
- The explainer must be available through hover, keyboard focus, and click/tap.
- Hover/focus should expose a concise tooltip or equivalent explanatory surface.
- Click/tap should provide a reliable way to open or keep the explanation visible on touch devices and for users who do not use hover.
- The explanation should describe the feature’s usage benefit: Freebuff can help the user continue or refine the generated prompt/workflow.
- The explainer should not imply that the prompt is transferred automatically.
- Provide an accessible name, such as `aria-label="About Freebuff"`, and an appropriate relationship between the control and its explanatory text (`aria-describedby`, tooltip ID, or popover semantics as supported by the target stack).
- The explanation must not block normal composer operation or remain permanently open after unrelated interaction unless that matches existing page behavior.

Suggested explanatory copy:

> **Freebuff** helps you continue and refine your AI workflow in a separate chat. Clicking opens Freebuff Chat in a new tab.

The final copy may be localized to the chat page’s language, but it must preserve the meaning above and must not promise automatic prompt transfer.

## 6. Interaction and accessibility requirements

- Use a semantic `<button>` or `<a>` for the action, not a non-semantic clickable `<div>`.
- The control must be keyboard reachable in the normal tab order.
- It must have an accessible name that communicates the action, for example `Open Freebuff Chat`.
- The “i” control must be keyboard reachable and have an accessible name.
- Provide visible `:focus-visible` styling consistent with the existing page.
- Do not rely on color, hover, or the icon alone to communicate the action.
- Ensure sufficient contrast in light and dark themes if both themes exist.
- Ensure the explainer works on touch devices where hover is unavailable.
- Ensure the new-tab behavior is understandable from accessible text or the explainer; optionally include a visually-hidden “opens in a new tab” suffix if consistent with site conventions.
- Avoid focus traps. If click opens a popover, Escape and clicking outside should close it where consistent with the existing component system.
- Respect reduced-motion preferences if the tooltip/popover uses animation.

## 7. Responsive behavior

- Keep the control usable at mobile widths without overflowing the composer.
- Allow the icon and text to remain legible when the composer wraps.
- The explainer surface must remain within the viewport and avoid being clipped by overflow containers.
- On touch devices, use tap/click behavior as the primary explicit interaction; hover behavior must not be required.

## 8. Visual requirements

- Match the existing chat page’s button height, border radius, typography, spacing, and disabled/loading conventions.
- Use Freebuff branding only as a modest emphasis; do not overpower the primary prompt-generation action.
- The “i” control should be visually secondary but discoverable.
- Support the existing theme(s), including dark mode if present.
- Avoid introducing a new dependency solely for a tooltip/popover if an existing component or CSS pattern can satisfy the requirement.

## 9. Error and edge-case behavior

- Generation in progress: hide the control or keep it non-interactive according to the page’s established loading-state convention; it must not open prematurely.
- Generation failure: keep the control hidden.
- Empty/whitespace-only generated prompt: keep the control hidden.
- Prompt regenerated: update visibility based on the newest generation result; do not retain a stale enabled control after the prompt becomes invalid.
- User clears the generated prompt: hide the control.
- Repeated activation: each deliberate activation may open a new tab, subject to normal browser popup policies; do not create hidden background tabs or automatic retries.
- Popup blocking: do not silently alter the current page’s location. If the page already has a notification convention, use it to explain that the browser blocked the new tab.
- Slow generation: do not expose the action until a valid result is committed.
- Missing brand icon asset: retain the textual “Freebuff” label and accessible name.

## 10. Automated browser test requirements

Add browser-level coverage using the project’s existing browser test framework/conventions. Tests should verify:

1. **Initial state**
   - Freebuff control is not visible before a prompt is successfully generated.
2. **Successful generation state**
   - After a non-empty prompt is generated, the Freebuff control becomes visible.
3. **Invalid generation state**
   - Empty output and generation failure do not expose an enabled Freebuff action.
4. **Navigation**
   - Activating the control requests/opens `https://freebuff.com/chat` in a new tab.
   - The originating page remains available.
   - No prompt query parameter or automatic prompt transfer is introduced.
5. **Information behavior**
   - Hover exposes the explainer.
   - Keyboard focus exposes or makes the explainer available.
   - Click/tap opens the explainer on a touch-compatible interaction path.
   - Explainer text communicates the usage benefit and separate-tab behavior without claiming automatic transfer.
6. **Accessibility basics**
   - The action and “i” control have accessible names.
   - Both are keyboard reachable.
   - Focus-visible state is present according to the page’s testable conventions.
7. **Responsive/theme smoke coverage**
   - The controls remain visible and usable at the project’s supported mobile viewport.
   - Light/dark theme rendering does not make the controls unreadable, if themes are supported.

Tests should avoid depending on an actual external Freebuff network response. Intercept or observe the new-tab URL and assert the navigation intent instead.

## 11. Acceptance criteria

- [ ] A branded Freebuff icon-plus-text control exists beside the prompt composer.
- [ ] The control appears only after successful non-empty prompt generation.
- [ ] The control remains hidden for generation failures and empty output.
- [ ] Clicking/tapping opens `https://freebuff.com/chat` in a new tab.
- [ ] The current page and generated prompt remain intact.
- [ ] No automatic prompt transfer, clipboard copy, or URL parameter is used.
- [ ] An adjacent “i” control works on hover, keyboard focus, and click/tap.
- [ ] Explainer copy describes continuing/refining the workflow and does not imply automatic transfer.
- [ ] Styling matches existing chat-page conventions and supported themes.
- [ ] The controls are responsive and keyboard accessible.
- [ ] Automated browser tests cover visibility, invalid states, navigation intent, explainer interactions, and basic accessibility.

## 12. Implementation notes for the future coding task

1. Inspect the hosted chat page’s actual source/component structure before editing.
2. Reuse existing button, tooltip, popover, icon, localization, and test utilities where available.
3. Prefer an ordinary external link with `target="_blank"` and safe `rel` attributes if that fits the page architecture; otherwise use the project’s established navigation helper.
4. Keep prompt state and Freebuff visibility derived from the existing successful-generation state.
5. Do not add prompt handoff behavior unless the product requirement is explicitly changed later.
6. If the hosted chat UI lives in a different repository, move this spec into that repository before implementation or link to it from the relevant issue.
