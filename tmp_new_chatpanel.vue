<template>
  <!-- Fullscreen on mobile; floating card on md+ -->
  <div class="assistant theme--blue fixed inset-0 md:inset-auto md:bottom-4 md:right-4 z-[9999]">
    <section class="panel h-full w-full md:h-[560px] md:w-[380px] md:max-h-[85vh] md:rounded-2xl shadow-2xl border border-white/10 bg-surface flex flex-col overflow-hidden">
      <!-- Header (blue) -->
      <header class="px-4 py-3 flex items-center justify-between header">
        <div class="leading-tight">
          <div class="font-semibold">Rahim Assistant</div>
          <div class="text-xs opacity-90">{{ subtitle }}</div>
        </div>
        <span class="hidden md:inline-flex text-[11px] px-2 py-0.5 rounded-full border border-white/30 bg-white/10 capitalize">{{ role }}</span>
      </header>

      <!-- Messages -->
      <div ref="listEl" class="flex-1 overflow-y-auto p-3 space-y-2">
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
      <div class="px-3 pt-1 pb-2 flex flex-wrap gap-2">
        <button v-for="s in suggestions" :key="s" class="chip" @click="useSuggestion(s)">{{ s }}</button>
      </div>

      <!-- Composer -->
      <form class="composer border-t border-white/10 bg-white/5 p-2" @submit.prevent="submit">
        <div class="row">
          <button type="button" class="chip">Topics</button>
          <textarea ref="taEl" v-model="draft" rows="1" @input="autosize" @keydown.enter.exact.prevent="submit" @keydown.enter.shift.stop placeholder="Ask me anything…" class="ta" />
          <button class="send" :disabled="!canSend">Send</button>
        </div>
        <div class="hint">Enter to send • Shift+Enter for newline</div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'

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

const messages = ref<Array<any>>([])
const draft = ref('')
const listEl = ref<HTMLDivElement | null>(null)
const taEl = ref<HTMLTextAreaElement | null>(null)
const canSend = computed(() => draft.value.trim().length > 0)

function pushText(who: 'you'|'bot', text: string) {
  messages.value.push({ kind: 'text', who, text })
  scrollToBottom()
}
function pushTable(tbl: { title?:string; columns:string[]; rows:any[]; footnote?:string }) {
  messages.value.push({ kind: 'table', who: 'bot', table: tbl })
  scrollToBottom()
}
function scrollToBottom() { nextTick(() => listEl.value?.scrollTo({ top: listEl.value.scrollHeight, behavior: 'smooth' })) }
function autosize() { if (!taEl.value) return; taEl.value.style.height='0px'; taEl.value.style.height=Math.min(taEl.value.scrollHeight,112)+'px' }
function useSuggestion(s: string) { draft.value = s; autosize() }

function normalizedRows(tbl: any): any[] { return (tbl.rows || []).map((r: any) => Array.isArray(r) ? r : Object.values(r)) }
function toCSV(columns: string[], rows: any[][]): string { const data=[columns, ...rows]; return data.map(cols=>cols.map(v=>{ const s=v==null?'':String(v); return /[",\n]/.test(s)?`"${s.replace(/"/g,'""')}"`:s; }).join(',')).join('\n') }
async function copyCSV(tbl: any) { const rows = normalizedRows(tbl); await navigator.clipboard.writeText(toCSV(tbl.columns || [], rows)) }
async function copyJSON(tbl: any) { const rows = normalizedRows(tbl); await navigator.clipboard.writeText(JSON.stringify({ columns: tbl.columns || [], rows }, null, 2)) }

async function submit() {
  const q = draft.value.trim(); if (!q) return
  pushText('you', q); draft.value = ''; autosize()
  try {
    const res = await fetch(props.apiUrl, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFCookie() || '' }, body: JSON.stringify({ message: q, persona }) })
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
function getCSRFCookie(): string | null { const m=document.cookie.match(/csrftoken=([^;]+)/); return m?decodeURIComponent(m[1]):null }

onMounted(() => { pushText('bot', `Hi! Try: ${suggestions.slice(0,3).join(' • ')}`); nextTick(autosize) })
</script>

<style scoped>
.assistant { pointer-events: none; }
.panel { pointer-events: auto; }
.theme--blue { --md-sys-color-primary: #2563eb; }
.theme--blue .header { background: color-mix(in oklab, var(--md-sys-color-primary) 85%, transparent); }
.bg-surface { background: linear-gradient(#0b1b29, #0a1320 60%, #090c13); color: white; }
.bubble { padding:.5rem .625rem; border-radius:.75rem; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); }
.bubble.you { background:rgba(255,255,255,.10); }
.table-wrap { border-radius:.75rem; }
.table-head { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding-bottom:.25rem; }
.table-head .title { font-weight:600; font-size:.9rem; opacity:.9; }
.actions { display:flex; gap:.5rem; }
.chip { padding:.375rem .75rem; border-radius:999px; border:1px solid rgba(255,255,255,.2); background: rgba(255,255,255,.1); font-size:.8rem; }
.chip:hover { background: rgba(255,255,255,.15); }
.scroll-x { overflow-x:auto; }
table.nice { width:100%; border-collapse: collapse; font-size:.9rem; }
table.nice thead { background: rgba(255,255,255,.08); }
table.nice th, table.nice td { text-align:left; padding:.5rem .75rem; white-space:nowrap; }
table.nice tbody tr.odd { background: rgba(255,255,255,.03); }
.footnote { margin-top:.25rem; font-size:.7rem; opacity:.7; }
.composer .row { display:flex; align-items:flex-end; gap:.5rem; }
.ta { min-height:44px; max-height:112px; width:100%; resize:none; border-radius:.75rem; padding:.5rem .75rem; background: rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.2); color:white; }
.ta:focus { outline:none; box-shadow:0 0 0 2px rgba(37,99,235,.7); border-color:transparent; }
.send { padding:.5rem 1rem; border-radius:.75rem; background:#2563eb; color:white; }
.send:hover { background:#1d4ed8; }
.send:disabled { opacity:.5; cursor:not-allowed; }
.hint { margin-top:.25rem; font-size:.7rem; opacity:.7; }
</style>