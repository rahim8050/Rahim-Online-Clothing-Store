// Content script: checker_312i.js
// Moved from website into Chrome Extension context (MV3).
// This file runs on pages matched by manifest.json and may use chrome.runtime APIs.
(function () {
  try {
    // Guard: only run in extension-supported pages
    if (!window || !document) return;

    // Example: resolve an internal asset URL and fetch it to validate WAR config
    const assetUrl = (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL)
      ? chrome.runtime.getURL('assets/config.json')
      : null;

    if (assetUrl) {
      fetch(assetUrl)
        .then(r => r.ok ? r.json() : null)
        .then(j => {
          if (j) {
            console.debug('[Rahim Assistant] checker loaded asset', j);
          }
        })
        .catch(() => {/* ignore */});
    }

    // Place any DOM inspection or page-check logic here as needed.
    console.debug('[Rahim Assistant] checker_312i content script active');
  } catch (e) {
    // Never throw in content scripts; log and continue
    console.warn('[Rahim Assistant] checker init failed', e);
  }
})();
