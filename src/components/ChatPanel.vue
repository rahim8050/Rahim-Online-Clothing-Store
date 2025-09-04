<template>
  <!-- Wrapper is always present; panel can be toggled -->
  <div class="assistant theme--blue">
    <!-- Floating open button (bubble) -->
    <button v-show="!isOpen" class="fab" @click="isOpen = true" aria-label="Open assistant">
      <!-- simple chat glyph -->
      <span class="fab-icon">💬</span>
    </button>

    <!-- Panel -->
    <section v-show="isOpen" class="panel bg-surface">
      <header class="header">
        <div class="title">
          <div class="name">Rahim Assistant</div>
          <div class="sub">{{ subtitle }}</div>
        </div>

        <div class="header-actions">
          <span class="role-badge">{{ role }}</span>
          <button class="close" @click="isOpen = false" aria-label="Close assistant">×</button>
        </div>
      </header>

      <div ref="listEl" class="messages">
        <div v-for="(m, i) in messages" :key="i" class="bubble" :class="m.who === 'you' ? 'you' : 'bot'">
          <div v-if="m.kind === 'text'">{{ m.text }}</div>
          <div v-else-if="m.kind === 'table'" class="table-wrap">
            <div class="table-head">
              <div class="title">{{ m.table.title || 'Table' }}</div>
              <div class="actions">
                <button class="chip" @click="copyCSV(m.table)">Copy CSV</button>
                <button class="chip" @click="copyJSON(m.table)">Copy JSON</button>
              </div>
            </div>
            <div class="scroll-x">
              <table class="nice">
                <thead>
                  <tr>
                    <th v-for="c in m.table.columns" :key="c">{{ c }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, rIdx) in normalizedRows(m.table)" :key="rIdx" :class="rIdx % 2 ? 'odd' : ''">
                    <td v-for="(cell, cIdx) in r" :key="cIdx">{{ cell }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="m.table.footnote" class="footnote">{{ m.table.footnote }}</div>
          </div>
        </div>
      </div>

      <!-- Suggestions -->
      <div class="suggestions">
        <button v-for="s in suggestions" :key="s" class="chip" @click="useSuggestion(s)">{{ s }}</button>
      </div>

      <!-- Composer (Topics + hint removed) -->
      <form class="composer" @submit.prevent="submit">
        <div class="row">
          <textarea ref="taEl" v-model="draft" rows="1" @input="autosize" @keydown.enter.exact.prevent="submit" @keydown.enter.shift.stop placeholder="Ask me anything…" class="ta" />
          <button class="send" :disabled="!canSend">Send</button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'

type Role = 'vendor'|'vendor_staff'|'customer'|'driver'|'admin'|'guest'
const props = defineProps<{ apiUrl: string; role: Role }>()

const CONFIG: Record<Role, { subtitle: string; suggestions: string[]; persona: string }> = {
  vendor:       { subtitle: 'Vendor helper',       suggestions: ['list orders','create product','order status RAH123','payouts','inventory'], persona: 'vendor' },
  vendor_staff: { subtitle: 'Vendor staff helper', suggestions: ['assigned products','import CSV','orders today','deactivate staff'], persona: 'vendor_staff' },
  customer:     { subtitle: 'Customer helper',     suggestions: ['track order RAH123','refund policy','shipping fees','returns'], persona: 'customer' },
  driver:       { subtitle: 'Driver helper',       suggestions: ['my deliveries','start shift','delivery status 57','panic'], persona: 'driver' },
  admin:        { subtitle: 'Admin helper',        suggestions: ['system health','failed webhooks','user search rahim','reconcile payouts'], persona: 'admin' },
  guest:        { subtitle: 'Assistant',           suggestions: ['sign in','help','contact'], persona: 'guest' }
}
const role = (props.role || 'customer') as Role
const subtitle = CONFIG[role]?.subtitle ?? 'Assistant'
const suggestions = CONFIG[role]?.suggestions ?? []
const persona = CONFIG[role]?.persona ?? 'customer'

// Start closed by default; open only on user interaction
const isOpen = ref(false)

const messages = ref<Array<any>>([])
const draft = ref('')
const listEl = ref<HTMLDivElement | null>(null)
const taEl = ref<HTMLTextAreaElement | null>(null)
const canSend = computed(() => draft.value.trim().length > 0)

// Persist only content (messages, draft). Never persist open/closed state.
const STORAGE_KEY = 'assistant_state_v1'
function loadState(){
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const s = JSON.parse(raw)
    if (Array.isArray(s.messages)) messages.value = s.messages
    if (typeof s.draft === 'string') draft.value = s.draft
  } catch {}
}
function saveState(){
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ messages: messages.value, draft: draft.value })) } catch {}
}

// Restore persisted content on script setup (does not open panel)
loadState()


function pushText(who: 'you'|'bot', text: string) {
  messages.value.push({ kind: 'text', who, text })
  scrollToBottom()
  saveState()
}
function pushTable(tbl: { title?:string; columns:string[]; rows:any[]; footnote?:string }) {
  messages.value.push({ kind: 'table', who: 'bot', table: tbl })
  scrollToBottom()
  saveState()
}
function scrollToBottom() { nextTick(() => listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'smooth' })) }
function autosize() { if (!taEl.value) return; taEl.value.style.height='0px'; taEl.value.style.height=Math.min(taEl.value.scrollHeight,112)+'px' }
function useSuggestion(s: string) { draft.value = s; saveState(); autosize() }

// Persist draft updates as user types
watch(draft, () => saveState())

function normalizedRows(tbl: any): any[] { return (tbl.rows || []).map((r: any) => Array.isArray(r) ? r : Object.values(r)) }
function toCSV(columns: string[], rows: any[][]): string { const data=[columns, ...rows]; return data.map(cols=>cols.map(v=>{ const s=v==null?'':String(v); return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s; }).join(',')).join('\n') }
async function copyCSV(tbl: any) { const rows = normalizedRows(tbl); await navigator.clipboard.writeText(toCSV(tbl.columns || [], rows)) }
async function copyJSON(tbl: any) { const rows = normalizedRows(tbl); await navigator.clipboard.writeText(JSON.stringify({ columns: tbl.columns || [], rows }, null, 2)) }

function getCSRFCookie(): string | null { const m=document.cookie.match(/csrftoken=([^;]+)/); return m?decodeURIComponent(m[1]):null }

async function submit() {
  const q = draft.value.trim(); if (!q) return
  pushText('you', q); draft.value = ''; autosize()

  // persist a session key per-browser
  const sessKey = localStorage.getItem('rahimAssistantSession') || (() => {
    const k = (crypto?.randomUUID?.() || String(Date.now()))
    localStorage.setItem('rahimAssistantSession', k)
    return k
  })()

  try {
    const res = await fetch(props.apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFCookie() || '' },
      body: JSON.stringify({ message: q, persona, session_key: sessKey })
    })
    const raw = await res.text(); if (!res.ok) throw new Error(`HTTP ${res.status}: ${raw.slice(0,200)}`)
    const data = JSON.parse(raw)
    if (data?.table?.rows) {
      pushTable(data.table)
    } else if (typeof data?.reply === 'string' && /^\s*Recent orders:/i.test(data.reply)) {
      const rows = data.reply.split('\n').slice(1).map((s: string)=>s.trim()).filter(Boolean).map((line: string)=>{ const m=line.match(/^(\d+):\s*(\S+)\s+-\s+([A-Z_]+)\s+\(([^)]+)\)/i); return m?[m[1],m[2],m[3],m[4]]:['','','',line] })
      pushTable({ title: 'Recent orders', columns: ['#','Order Code','Status','Item'], rows })
    } else {
      pushText('bot', data?.reply ?? '(no reply)')
    }
  } catch (e:any) {
    pushText('bot', '⚠️ Assistant error. Check console.'); console.error('[assistant]', e)
  }
}

onMounted(() => { nextTick(autosize) })
</script>

<style scoped>
/* Fallback layout (no Tailwind required) */
.assistant { position: fixed; inset: 0; z-index: 2147483000; }
.panel { height: 100%; width: 100%; max-height: 100vh; display: flex; flex-direction: column; border-radius: 0; pointer-events: auto; }
@media (min-width: 768px) {
  .assistant { inset: auto; right: 1rem; bottom: 1rem; width: 380px; height: 560px; max-height: 85vh; }
  .panel { height: 100%; width: 100%; border-radius: 1rem; }
}

/* Open bubble button */
.fab {
  position: fixed;
  right: 1rem; bottom: 1rem;
  width: 56px; height: 56px; border-radius: 9999px;
  background: #2563eb; color: #fff; border: none;
  box-shadow: 0 8px 20px rgba(0,0,0,.35);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 20px;
}
.fab:active { transform: translateY(1px); }
.fab-icon { line-height: 1; }

/* Header & close */
.theme--blue { --md-sys-color-primary: #2563eb; }
.theme--blue .header { background: color-mix(in oklab, var(--md-sys-color-primary) 85%, transparent); display:flex; align-items:center; justify-content:space-between; padding: .75rem 1rem; }
.bg-surface { background: linear-gradient(#0b1b29, #0a1320 60%, #090c13); color: white; }
.title .name { font-weight: 600; }
.title .sub { font-size: 12px; opacity: .9; }
.header-actions { display: inline-flex; align-items: center; gap: .5rem; }
.role-badge { display: inline-flex; font-size: 11px; padding: 2px 8px; border-radius: 999px; border:1px solid rgba(255,255,255,.3); background: rgba(255,255,255,.1); text-transform: capitalize; }
.close { appearance: none; border: 1px solid rgba(255,255,255,.35); background: rgba(255,255,255,.12); color: #fff; width: 28px; height: 28px; border-radius: 9999px; font-size: 18px; line-height: 24px; cursor: pointer; }
.close:hover { background: rgba(255,255,255,.2); }

/* Messages & bubbles */
.messages { flex: 1; overflow-y: auto; padding: .75rem; display: flex; flex-direction: column; gap: .5rem; }
.bubble { padding:.5rem .625rem; border-radius:.75rem; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); }
.bubble.you { background:rgba(255,255,255,.10); align-self: flex-end; }

/* Tables */
.table-wrap { border-radius:.75rem; }
.table-head { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding-bottom:.25rem; }
.table-head .title { font-weight:600; font-size:.9rem; opacity:.9; }
.actions { display:flex; gap:.5rem; }
.chip { padding:.375rem .75rem; border-radius:999px; border:1px solid rgba(255,255,255,.2); background: rgba(255,255,255,.1); font-size:.8rem; cursor: pointer; }
.chip:hover { background: rgba(255,255,255,.15); }
.scroll-x { overflow-x:auto; }
table.nice { width:100%; border-collapse: collapse; font-size:.9rem; }
table.nice thead { background: rgba(255,255,255,.08); }
table.nice th, table.nice td { text-align:left; padding:.5rem .75rem; white-space:nowrap; }
table.nice tbody tr.odd { background: rgba(255,255,255,.03); }
.footnote { margin-top:.25rem; font-size:.7rem; opacity:.7; }

/* Suggestions */
.suggestions { padding: .25rem .75rem .5rem; display:flex; flex-wrap:wrap; gap:.5rem; }

/* Composer (Topics & hint removed) */
.composer { border-top: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.05); padding: .5rem; }
.composer .row { display:flex; align-items:flex-end; gap:.5rem; }
.ta { min-height:44px; max-height:112px; width:100%; resize:none; border-radius:.75rem; padding:.5rem .75rem; background: rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.2); color:white; }
.ta:focus { outline:none; box-shadow:0 0 0 2px rgba(37,99,235,.7); border-color:transparent; }
.send { padding:.5rem 1rem; border-radius:.75rem; background:#2563eb; color:white; cursor: pointer; }
.send:hover { background:#1d4ed8; }
.send:disabled { opacity:.5; cursor:not-allowed; }
</style>


