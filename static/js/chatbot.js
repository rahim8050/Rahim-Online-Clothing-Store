(() => {
  const root = document.getElementById('rahim-assistant');
  if (!root) return;

  const panel = document.getElementById('assistant-panel');
  const toggle = document.getElementById('assistant-toggle');
  const closeBtn = document.getElementById('assistant-close');
  const input = document.getElementById('assistant-input');
  const send = document.getElementById('assistant-send');
  const feed = document.getElementById('assistant-messages');

  function genKey(){
    const k = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    try { sessionStorage.setItem('assistant_key', k); } catch {}
    return k;
  }
  function getKey(){
    try { return sessionStorage.getItem('assistant_key') || genKey(); } catch { return genKey(); }
  }
  const SESSION_KEY = getKey();

  function line(text, who){
    const div = document.createElement('div');
    div.className = who === 'me' ? 'text-right' : 'text-left';
    const bubble = document.createElement('div');
    bubble.className = (who === 'me') ? 'inline-block rounded-lg px-3 py-2 bg-blue-600 text-white' : 'inline-block rounded-lg px-3 py-2 bg-gray-100';
    bubble.textContent = text;
    div.appendChild(bubble);
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
  }

  function togglePanel(){ panel.classList.toggle('hidden'); }
  toggle?.addEventListener('click', togglePanel);
  closeBtn?.addEventListener('click', togglePanel);

  async function ask(){
    const msg = (input.value || '').trim();
    if (!msg) return;
    line(msg, 'me');
    input.value = '';
    try {
      const r = await fetch('/api/assistant/ask/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.CSRF_TOKEN || ''
        },
        credentials: 'same-origin',
        body: JSON.stringify({ session_key: SESSION_KEY, message: msg })
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json();
      line(j.reply || '…', 'bot');
    } catch (e) {
      line('Sorry, something went wrong.', 'bot');
    }
  }

  send?.addEventListener('click', ask);
  input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') ask(); });
})();

