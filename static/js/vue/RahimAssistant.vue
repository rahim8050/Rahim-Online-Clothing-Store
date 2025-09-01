<template>
  <div id="rahim-assistant" class="fixed bottom-4 right-4 z-50">
    <!-- Panel -->
    <div
      v-show="open"
      class="w-[360px] max-w-[92vw] rounded-2xl shadow-2xl border border-white/10
             bg-gradient-to-b from-[#1b0b29] via-[#130a1e] to-[#0c0913] text-white
             overflow-hidden backdrop-blur"
    >
      <!-- Header -->
      <div class="px-4 py-3 bg-gradient-to-r from-fuchsia-600/70 to-indigo-600/70 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-full bg-white/10 grid place-items-center ring-2 ring-fuchsia-400/60">
            <span class="text-pink-300">🤖</span>
          </div>
          <div class="leading-tight">
            <div class="font-semibold">
              {{ title }}
              <span v-if="beta" class="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-black/30">Beta</span>
            </div>
            <div class="text-[11px] text-white/70">{{ subtitle }}</div>
          </div>
        </div>
        <button @click="open=false" class="text-white/80 hover:text-white text-xl leading-none">×</button>
      </div>

      <!-- Welcome / suggestions -->
      <div v-if="showWelcome" class="px-4 pt-3 pb-2 text-xs text-white/80 border-b border-white/10">
        Hey, I'm Rahim! My goal is to make your orders, deliveries, and payments simple. I can view your data to help, but I can’t move your funds. You’re always in control. 👍
        <div class="mt-2 flex flex-wrap gap-2">
          <button v-for="(s, i) in currentChips" :key="'chip-'+i" class="chip" @click="useSuggestion(s)">{{ s }}</button>
        </div>
      </div>

      <!-- Messages -->
      <div ref="feed" class="p-4 space-y-2 h-80 overflow-y-auto text-[13px] bg-transparent">
        <div v-for="(m, i) in messages" :key="i" :class="['msg', m.who]">
          <div :class="['bubble', m.who]">{{ m.text }}</div>
        </div>
        <div v-if="typing" class="msg bot typing-row">
          <div class="bubble bot typing"><span></span><span></span><span></span></div>
        </div>
      </div>

      <!-- Input row -->
      <div class="border-t border-white/10 p-2">
        <div class="flex items-end gap-2">
          <button @click="rotateTopics" class="px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 text-xs">Topics</button>
          <div class="flex-1 bg-white/5 rounded-xl flex items-center px-3 py-2 ring-1 ring-white/10 focus-within:ring-fuchsia-400/50">
            <input v-model="draft" @keydown.enter.prevent="send" class="flex-1 bg-transparent outline-none placeholder:text-white/40 text-sm" :placeholder="placeholder" />
            <button @click="send" :disabled="pending" class="ml-2 px-3 py-1.5 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-500 text-white text-sm disabled:opacity-50">Send</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Launcher -->
    <button @click="open = !open"
            class="rounded-full w-14 h-14 bg-gradient-to-br from-fuchsia-600 to-indigo-600 text-white shadow-2xl
                   flex items-center justify-center ring-2 ring-white/10 hover:scale-105 transition">
      <span class="text-2xl">💬</span>
    </button>
  </div>
</template>

<script>
export default {
  name: 'RahimAssistant',
  props: {
    endpoint: { type: String, default: '/api/assistant/ask/' },
    title: { type: String, default: 'Rahim Assistant' },
    subtitle: { type: String, default: 'Powered by Rahim Cloth store ' },
    beta: { type: Boolean, default: true },
    suggestions: {
      type: Array,
      default: () => [
        'What is my latest order?',
        'Track my delivery',
        'Payment status for #123',
        'How do refunds work?'
      ]
    },
    autoOpen: { type: Boolean, default: true },
    placeholder: { type: String, default: 'Ask me anything…' }
  },
  data(){
    return {
      open: false,
      messages: [],
      draft: '',
      pending: false,
      typing: false,
      chipPage: 0,
      sessionKey: this.getSessionKey(),
      showWelcome: true
    };
  },
  computed: {
    currentChips(){
      const chunk = 4;
      const start = this.chipPage * chunk;
      const arr = this.suggestions.slice(start, start + chunk);
      return arr.length ? arr : this.suggestions.slice(0, chunk);
    }
  },
  mounted(){
    // first-run auto-open (once per browser)
    if (this.autoOpen) {
      try {
        if (!localStorage.getItem('rahim_assistant_seen')) {
          this.open = true;
          localStorage.setItem('rahim_assistant_seen', '1');
        }
      } catch {}
    }
  },
  methods: {
    rotateTopics(){ this.chipPage = (this.chipPage + 1) % Math.ceil(this.suggestions.length / 4 || 1); },
    useSuggestion(s){ this.draft = s; this.send(); },
    addMessage(text, who){
      this.messages.push({ text, who });
      this.$nextTick(()=>{ const el = this.$refs.feed; if (el) el.scrollTop = el.scrollHeight; });
    },
    getSessionKey(){
      try {
        const k = sessionStorage.getItem('assistant_key');
        if (k) return k;
        const nk = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
        sessionStorage.setItem('assistant_key', nk);
        return nk;
      } catch { return String(Date.now()); }
    },
    getCookie(name){
      try {
        return document.cookie.split('; ').find(r=>r.startsWith(name+'='))?.split('=')[1] || '';
      } catch { return ''; }
    },
    async send(){
      const msg = (this.draft || '').trim();
      if (!msg || this.pending) return;
      this.showWelcome = false;
      this.addMessage(msg, 'me');
      this.draft = '';

      this.pending = true; this.typing = true;
      const headers = { 'Content-Type': 'application/json' };
      const csrf = window.CSRF_TOKEN || this.getCookie('csrftoken');
      if (csrf) headers['X-CSRFToken'] = csrf;

      try {
        const r = await fetch(this.endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          headers,
          body: JSON.stringify({ session_key: this.sessionKey, message: msg })
        });
        const ok = r.ok; let j = {};
        try { j = await r.json(); } catch {}
        this.typing = false;
        if (!ok) throw new Error('HTTP '+r.status);
        this.addMessage(j.reply || '…', 'bot');
      } catch (e) {
        this.typing = false;
        this.addMessage('Sorry, something went wrong.', 'bot');
        // console.error(e);
      } finally {
        this.pending = false;
      }
    }
  }
}
</script>

<style scoped>
.chip{font-size:12px;padding:.35rem .6rem;border-radius:9999px;background:rgba(255,255,255,.06);color:#fff;border:1px solid rgba(255,255,255,.12)}
.chip:hover{background:rgba(255,255,255,.12)}
.msg{display:flex;gap:.5rem}
.msg.me{justify-content:flex-end}
.bubble{max-width:85%;padding:.5rem .7rem;border-radius:12px}
.bubble.me{background:#6d28d9;color:#fff}
.bubble.bot{background:rgba(255,255,255,.08);color:#fff;border:1px solid rgba(255,255,255,.08)}
.typing span{display:inline-block;width:6px;height:6px;margin-right:3px;border-radius:50%;background:#ddd;opacity:.6;animation:blink 1.1s infinite}
.typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.2;transform:translateY(0)}40%{opacity:1;transform:translateY(-2px)}}
</style>
