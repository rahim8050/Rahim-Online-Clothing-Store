Test Plan: M3 ChatPanel

Scope
- Validates accessibility, CSP, performance, streaming fallback, theming, and markdown table rendering.

Manual Checks
- Theming
  - Strict default: Ensure no `data-theme` attribute on `<html>`. Panel uses solid tonal M3 app bar and FAB; radii, spacing, and elevation consistent.
  - Hybrid: Set `<html data-theme="hybrid">`. Verify gradient app bar and FAB appear. Spacing and radii unchanged. Remove attribute restores strict look.
  - Dark: Toggle `document.documentElement.classList.add('dark')`. Verify contrast remains AA+ for text on surfaces and primary containers.

- Accessibility
  - Keyboard: Tab to launcher, press Enter to open. Focus moves into dialog. Shift+Tab cycles within panel; ESC closes.
  - Roles: Dialog has role="dialog" and aria-modal. Messages container role="log" updates and aria-busy when sending. Typing indicator announced via aria-live=polite region (assistant messages announce on arrival).
  - Focus ring: Buttons and textarea show visible focus rings (box-shadow var(--m3-focus)).
  - Screen readers: New assistant messages are appended and announced politely.

- CSP
  - Ensure no inline event handlers in SFC templates. All styling in CSS/SFC, no inline style attributes; build produces external JS/CSS. Nonce is not required due to external assets.

- Networking
  - WS streaming: With Channels running, connect to `/ws/assistant/stream/`. Send a message. Verify receipt of `assistant_delta` fragments and a final `assistant_message`. If WS is unavailable, HTTP fallback to `/apis/assistant/reply/` responds and UI displays assistant reply.
  - Backoff: Kill WS server mid-session; observe reconnect attempts with exponential backoff up to 30s.
  - Payload guard: Send malformed or oversized (>32KB) frames; client ignores them without crashing.

- Performance
  - Populate with 500 mixed messages. Scroll up/down quickly: rendering stays smooth (~60fps). Opening/closing panel 5 times does not increase memory materially (no retained WS listeners).
  - Autosize: Hold Enter with Shift to add newlines. Textarea grows up to 160px and remains responsive.

- Markdown & Tables
  - Paste a message with a pipe table; verify borders, zebra striping, and horizontal overflow if narrow.
  - Code fences render with proper escaping and no execution.

Automation (Optional)
- Unit tests (Vitest): `tests/unit/markdown.spec.ts` and `tests/unit/sanitize.spec.ts` validate parser and sanitizer basics.
- E2E (Playwright): `tests/e2e/chatpanel.spec.ts` is a smoke spec. Requires adding Playwright to devDependencies and a test runner script.

Acceptance Criteria Trace
- A11Y: Verified roles, focus trap, ESC, keyboard reachability, aria-live announcements, and visible focus rings.
- CSP: No inline event handlers/styles. All assets external.
- Perf: Virtualization preserves smoothness at 500 messages. No leaks after repeated open/close.
- Tables: Markdown pipe tables rendered with proper borders and zebra striping.
- WS Fallback: Streaming preferred, HTTP fallback functional, reconnection backoff capped at 30s.
- Theme: Hybrid toggles only gradients/shadows; radii/spacing/tokens consistent.
- Dark mode: `.dark` class switches tokens while maintaining AA+ contrast.
