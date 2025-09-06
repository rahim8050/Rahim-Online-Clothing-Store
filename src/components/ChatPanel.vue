<!-- SafeAssistant.vue -->
<template>
  <teleport to="body">
    <!-- Full-screen root NEVER intercepts clicks -->
    <div class="assistant-root theme--blue" :data-open="isOpen">
      <!-- Floating button (interactive) -->
      <button
        v-show="!isOpen"
        class="fab"
        @click="toggle(true)"
        aria-label="Open assistant"
      >
        💬
      </button>

      <!-- Panel (interactive) -->
      <section
        v-show="isOpen"
        class="panel bg-surface"
        role="dialog"
        aria-modal="true"
        aria-label="Assistant"
      >
        <header class="header">
          <div class="title">
            <div class="name">Rahim Assistant</div>
            <div class="sub">{{ subtitle }}</div>
          </div>
          <div class="header-actions">
            <span class="role-badge">{{ role }}</span>
            <button class="close" @click="toggle(false)" aria-label="Close">×</button>
          </div>
        </header>

        <div ref="listEl" class="messages">
          <div v-for="(m,i) in messages" :key="i" class="bubble" :class="m.who==='you' ? 'you' : 'bot'">
            <div v-if="m.kind==='text'">{{ m.text }}</div>
            <div v-else-if="m.kind==='table'" class="table-wrap">
              <div class="table-head">
                <div class="title">{{ m.table.title || 'Table' }}</div>
                <div class="actions">
                  <button class="chip" @click="copyCSV(m.table)">Copy CSV</button>
                  <button class="chip" @click="copyJSON(m.table)">Copy JSON</button>
                </div>
              </div>
              <div class="scroll-x">
                <table class="nice">
                  <thead><tr><th v-for="c in m.table.columns" :key="c">{{ c }}</th></tr></thead>
                  <tbody>
                    <tr v-for="(r,rIdx) in normalizedRows(m.table)" :key="rIdx" :class="rIdx % 2 ? 'odd' : ''">
                      <td v-for="(cell,cIdx) in r" :key="cIdx">{{ cell }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="m.table.footnote" class="footnote">{{ m.table.footnote }}</div>
            </div>
          </div>
        </div>

        <div class="suggestions">
          <button v-for="s in suggestions" :key="s" class="chip" @click="useSuggestion(s)">{{ s }}</button>
        </div>

        <form class="composer" @submit.prevent="submit">
          <div class="row">
            <textarea
              ref="taEl"
              v-model="draft"
              rows="1"
              class="ta"
              placeholder="Ask me anything…"
              @input="autosize"
              @keydown.enter.exact.stop.prevent="submit"
              @keydown.enter.shift.stop
            />
            <!-- Explicitly type=button and stop propagation to avoid interfering with page forms -->
            <button type="button" class="send" :disabled="!canSend" @click.stop.prevent="submit">Send</button>
          </div>
        </form>
      </section>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'

type Role = 'vendor'|'vendor_staff'|'customer'|'driver'|'admin'|'guest'
const props = defineProps<{ apiUrl: string; role: Role }>()

const CONFIG: Record<Role, { subtitle: string; suggestions: string[] }> = {
  vendor: { subtitle: 'Vendor helper', suggestions: ['list orders','create product','order RAH123','payouts','inventory'] },
  vendor_staff: { subtitle: 'Vendor staff helper', suggestions: ['assigned products','import CSV','orders today'] },
  customer: { subtitle: 'Customer helper', suggestions: ['track order RAH123','refund policy','shipping fees'] },
  driver: { subtitle: 'Driver helper', suggestions: ['my deliveries','start shift','delivery status 57'] },
  admin: { subtitle: 'Admin helper', suggestions: ['system health','failed webhooks','reconcile payouts'] },
  guest: { subtitle: 'Assistant', suggestions: ['sign in','help','contact'] }
}
const role = (props.role || 'customer') as Role
const subtitle = CONFIG[role].subtitle
const suggestions = CONFIG[role].suggestions

const isOpen = ref(false)
const messages = ref<any[]>([])
const draft = ref('')
const listEl = ref<HTMLDivElement|null>(null)
const taEl = ref<HTMLTextAreaElement|null>(null)
const canSend = computed(() => draft.value.trim().length > 0)

const STORAGE_KEY = 'assistant_state_v1'
function loadState(){ try { const s = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); if(s){ messages.value=s.messages||[]; draft.value=s.draft||''; } } catch{} }
function saveState(){ try { localStorage.setItem(STORAGE_KEY, JSON.stringify({messages:messages.value, draft:draft.value})) } catch{} }
loadState()
watch(draft, saveState)

function pushText(who:'you'|'bot', text:string){ messages.value.push({kind:'text', who, text}); scrollToBottom(); saveState() }
function pushTable(tbl:any){ messages.value.push({kind:'table', who:'bot', table:tbl}); scrollToBottom(); saveState() }
function normalizedRows(tbl:any){ return (tbl.rows||[]).map((r:any)=>Array.isArray(r)?r:Object.values(r)) }
function toCSV(cols:string[], rows:any[][]){ const data=[cols,...rows]; return data.map(r=>r.map(v=>{const s=v==null?'':String(v); return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s}).join(',')).join('\n') }
async function copyCSV(tbl:any){ const rows=normalizedRows(tbl); await navigator.clipboard.writeText(toCSV(tbl.columns||[], rows)) }
async function copyJSON(tbl:any){ const rows=normalizedRows(tbl); await navigator.clipboard.writeText(JSON.stringify({columns:tbl.columns||[], rows}, null, 2)) }
function useSuggestion(s:string){ draft.value=s; saveState(); autosize() }
function scrollToBottom(){ nextTick(()=> listEl.value?.scrollTo({top: listEl.value.scrollHeight, behavior:'smooth'})) }
function autosize(){ if(!taEl.value) return; taEl.value.style.height='0px'; taEl.value.style.height=Math.min(taEl.value.scrollHeight,112)+'px' }

function getCSRFCookie(){ const m=document.cookie.match(/csrftoken=([^;]+)/); return m?decodeURIComponent(m[1]):null }
async function submit(){
  const q = draft.value.trim(); if(!q) return
  pushText('you', q); draft.value=''; autosize()
  const sessKey = localStorage.getItem('rahimAssistantSession') || (()=>{
    const k = (crypto?.randomUUID?.() || String(Date.now())); localStorage.setItem('rahimAssistantSession', k); return k
  })()
  try{
    const res = await fetch(props.apiUrl, { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':getCSRFCookie()||''}, body: JSON.stringify({ message:q, role, session_key:sessKey }) })
    const raw = await res.text(); if(!res.ok) throw new Error(`HTTP ${res.status}: ${raw.slice(0,200)}`)
    const data = JSON.parse(raw)
    if (data?.table?.rows) pushTable(data.table)
    else pushText('bot', data?.reply ?? '(no reply)')
  }catch(e:any){ pushText('bot','⚠️ Assistant error. Check console.'); console.error('[assistant]', e) }
}

function toggle(v:boolean){ isOpen.value=v }
watch(isOpen, v => { document.body.style.overflow = v ? 'hidden' : '' })
onMounted(()=> nextTick(autosize))
</script>

<style scoped>
/* Root never intercepts clicks */
.assistant-root { position: fixed; inset: 0; z-index: 2147483000; pointer-events: none; }
.assistant-root .fab,
.assistant-root .panel { pointer-events: auto; }

/* Optional non-interactive backdrop when open */
.assistant-root[data-open="true"]::before {
  content: ""; position: fixed; inset: 0;
  background: rgba(0,0,0,.25); pointer-events: none;
}

/* FAB */
.fab {
  position: fixed; right: 1rem; bottom: 1rem;
  width: 56px; height: 56px; border-radius: 9999px;
  background: #2563eb; color: #fff; border: none;
  display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 8px 20px rgba(0,0,0,.35); cursor: pointer; font-size: 20px;
}
.fab:active { transform: translateY(1px); }

/* Panel */
.panel {
  position: fixed; right: 1rem; bottom: 5.5rem;
  width: 380px; max-height: 70vh; display: flex; flex-direction: column;
  border-radius: 1rem; box-shadow: 0 20px 50px rgba(0,0,0,.35);
}
@media (max-width: 767px) {
  .panel { right: .5rem; left: .5rem; bottom: 5rem; width: auto; max-height: 75vh; }
}

/* Theme + content (same as yours) */
.theme--blue { --md-sys-color-primary: #2563eb; }
.theme--blue .header { background: color-mix(in oklab, var(--md-sys-color-primary) 85%, transparent);
  display:flex; align-items:center; justify-content:space-between; padding:.75rem 1rem; }
.bg-surface { background: linear-gradient(#0b1b29, #0a1320 60%, #090c13); color: white; }
.title .name { font-weight:600; }
.title .sub { font-size:12px; opacity:.9; }
.header-actions { display:inline-flex; align-items:center; gap:.5rem; }
.role-badge { display:inline-flex; font-size:11px; padding:2px 8px; border-radius:999px;
  border:1px solid rgba(255,255,255,.3); background:rgba(255,255,255,.1); text-transform:capitalize; }
.close { appearance:none; border:1px solid rgba(255,255,255,.35); background:rgba(255,255,255,.12); color:#fff;
  width:28px; height:28px; border-radius:9999px; font-size:18px; line-height:24px; cursor:pointer; }
.close:hover { background: rgba(255,255,255,.2); }

.messages { flex:1; overflow-y:auto; padding:.75rem; display:flex; flex-direction:column; gap:.5rem; }
.bubble { padding:.5rem .625rem; border-radius:.75rem; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); }
.bubble.you { background:rgba(255,255,255,.10); align-self:flex-end; }

.suggestions { padding:.25rem .75rem .5rem; display:flex; flex-wrap:wrap; gap:.5rem; }
.chip { padding:.375rem .75rem; border-radius:999px; border:1px solid rgba(255,255,255,.2);
  background:rgba(255,255,255,.1); font-size:.8rem; cursor:pointer; }
.chip:hover { background: rgba(255,255,255,.15); }

.table-wrap { border-radius:.75rem; }
.table-head { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding-bottom:.25rem; }
.table-head .title { font-weight:600; font-size:.9rem; opacity:.9; }
.scroll-x { overflow-x:auto; }
table.nice { width:100%; border-collapse:collapse; font-size:.9rem; }
table.nice thead { background: rgba(255,255,255,.08); }
table.nice th, table.nice td { text-align:left; padding:.5rem .75rem; white-space:nowrap; }
table.nice tbody tr.odd { background: rgba(255,255,255,.03); }
.footnote { margin-top:.25rem; font-size:.7rem; opacity:.7; }

.composer { border-top:1px solid rgba(255,255,255,.1); background:rgba(255,255,255,.05); padding:.5rem; }
.composer .row { display:flex; align-items:flex-end; gap:.5rem; }
.ta { min-height:44px; max-height:112px; width:100%; resize:none; border-radius:.75rem; padding:.5rem .75rem;
  background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.2); color:white; }
.ta:focus { outline:none; box-shadow:0 0 0 2px rgba(37,99,235,.7); border-color:transparent; }
.send { padding:.5rem 1rem; border-radius:.75rem; background:#2563eb; color:white; cursor:pointer; }
.send:hover { background:#1d4ed8; }
.send:disabled { opacity:.5; cursor:not-allowed; }
</style>
