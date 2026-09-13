export function formaterPrix(roupies: number | null): string {
  if (roupies === null) return 'Prix non détecté'
  return new Intl.NumberFormat('fr-FR').format(roupies) + ' Rs'
}

export function formaterSurface(perches: number | null): string | null {
  if (perches === null) return null
  return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(perches)} perches`
}

export function formaterDateRelative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const heures = Math.floor(diffMs / 3_600_000)
  if (heures < 1) return "à l'instant"
  if (heures < 24) return `il y a ${heures} h`
  const jours = Math.floor(heures / 24)
  if (jours === 1) return 'hier'
  if (jours < 7) return `il y a ${jours} j`
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(
    new Date(iso)
  )
}

export const LIBELLES_STATUT: Record<string, string> = {
  nouveau: 'Nouveau',
  vu: 'Vu',
  contacte: 'Contacté',
  visite: 'Visité',
  ecarte: 'Écarté',
}

export const LIBELLES_TYPE_BIEN: Record<string, string> = {
  maison: 'Maison',
  terrain: 'Terrain',
  autre: 'Autre',
}
