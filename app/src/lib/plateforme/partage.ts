/**
 * Partage natif d'une annonce (feuille de partage du système).
 *
 * Couche d'abstraction : utilise l'API Web Share, avec repli copie
 * presse-papiers si absente (ex: Chrome desktop). Pour Capacitor, remplacer
 * le corps par @capacitor/share (Share.share) — même signature.
 */
export interface ContenuPartage {
  titre: string
  texte: string
  url: string
}

export async function partager(contenu: ContenuPartage): Promise<'partage' | 'copie' | 'echec'> {
  if (navigator.share) {
    try {
      await navigator.share({ title: contenu.titre, text: contenu.texte, url: contenu.url })
      return 'partage'
    } catch {
      // L'utilisateur a annulé le partage, ou l'API a échoué : on tente la copie.
    }
  }

  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(`${contenu.titre}\n${contenu.url}`)
      return 'copie'
    } catch {
      return 'echec'
    }
  }

  return 'echec'
}
