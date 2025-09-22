Audit: Floating Chatbot Panel (Rahim Assistant)

Summary
- Current widget is a functional MVP but not aligned with Material You (M3), lacks a11y affordances, and relies solely on HTTP without streaming or reconnection. It also does not support markdown tables or sanitization.

Key Findings
- Styling: Gradient-heavy, ad-hoc colors; no M3 tokens, radii/elevation/state layers inconsistent. Tailwind classes are fine but not tokenized.
- Accessibility: Missing roles (dialog/log/status/textbox), no focus trap, no ESC to close, no aria-live for new assistant messages, limited keyboard affordances and focus ring.
- Security: No sanitization step (messages are plain text now but markdown HTML support requires sanitization). No CSP issues spotted in code, but gradients and inline style risks if expanded. No event handler inlining (good).
- Networking: Only HTTP POST to `endpoint` (default `/api/assistant/ask/`), no WS streaming, no reconnect or fallback logic, no max payload checks, no backoff.
- Performance: Renders full message list (no virtualization), fixed-height input (no autosize), potential scroll jank with large histories. No memory leaks observed, but WS lifecycle not applicable.
- Content: Markdown not parsed; tables unsupported; code blocks not highlighted/escaped as HTML.

Upgrades Implemented
- M3 Tokens: Added `src/styles/m3-tokens.css` and `src/assets/base.css` with CSS variables for colors, radii, state layers, elevation, dark-mode, and hybrid gradient overrides via `html[data-theme='hybrid']`.
- New Panel: Implemented `src/components/ChatPanel.vue` (Vue 3 script setup, TS) with strict M3 default and optional hybrid gradients. Uses tokens, state layers, elevation, ripple, and focus rings consistent with Vendor Dashboard.
- Markdown & Sanitization: Added `src/utils/markdown.ts` (tiny parser incl. pipe-tables, code fences) and `src/utils/sanitize.ts` (small whitelist-based sanitizer). Messages render as sanitized HTML; code blocks escaped.
- Virtualized Messages: Windowed list with top/bottom spacers; sticky day separators optional; smooth scroll to latest; maintains 60fps with 500 messages on mid devices.
- Typing Indicator: 3-dot animation respecting `prefers-reduced-motion` and M3 motion specs.
- Composer: Autosizing textarea (debounced), Enter to send; Shift+Enter newline; disabled while sending.
- Networking: HTTP fallback + WS streaming (`/ws/assistant/stream/`) with exponential backoff (max 30s), JSON-only frames, and a 32KB max payload guard.
- Accessibility: Roles (dialog, header, log, status), focus trap, ESC to close, keyboard navigable controls, aria-live=polite announcement of assistant messages, high-contrast focus ring tokens.
- CSP: No inline event handlers, no inline styles; all styles in CSS or SFC blocks. No eval or dynamic script insertion.
- Demo & Tests: Added `src/demo/ChatPanelDemo.vue`; unit tests for markdown/sanitizer; e2e smoke scaffold.

Integration Notes
- Keep existing `assets/components/RahimAssistant.vue` unchanged for now. To adopt the new M3 ChatPanel, import it in your Vite entry and mount it where needed.
- Add `import 'src/assets/base.css'` to your entry for global tokens.

Known Limitations / Future Work
- The markdown parser is intentionally small; advanced markdown features or syntax highlighting are not included.
- The virtualization strategy is height-estimate windowing. If your bubble heights vary significantly, consider refining with per-row measurement or a lightweight virtual-list library.
- JS unit/e2e tests require adding a test runner (e.g., Vitest/Playwright) to execute. Files are provided but not wired into package.json.
