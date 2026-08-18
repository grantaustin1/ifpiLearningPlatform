import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Bundle analyzer — run with ANALYZE=true npm run build
const analyze = process.env.ANALYZE === 'true'

export default defineConfig({
  plugins: [
    react(),
    analyze && (await import('rollup-plugin-visualizer')).visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
      filename: 'dist/stats.html',
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
  },
  build: {
    outDir: 'build',
    sourcemap: true,
    // Chunk-splitting heuristic: vendors in their own chunk,
    // everything else auto-split by Rollup.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          radix: [
            '@radix-ui/react-avatar',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-progress',
            '@radix-ui/react-slot',
            '@radix-ui/react-tabs',
            '@radix-ui/react-toast',
          ],
        },
      },
    },
  },
  envPrefix: 'VITE_',
})
