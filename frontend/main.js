import { createApp } from 'vue'
import RahimAssistant from './RahimAssistant.vue'

const app = createApp({})
app.component('rahim-assistant', RahimAssistant)
app.mount('#rahim-assistant-mount')
