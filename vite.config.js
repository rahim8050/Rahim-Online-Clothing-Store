import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// Use dev-friendly base in serve, Django static base in build
export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === 'build' ? '/static/dist/' : '/',
  server: {
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173',
  },
  build: {
    // Output into top-level static so Django staticfiles can serve it
    outDir: 'static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: 'assets/main.js',
      output: {
        entryFileNames: 'assets/main.js',
        assetFileNames: 'assets/[name][extname]'
      }
    },
  },
}));
