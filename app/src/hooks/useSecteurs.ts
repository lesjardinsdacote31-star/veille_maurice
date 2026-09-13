import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { lire, ecrire } from '../lib/plateforme/stockage'
import type { Secteur } from '../types'

const CLE_CACHE = 'secteurs-cache'

export function useSecteurs(): Secteur[] {
  const [secteurs, setSecteurs] = useState<Secteur[]>([])

  useEffect(() => {
    let annule = false
    ;(async () => {
      const { data, error } = await supabase.from('secteurs').select('*').eq('actif', true)
      if (!annule && !error && data) {
        setSecteurs(data as Secteur[])
        await ecrire(CLE_CACHE, data)
      } else if (!annule) {
        const cache = await lire<Secteur[]>(CLE_CACHE)
        if (cache) setSecteurs(cache)
      }
    })()
    return () => {
      annule = true
    }
  }, [])

  return secteurs
}
