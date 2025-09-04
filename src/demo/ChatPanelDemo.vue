<template>
  <div class="p-6 space-y-4">
    <h1 class="text-2xl font-semibold">ChatPanel Demo</h1>
    <div class="flex items-center gap-3">
      <label class="flex items-center gap-2">
        <input type="checkbox" v-model="hybrid"> Hybrid theme
      </label>
      <button @click="toggleDark" class="px-3 py-1 rounded border">Toggle dark</button>
    </div>
    <p class="text-sm opacity-80">Toggle hybrid mode via html[data-theme="hybrid"]. Strict M3 is default.</p>

    <ChatPanel />
  </div>
</template>

<script setup lang="ts">
import ChatPanel from '../components/ChatPanel.vue';
import '../assets/base.css';
import { ref, watchEffect } from 'vue';

const hybrid = ref(false);
watchEffect(() => {
  const html = document.documentElement;
  if (hybrid.value) html.setAttribute('data-theme', 'hybrid');
  else html.removeAttribute('data-theme');
});

function toggleDark() {
  const html = document.documentElement;
  html.classList.toggle('dark');
}
</script>

<style>
body { background: var(--m3-surface); color: var(--m3-on-surface); }
button { border-color: var(--m3-outline-variant); }
</style>
