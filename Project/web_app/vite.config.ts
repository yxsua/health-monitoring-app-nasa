import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api/v1/chatbot': { target: 'http://127.0.0.1:8002', changeOrigin: true },
      '/api/v1/simulation': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/api/v1': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: true },
});
