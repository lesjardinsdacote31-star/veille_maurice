/**
 * Stockage local persistant (cache des annonces déjà chargées pour lecture
 * hors-ligne, préférences d'affichage).
 *
 * Couche d'abstraction : implémentation web via localStorage. Pour
 * Capacitor, remplacer par @capacitor/preferences (même signature
 * async get/set/supprimer) — voir CAPACITOR.md.
 */
const PREFIXE = 'veille-maurice:'

export async function lire<T>(cle: string): Promise<T | null> {
  try {
    const brut = localStorage.getItem(PREFIXE + cle)
    return brut ? (JSON.parse(brut) as T) : null
  } catch {
    return null
  }
}

export async function ecrire<T>(cle: string, valeur: T): Promise<void> {
  try {
    localStorage.setItem(PREFIXE + cle, JSON.stringify(valeur))
  } catch {
    // Quota dépassé ou stockage indisponible (navigation privée) : on
    // dégrade silencieusement, l'app reste utilisable sans cache.
  }
}

export async function supprimer(cle: string): Promise<void> {
  try {
    localStorage.removeItem(PREFIXE + cle)
  } catch {
    // ignoré, voir ecrire()
  }
}
