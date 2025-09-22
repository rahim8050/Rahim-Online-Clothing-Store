// Shared assistant UI state (messages + draft only). No open/closed persistence.
// Safe to include on any page; it no-ops when localStorage is unavailable.
(function(global){
  const KEY = 'assistant_state_v1';
  function load(){
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {} } catch { return {} }
  }
  function save(state){
    try { localStorage.setItem(KEY, JSON.stringify({ messages: state.messages||[], draft: state.draft||'' })) } catch {}
  }
  function getMessages(){ const s = load(); return Array.isArray(s.messages) ? s.messages : [] }
  function setMessages(msgs){ const s = load(); s.messages = Array.isArray(msgs) ? msgs : []; save(s) }
  function getDraft(){ const s = load(); return typeof s.draft === 'string' ? s.draft : '' }
  function setDraft(d){ const s = load(); s.draft = (d||''); save(s) }
  function clear(){ save({ messages: [], draft: '' }) }
  global.AssistantState = { load, save, getMessages, setMessages, getDraft, setDraft, clear }
})(window);
