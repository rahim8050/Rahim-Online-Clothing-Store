Rahim Assistant Chrome Extension (MV3)

Overview
- This extension moves checker_312i.js and dataeloader_312i.js out of Django templates and into a proper Chrome Extension as content scripts. It ensures website pages never call Chrome Extension APIs directly.

Load Unpacked
1) Open Chrome and navigate to chrome://extensions
2) Toggle "Developer mode" (top-right)
3) Click "Load unpacked" and select this directory:
   extensions/rahim-assistant/
4) Visit http://127.0.0.1:8001/ (or http://localhost:8001/) and hard-refresh.
5) Open DevTools console to confirm logs from checker_312i.js and dataeloader_312i.js.

Notes
- Content scripts are configured in manifest.json to match the local dev origins.
- Any extension-bundled assets should be placed under assets/ and accessed via chrome.runtime.getURL('assets/...').
- The site runs normally without the extension enabled; no templates include these scripts directly.

