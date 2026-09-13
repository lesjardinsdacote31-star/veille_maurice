export type StatutAnnonce = 'nouveau' | 'vu' | 'contacte' | 'visite' | 'ecarte'
export type TypeBien = 'maison' | 'terrain' | 'autre'
export type VendeurType = 'particulier' | 'agence' | 'inconnu'

export interface Annonce {
  id: string
  source_id: string
  url: string
  titre: string | null
  description_brute: string | null
  prix_roupies: number | null
  secteur_id: string | null
  localisation_texte: string | null
  type_bien: TypeBien | null
  chambres: number | null
  surface_terrain_perches: number | null
  surface_batie_m2: number | null
  telephones: string[]
  photos: string[]
  latitude: number | null
  longitude: number | null
  distance_plage_estimee_km: number | null
  score: number | null
  resume: string | null
  drapeaux: string[]
  vendeur_type: VendeurType | null
  statut: StatutAnnonce
  decouverte_le: string
  envoyee_le: string | null
  derniere_maj: string
}

export interface Secteur {
  id: string
  nom: string
  alias: string[]
  actif: boolean
}
