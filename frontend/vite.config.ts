import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ command, mode }) => ({
  plugins: [react(), tailwindcss()],
  define: { __LOCAL_RESEARCH_ENABLED__: JSON.stringify(command === 'serve' && mode === 'development' && loadEnv(mode, process.cwd(), 'VITE_').VITE_LOCAL_RESEARCH === '1') },
}))
