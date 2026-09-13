/**
 * Ouverture de liens externes (annonce d'origine, WhatsApp, appel, itinéraire).
 *
 * Couche d'abstraction : le reste de l'app n'appelle jamais window.open()
 * directement. Pour basculer vers Capacitor plus tard, remplacer le corps
 * de ouvrirLienExterne par un appel à @capacitor/browser (Browser.open)
 * sans toucher au code appelant — voir CAPACITOR.md.
 */
export async function ouvrirLienExterne(url: string): Promise<void> {
  window.open(url, '_blank', 'noopener,noreferrer')
}

export function urlWhatsApp(telephone: string, message: string): string {
  const numero = telephone.replace(/\D/g, '')
  return `https://wa.me/${numero}?text=${encodeURIComponent(message)}`
}

export function urlAppel(telephone: string): string {
  return `tel:+${telephone.replace(/\D/g, '')}`
}

export function urlItineraire(latitude: number, longitude: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`
}
