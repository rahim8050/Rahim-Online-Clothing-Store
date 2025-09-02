import { createApp } from 'vue';
import RahimAssistant from './components/RahimAssistant.vue';
import '../static/css/rahim-assistant.css';

// Mount the component as the root app to ensure it renders immediately
const mountId = '#rahim-assistant-mount';
const target = document.querySelector(mountId);
if (target) {
  createApp(RahimAssistant).mount(mountId);
} else {
  console.warn('RahimAssistant: mount target not found', mountId);
}
