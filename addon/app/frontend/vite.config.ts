import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Use relative base so assets load correctly under HA Ingress path prefix
  // HA Ingress serves the app at /api/hassio_ingress/<token>/ — absolute paths
  // like /assets/... would 404. Relative paths (./assets/...) work correctly.
  base: './',

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  build: {
    // Output to dist/ — served as static files by the aiohttp server
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
    // Dev server proxy — forwards /api/* to the addon server during development
    proxy: {
      '/api': {
        target: 'http://localhost:8099',
        changeOrigin: true,
        ws: true,
      },
    },
    port: 3000,
    open: false,
  },

  preview: {
    port: 3001,
  },
})
