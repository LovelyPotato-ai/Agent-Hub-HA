import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  build: {
    // Output to dist/ — AppDaemon serves this as static files
    outDir: 'dist',
    emptyOutDir: true,
    // Inline small assets to reduce HTTP requests on the local network
    assetsInlineLimit: 4096,
    sourcemap: false,
    rollupOptions: {
      output: {
        // Stable chunk names for caching
        manualChunks: {
          react: ['react', 'react-dom'],
          markdown: ['react-markdown', 'remark-gfm'],
        },
      },
    },
  },

  server: {
    // Dev server proxy — forwards API calls to AppDaemon during development
    // Change the target to your HA Green's IP if developing remotely
    proxy: {
      '/api/appdaemon': {
        target: 'http://homeassistant.local:5050',
        changeOrigin: true,
        ws: true, // proxy WebSocket connections too
      },
    },
    port: 3000,
    open: false,
  },

  preview: {
    port: 3001,
  },
})
