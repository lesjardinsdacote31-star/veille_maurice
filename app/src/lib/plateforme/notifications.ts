/**
 * Abonnement aux notifications push (nouvelle annonce détectée par la
 * collecte).
 *
 * Couche d'abstraction : implémentation web via l'API Push + Service
 * Worker. Pour Capacitor, remplacer par @capacitor/push-notifications +
 * Firebase Cloud Messaging (même signature abonnerNotifications/
 * desabonnerNotifications) — voir CAPACITOR.md. Le job Python devra alors
 * aussi changer (collecte/notifications.py), les deux bouts de
 * l'abstraction évoluant ensemble.
 */
import { supabase } from '../supabase'

export type EtatNotifications = 'non-supporte' | 'refuse' | 'inactif' | 'actif'

function urlBase64VersOctets(base64Url: string): ArrayBuffer {
  const base64 = (base64Url + '='.repeat((4 - (base64Url.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const brut = atob(base64)
  const octets = new Uint8Array(brut.length)
  for (let i = 0; i < brut.length; i++) octets[i] = brut.charCodeAt(i)
  return octets.buffer
}

export function notificationsSupportees(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export async function etatNotifications(): Promise<EtatNotifications> {
  if (!notificationsSupportees()) return 'non-supporte'
  if (Notification.permission === 'denied') return 'refuse'

  const registration = await navigator.serviceWorker.ready
  const abonnement = await registration.pushManager.getSubscription()
  return abonnement ? 'actif' : 'inactif'
}

export async function abonnerNotifications(cleVapidPublique: string): Promise<EtatNotifications> {
  if (!notificationsSupportees()) return 'non-supporte'

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return 'refuse'

  const registration = await navigator.serviceWorker.ready
  let abonnement = await registration.pushManager.getSubscription()
  if (!abonnement) {
    abonnement = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64VersOctets(cleVapidPublique),
    })
  }

  const json = abonnement.toJSON()
  await supabase.from('abonnements_push').insert({
    endpoint: json.endpoint,
    clefs: json.keys,
  })

  return 'actif'
}

export async function desabonnerNotifications(): Promise<void> {
  if (!notificationsSupportees()) return
  const registration = await navigator.serviceWorker.ready
  const abonnement = await registration.pushManager.getSubscription()
  await abonnement?.unsubscribe()
  // La ligne côté Supabase reste (RLS n'autorise pas la suppression depuis
  // le navigateur) : elle sera désactivée automatiquement au prochain envoi
  // échoué (404/410), voir collecte/notifications.py.
}
