import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // injectManifest (pas generateSW) : nécessaire pour un service worker
      // qui gère aussi les notifications push (src/sw.ts), pas seulement le
      // cache de l'app shell.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      // Le SW ne s'enregistre pas en dev par défaut (comportement normal
      // de vite-plugin-pwa) : activé ici pour pouvoir déboguer les
      // notifications push sans repasser par un build de prod à chaque fois.
      devOptions: { enabled: true, type: 'module' },
      manifest: {
        name: 'Veille Maurice',
        short_name: 'Veille Maurice',
        description: 'Veille immobilière personnelle — Nord de l\'Île Maurice',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // Les données (annonces, photos) sont mises en cache par la couche
        // d'abstraction stockage.ts (localStorage), pas par le service
        // worker : il ne précache que les fichiers de l'app shell.
        globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
      },
    }),
  ],
})
