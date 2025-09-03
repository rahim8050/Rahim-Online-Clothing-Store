// Tiny markdown -> HTML with support for code fences, inline code, basic lists,
// paragraphs, links, emphasis, headings (h1-h3 simplified), and pipe tables.
// Keep small and predictable for CSP and performance. Pair with sanitize().

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function parseInline(md: string): string {
  // inline code
  let out = md.replace(/`([^`]+)`/g, (_, code) => `<code>${escapeHtml(code)}</code>`);
  // bold
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // italics
  out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // links [text](url)
  out = out.replace(/\[([^\]]+)\]\(([^\)]+)\)/g, (_, txt, url) => `<a href="${escapeHtml(url)}">${escapeHtml(txt)}</a>`);
  return out;
}

function isDividerRow(row: string): boolean {
  // Match table divider like: |---|:---:|---|
  const cells = row.trim().split('|').filter(Boolean);
  if (!cells.length) return false;
  return cells.every(c => /^\s*:?-{3,}:?\s*$/.test(c));
}

function parseTable(lines: string[], i: number): { html: string; next: number } | null {
  // Detect a table starting at i using pipe syntax
  const head = lines[i];
  const next = lines[i+1];
  if (!head || !next) return null;
  if (head.indexOf('|') === -1) return null;
  if (!isDividerRow(next)) return null;

  const headers = head.trim().split('|').filter(Boolean).map(h => h.trim());
  const alignSpec = next.trim().split('|').filter(Boolean).map(c => c.trim());
  const aligns = alignSpec.map(spec => {
    const left = spec.startsWith(':');
    const right = spec.endsWith(':');
    return left && right ? 'center' : right ? 'right' : 'left';
  });

  let j = i + 2;
  const rows: string[][] = [];
  for (; j < lines.length; j++) {
    const line = lines[j];
    if (!line || line.trim() === '' || line.indexOf('|') === -1) break;
    const cells = line.split('|').filter(Boolean).map(c => c.trim());
    if (cells.length) rows.push(cells);
  }

  const thead = `<thead><tr>${headers.map((h,k) => `<th align="${aligns[k] || 'left'}">${parseInline(escapeHtml(h))}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${rows.map(r => `<tr>${r.map((c,k) => `<td align="${aligns[k] || 'left'}">${parseInline(escapeHtml(c))}</td>`).join('')}</tr>`).join('')}</tbody>`;
  const html = `<table class="assistant-table">${thead}${tbody}</table>`;
  return { html, next: j };
}

export function markdownToHtml(md: string): string {
  if (!md) return '';
  // Normalize newlines
  const src = md.replace(/\r\n?/g, '\n');
  const lines = src.split('\n');
  const out: string[] = [];

  let i = 0;
  while (i < lines.length) {
    let line = lines[i];
    if (!line) { i++; continue; }

    // Code fence block
    if (/^```/.test(line)) {
      const fence = line.slice(3).trim().toLowerCase();
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
      // skip closing fence
      if (i < lines.length && /^```/.test(lines[i])) i++;
      out.push(`<pre><code data-lang="${escapeHtml(fence)}">${escapeHtml(code.join('\n'))}</code></pre>`);
      continue;
    }

    // Headings (#, ##, ### only)
    const h = /^(#{1,3})\s+(.+)$/.exec(line);
    if (h) {
      const level = h[1].length;
      out.push(`<h${level}>${parseInline(escapeHtml(h[2]))}</h${level}>`);
      i++; continue;
    }

    // Lists
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        const item = lines[i].replace(/^\s*[-*+]\s+/, '');
        items.push(`<li>${parseInline(escapeHtml(item))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join('')}</ul>`);
      continue;
    }

    // Table
    const table = parseTable(lines, i);
    if (table) {
      out.push(table.html);
      i = table.next;
      continue;
    }

    // Paragraph
    out.push(`<p>${parseInline(escapeHtml(line))}</p>`);
    i++;
  }

  return out.join('\n');
}

export default markdownToHtml;

