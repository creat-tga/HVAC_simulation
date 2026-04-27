import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vendor-vue',
              test: /node_modules[\\/](vue|@vue|vue-router|pinia|vue-i18n)[\\/]/,
              priority: 30,
            },
            {
              name: 'vendor-element-plus',
              test: /node_modules[\\/](element-plus|@element-plus|@floating-ui|@sxzz|async-validator|dayjs|lodash|lodash-es|lodash-unified|normalize-wheel-es)[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor-echarts',
              test: /node_modules[\\/](echarts|vue-echarts)[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor-zrender',
              test: /node_modules[\\/]zrender[\\/]/,
              priority: 25,
            },
          ],
        },
      },
    },
  },
})
