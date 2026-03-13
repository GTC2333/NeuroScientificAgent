import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command, mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '')

  const host = env.HOST || '0.0.0.0'
  // When binding to all interfaces (0.0.0.0), proxy should connect to localhost
  // Otherwise, proxy to the specific host the backend is bound to
  const proxyHost = host === '0.0.0.0' ? 'localhost' : host
  const port = env.PORT || 3001

  // MAS Backend URL - configurable via env
  const masBackendUrl = env.MAS_BACKEND_URL || 'http://localhost:9000'
  const expressServerUrl = 'http://localhost:3001'

  return {
    plugins: [react()],
    server: {
      host,
      port: parseInt(env.VITE_PORT) || 9001,
      proxy: {
        // Forward /api/commands and /api/taskmaster to Express server (port 3001)
        // All other /api routes go to FastAPI backend (port 9000)
        '/api/commands': expressServerUrl,
        '/api/taskmaster': expressServerUrl,
        '/api': masBackendUrl,
        // WebSocket for streaming responses
        '/ws': {
          target: masBackendUrl,
          ws: true
        },
        // Shell/terminal WebSocket (if needed)
        '/shell': {
          target: masBackendUrl,
          ws: true
        }
      }
    },
    build: {
      outDir: 'dist',
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-codemirror': [
              '@uiw/react-codemirror',
              '@codemirror/lang-css',
              '@codemirror/lang-html',
              '@codemirror/lang-javascript',
              '@codemirror/lang-json',
              '@codemirror/lang-markdown',
              '@codemirror/lang-python',
              '@codemirror/theme-one-dark'
            ],
            'vendor-xterm': ['@xterm/xterm', '@xterm/addon-fit', '@xterm/addon-clipboard', '@xterm/addon-webgl']
          }
        }
      }
    }
  }
})
