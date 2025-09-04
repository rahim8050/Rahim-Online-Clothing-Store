// Content script: dataeloader_312i.js
// Moved from website into Chrome Extension context (MV3).
// Keep asset resolution via chrome.runtime.getURL where needed.
(function () {
  try {
    if (!window || !document) return;

    // Example: use chrome.runtime.getURL to fetch an extension-bundled asset
    const url = (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL)
      ? chrome.runtime.getURL('assets/config.json')
      : null;

    if (url) {
      fetch(url)
        .then(r => r.ok ? r.json() : null)
        .then(cfg => {
          if (!cfg) return;
          console.debug('[Rahim Assistant] data loader config', cfg);
          // Initialize or load data based on cfg if needed.
        })
        .catch(() => {/* ignore */});
    }

    console.debug('[Rahim Assistant] dataeloader_312i content script active');
  } catch (e) {
    console.warn('[Rahim Assistant] data loader init failed', e);
  }
})();

