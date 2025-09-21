// Small whitelist-based HTML sanitizer for chat messages
// - Strips scripts/styles/iframes
// - Removes event handler attributes (on*) and javascript: URLs
// - Allows a safe subset of tags/attributes

const ALLOWED_TAGS = new Set([
  'p','b','strong','i','em','u','s','br','code','pre','blockquote','ul','ol','li','a','table','thead','tbody','tr','th','td','hr'
]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(['href','title','target','rel']),
  code: new Set([]),
  pre: new Set([]),
  th: new Set(['colspan','rowspan','align']),
  td: new Set(['colspan','rowspan','align']),
};

function sanitizeUrl(url: string): string {
  try {
    const u = url.trim().toLowerCase();
    if (u.startsWith('javascript:') || u.startsWith('data:')) return '#';
    return url;
  } catch {
    return '#';
  }
}

export function sanitize(html: string): string {
  const tmpl = document.createElement('template');
  tmpl.innerHTML = html;

  const walker = document.createTreeWalker(tmpl.content, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_COMMENT | NodeFilter.SHOW_TEXT);
  const toRemove: Node[] = [];

  let node: Node | null;
  while ((node = walker.nextNode())) {
    if (node.nodeType === Node.COMMENT_NODE) {
      toRemove.push(node);
      continue;
    }
    if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      const tag = el.tagName.toLowerCase();

      if (!ALLOWED_TAGS.has(tag)) {
        toRemove.push(el);
        continue;
      }

      // Remove dangerous attributes
      [...el.attributes].forEach(attr => {
        const name = attr.name.toLowerCase();
        const val = attr.value;

        if (name.startsWith('on')) {
          el.removeAttribute(attr.name);
          return;
        }
        if (name === 'style') {
          el.removeAttribute(attr.name);
          return;
        }
        // Restrict attributes by tag
        const allowed = ALLOWED_ATTRS[tag];
        if (allowed && !allowed.has(name)) {
          el.removeAttribute(attr.name);
          return;
        }
        if (tag === 'a' && name === 'href') {
          el.setAttribute('href', sanitizeUrl(val));
          el.setAttribute('rel', 'noopener noreferrer');
        }
      });
    }
  }

  toRemove.forEach(n => {
    if (n.parentNode) n.parentNode.removeChild(n);
  });

  return tmpl.innerHTML;
}

export default sanitize;
