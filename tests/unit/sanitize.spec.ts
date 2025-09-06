import { describe, it, expect } from 'vitest';
import { sanitize } from '../../src/utils/sanitize';

describe('sanitize', () => {
  it('removes scripts and events', () => {
    const dirty = '<p onclick="alert(1)">hi<script>alert(2)</script></p>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<p>hi</p>');
    expect(clean).not.toContain('onclick');
    expect(clean).not.toContain('<script');
  });

  it('drops javascript href', () => {
    const dirty = '<a href="javascript:alert(1)">x</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('href="#"');
  });
});

