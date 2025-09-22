import { describe, it, expect } from 'vitest';
import { markdownToHtml } from '../../src/utils/markdown';

describe('markdownToHtml', () => {
  it('renders code fences safely', () => {
    const md = '```js\nalert(1)\n```';
    const html = markdownToHtml(md);
    expect(html).toContain('<pre><code');
    expect(html).toContain('&lt;'); // escaped
  });

  it('renders links', () => {
    const md = '[site](https://example.com)';
    const html = markdownToHtml(md);
    expect(html).toContain('<a href=');
  });

  it('renders tables', () => {
    const md = '| a | b |\n|---|---|\n| 1 | 2 |';
    const html = markdownToHtml(md);
    expect(html).toContain('<table');
    expect(html).toContain('<thead>');
  });
});
