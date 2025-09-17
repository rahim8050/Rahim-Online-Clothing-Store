# Changelog

## 2025-09-04 – Stop chatbot auto-open; persist content only

- Frontend assistant (Vue `ChatPanel.vue`)
  - Starts closed by default; opens only on user click.
  - Persists only messages and draft in `localStorage` under `assistant_state_v1`.
  - Does not persist open/closed state. Greeting avoids duplication across reloads.
- Legacy DOM assistant (`static/js/chatbot.js`)
  - Added `static/js/assistant-state.js` for {messages, draft} persistence.
  - Hydrates content on open; never auto-opens on page load.
  - Adds `openPanel()`/`closePanel()` helpers and prevents accidental auto-open triggers.
- Templates
  - Ensured assistant panel stays hidden by default; bubble toggle remains visible.
- Test
  - Added `tests/assistant_auto_open.spec.ts` (Playwright) to assert the panel remains closed on navigation.

Notes: No open-state is read from storage anymore. Any prior flags like `rahim_assistant_seen` are ignored for auto-opening.
