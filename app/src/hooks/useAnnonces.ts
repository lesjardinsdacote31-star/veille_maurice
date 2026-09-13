import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { lire, ecrire } from '../lib/plateforme/stockage'
import type { Annonce } from '../types'

const CLE_CACHE = 'annonces-cache'
const LIMITE = 500

interface EtatAnnonces {
  annonces: Annonce[]
  chargement: boolean
  erreur: string | null
  horsLigne: boolean
  recharger: () => Promise<void>
}

/** Charge toutes les annonces (triées par score) une fois ; le filtrage se
 * fait ensuite côté client (voir Flux.tsx) pour que le cache hors-ligne
 * reste utilisable quel que soit le filtre actif au moment de la coupure. */
export function useAnnonces(): EtatAnnonces {
  const [annonces, setAnnonces] = useState<Annonce[]>([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState<string | null>(null)
  const [horsLigne, setHorsLigne] = useState(false)

  const recharger = useCallback(async () => {
    setChargement(true)
    setErreur(null)
    try {
      const { data, error } = await supabase
        .from('annonces')
        .select('*')
        .neq('statut', 'ecarte')
        .order('score', { ascending: false, nullsFirst: false })
        .limit(LIMITE)

      if (error) throw error

      setAnnonces(data as Annonce[])
      setHorsLigne(false)
      await ecrire(CLE_CACHE, data)
    } catch (e) {
      const cache = await lire<Annonce[]>(CLE_CACHE)
      if (cache) {
        setAnnonces(cache)
        setHorsLigne(true)
      } else {
        setErreur(e instanceof Error ? e.message : 'Erreur de chargement')
      }
    } finally {
      setChargement(false)
    }
  }, [])

  useEffect(() => {
    recharger()
  }, [recharger])

  return { annonces, chargement, erreur, horsLigne, recharger }
}
