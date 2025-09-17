Website Mode Hardening and Orders Route Fix

Overview
- Goal: Ensure no Chrome Extension APIs execute on normal web pages, fix /orders/create/ routing, and harden button handlers to avoid fatal JS errors.

What Changed
- Added website-safe URL resolver:
  - File: static/js/utils/url.js
  - Exports resolveAssetUrl(path) which converts any path into an absolute URL on the current origin without using chrome.runtime.getURL.

- Fixed Orders create route (trailing slash):
  - File: orders/urls.py
  - path('create', ...) -> path('create/', ...)
  - Also normalized related routes to include trailing slashes for consistency.

- Hardened navbar button handlers:
  - File: static/js/vue/navbar.js
  - Wrapped event handlers in try/catch, added null checks, and made fetch flows resilient so thrown errors don’t break subsequent interactions.

Extension API Audit
- A repo-wide search found no occurrences of chrome.runtime / chrome.storage / chrome.tabs in project sources or templates (excluding node_modules). The console errors you observed (checker_312i.js, dataeloader_312i.js) are consistent with injected Chrome extension scripts, not files from this repository.
  - If these scripts are still being inserted by any template, remove them or ensure they are only loaded in an extension environment. No such inclusions were found in templates/.

Notes on Usage
- If a future script needs to convert relative/static paths to absolute origins in website mode, import resolveAssetUrl from static/js/utils/url.js.

Testing
- Hard refresh the app and verify there are no red errors in DevTools.
- Visit /orders/create/ and confirm it resolves (200/302 depending on view).
- Click the mobile menu and Add to Cart buttons; errors should not break interaction.

