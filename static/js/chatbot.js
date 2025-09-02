(() => {
  const root = document.getElementById('rahim-assistant');
  if (!root) return;

  const panel = document.getElementById('assistant-panel');
  const toggle = document.getElementById('assistant-toggle');
  const closeBtn = document.getElementById('assistant-close');
  const input = document.getElementById('assistant-input');
  const send = document.getElementById('assistant-send');
  const feed = document.getElementById('assistant-messages');
  const welcome = document.getElementById('assistant-welcome');
  const suggestions = document.getElementById('assistant-suggestions');
  const topicsBtn = document.getElementById('assistant-topics');

  /* ---------- session key ---------- */
  function genKey(){
    const k = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    try { sessionStorage.setItem('assistant_key', k); } catch {}
    return k;
  }
  function getKey(){
    try { return sessionStorage.getItem('assistant_key') || genKey(); } catch { return genKey(); }
  }
  const SESSION_KEY = getKey();

  /* ---------- helpers: bubbles ---------- */
  function bubbleText(text, who='bot'){
    const row = document.createElement('div');
    row.className = who === 'me' ? 'text-right' : 'text-left';

    const b = document.createElement('div');
    b.className = (who === 'me')
      ? 'inline-block rounded-lg px-3 py-2 bg-blue-600 text-white'
      : 'inline-block rounded-lg px-3 py-2 bg-gray-100 text-gray-900';
    b.textContent = text;

    row.appendChild(b);
    feed.appendChild(row);
    feed.scrollTop = feed.scrollHeight;
  }

  function bubbleTyping(on=true){
    let node = feed.querySelector('.typing-row');
    if (on) {
      if (node) return;
      node = document.createElement('div');
      node.className = 'text-left typing-row';
      const b = document.createElement('div');
      b.className = 'inline-block rounded-lg px-3 py-2 bg-gray-100 text-gray-900';
      b.innerHTML = '<span class="inline-block w-2 h-2 rounded-full bg-gray-500 opacity-60 mr-1 animate-pulse"></span>'
                  + '<span class="inline-block w-2 h-2 rounded-full bg-gray-500 opacity-60 mr-1 animate-pulse" style="animation-delay:.15s"></span>'
                  + '<span class="inline-block w-2 h-2 rounded-full bg-gray-500 opacity-60 animate-pulse" style="animation-delay:.3s"></span>';
      node.appendChild(b);
      feed.appendChild(node);
      feed.scrollTop = feed.scrollHeight;
    } else if (node) {
      node.remove();
    }
  }

  function bubbleTable(columns, rows){
    const row = document.createElement('div');
    row.className = 'text-left';
    const wrap = document.createElement('div');
    wrap.className = 'inline-block bubble-table'; // styled by CSS above

    const table = document.createElement('table');
    table.className = 'assistant-table';

    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    (columns || []).forEach(c => {
      const th = document.createElement('th');
      th.className = 'th';
      th.textContent = c;
      trh.appendChild(th);
    });
    thead.appendChild(trh);

    const tbody = document.createElement('tbody');
    (rows || []).forEach(r => {
      const tr = document.createElement('tr');
      (columns || []).forEach(c => {
        const td = document.createElement('td');
        td.className = 'td';
        td.textContent = r[c] ?? '';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
    row.appendChild(wrap);
    feed.appendChild(row);
    feed.scrollTop = feed.scrollHeight;
  }

  /* ---------- parser for your current text ---------- */
  function parseRecentOrders(text){
    // normalize & split
    const lines = (text || '')
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(Boolean);

    if (!lines.length) return null;

    // Find start (line that begins with 'Recent orders')
    let i = lines.findIndex(l => /^recent orders?/i.test(l));
    if (i === -1) i = 0; // allow responses without the header

    const dataLines = lines.slice(i + (lines[i] && /^recent orders?/i.test(lines[i]) ? 1 : 0));
    const rows = [];

    for (const line of dataLines) {
      // Remove possible device fragments like "([iphone]:24)" etc.
      const cleaned = line.replace(/\(\[[^\]]+\]:?\d*\)/ig, '').trim();

      // Match "56: RAH56 — PENDING" or "56: RAH56 - PENDING"
      const m = cleaned.match(/^\s*(\d+)\s*:\s*([A-Z0-9-]+)\s*[—-]\s*([A-Z _]+)\s*$/i);
      if (m) {
        rows.push({
          'ID': m[1],
          'Code': m[2],
          'Status': m[3].replace(/_/g,' ').toUpperCase()
        });
      }
    }

    if (!rows.length) return null;
    return { columns: ['ID','Code','Status'], rows };
  }

  /* ---------- toggle ---------- */
  function togglePanel(){ panel.classList.toggle('hidden'); }
  toggle?.addEventListener('click', togglePanel);
  closeBtn?.addEventListener('click', togglePanel);

  /* ---------- suggestions ---------- */
  suggestions?.addEventListener('click', (e)=>{
    const btn = e.target.closest('button.chip');
    if (!btn) return;
    input.value = btn.textContent.trim();
    ask();
  });
  topicsBtn?.addEventListener('click', ()=>{
    // rotate some extras
    const extra = [
      'Show my last 3 orders',
      'Driver ETA for current delivery',
      'Explain a failed payment',
      'How do refunds work?'
    ];
    suggestions.innerHTML = '';
    for (const t of extra) {
      const b=document.createElement('button'); b.className='chip'; b.textContent=t;
      suggestions.appendChild(b);
    }
  });

  /* ---------- CSRF ---------- */
  function getCookie(name) {
    try {
      return document.cookie.split('; ').find(r=>r.startsWith(name+'='))?.split('=')[1] || '';
    } catch { return ''; }
  }
  const CSRF = (window.CSRF_TOKEN || getCookie('csrftoken') || '');

  /* ---------- send/ask ---------- */
  let pending = false;
  async function ask(){
    const msg = (input.value || '').trim();
    if (!msg || pending) return;

    welcome?.classList.add('hidden');      // hide welcome on first message
    bubbleText(msg, 'me');
    input.value = '';
    pending = true; send.disabled = true;
    bubbleTyping(true);

    try {
      const r = await fetch('/api/assistant/ask/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
        credentials: 'same-origin',
        body: JSON.stringify({ session_key: SESSION_KEY, message: msg })
      });

      bubbleTyping(false);

      // try to read JSON always (your API returns JSON)
      let j = {};
      try { j = await r.json(); } catch {}

      if (!r.ok) throw new Error('HTTP ' + r.status);

      // 1) server-driven table?
      if (j && j.reply_type === 'table' && Array.isArray(j.rows)) {
        const cols = j.columns && j.columns.length
          ? j.columns
          : (j.rows[0] ? Object.keys(j.rows[0]) : []);
        bubbleTable(cols, j.rows);
        return;
      }

      // 2) text that looks like your \"Recent orders\" list?
      const parsed = parseRecentOrders(j.reply || '');
      if (parsed) {
        bubbleTable(parsed.columns, parsed.rows);
      } else {
        bubbleText(j.reply || '…', 'bot');
      }
    } catch (e) {
      bubbleTyping(false);
      bubbleText('Sorry, something went wrong.', 'bot');
      // console.error(e);
    } finally {
      pending = false; send.disabled = false; input.focus();
    }
  }

  send?.addEventListener('click', ask);
  input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') ask(); });

})();
