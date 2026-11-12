import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Served by the MailLens backend at /dashboard/ (same origin as the API: no CORS, strict CSP).
export default defineConfig({
  base: '/dashboard/',
  plugins: [react()],
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 600 },
  server: { proxy: { '/v1': 'http://127.0.0.1:8787' } },
});
