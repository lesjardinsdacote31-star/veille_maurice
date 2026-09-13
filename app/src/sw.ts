/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching'

declare let self: ServiceWorkerGlobalScope

// Injecté au build par vite-plugin-pwa (strategy: injectManifest).
precacheAndRoute(self.__WB_MANIFEST)

self.skipWaiting()

interface DonneesNotification {
  titre?: string
  corps?: string
  url?: string
}

self.addEventListener('push', (event: PushEvent) => {
  let donnees: DonneesNotification = {}
  try {
    donnees = event.data?.json() ?? {}
  } catch {
    donnees = { corps: event.data?.text() }
  }

  event.waitUntil(
    self.registration.showNotification(donnees.titre ?? 'Veille Maurice', {
      body: donnees.corps ?? '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: donnees.url ?? '/' },
    })
  )
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const url = (event.notification.data?.url as string) ?? '/'

  event.waitUntil(
    (async () => {
      const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const dejaOuvert = clientsList.find((c) => 'focus' in c) as WindowClient | undefined
      if (dejaOuvert) {
        await dejaOuvert.focus()
        dejaOuvert.postMessage({ type: 'naviguer', url })
      } else {
        await self.clients.openWindow(url)
      }
    })()
  )
})
