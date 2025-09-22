// Website-safe asset URL resolver. No Chrome extension APIs.
// Idempotent and safe in any environment.
export function resolveAssetUrl(path) {
  try {
    const base = window?.location?.origin || '';
    // Allow absolute or relative paths; new URL handles both with a base.
    return new URL(path, base).href;
  } catch (_e) {
    // Fallback to given path if URL construction fails.
    return path;
  }
}
