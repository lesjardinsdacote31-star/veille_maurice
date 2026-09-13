import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { lire } from '../lib/plateforme/stockage'
import { ouvrirLienExterne, urlAppel, urlItineraire, urlWhatsApp } from '../lib/plateforme/liens'
import { partager } from '../lib/plateforme/partage'
import { formaterPrix, formaterSurface, LIBELLES_TYPE_BIEN } from '../lib/format'
import { useSecteurs } from '../hooks/useSecteurs'
import { BadgeScore } from '../components/BadgeScore'
import type { Annonce } from '../types'

export function FicheAnnonce() {
  const { id } = useParams<{ id: string }>()
  const secteurs = useSecteurs()
  const [annonce, setAnnonce] = useState<Annonce | null>(null)
  const [chargement, setChargement] = useState(true)
  const [introuvable, setIntrouvable] = useState(false)

  useEffect(() => {
    if (!id) return
    let annule = false
    ;(async () => {
      const { data, error } = await supabase.from('annonces').select('*').eq('id', id).single()
      if (annule) return
      if (!error && data) {
        setAnnonce(data as Annonce)
      } else {
        const cache = await lire<Annonce[]>('annonces-cache')
        const trouvee = cache?.find((a) => a.id === id) ?? null
        if (trouvee) setAnnonce(trouvee)
        else setIntrouvable(true)
      }
      setChargement(false)
    })()
    return () => {
      annule = true
    }
  }, [id])

  if (chargement) {
    return <p className="p-6 text-center text-slate-400">Chargement…</p>
  }

  if (introuvable || !annonce) {
    return (
      <div className="p-6 text-center text-slate-400">
        <p>Annonce introuvable.</p>
        <Link to="/" className="mt-2 inline-block text-cyan-400">
          Retour au flux
        </Link>
      </div>
    )
  }

  const nomSecteur = secteurs.find((s) => s.id === annonce.secteur_id)?.nom ?? annonce.secteur_id
  const telephone = annonce.telephones[0]
  const messagePreRempli = `Bonjour, je vous contacte au sujet de votre annonce "${annonce.titre}" (${formaterPrix(annonce.prix_roupies)}).`

  return (
    <div className="min-h-full bg-slate-900 pb-28 text-slate-100">
      <header className="sticky top-0 z-10 flex items-center gap-3 bg-slate-900/95 px-4 py-3 backdrop-blur">
        <Link to="/" className="text-2xl leading-none">
          ←
        </Link>
        <h1 className="truncate text-lg font-medium">{annonce.titre ?? 'Annonce'}</h1>
      </header>

      {annonce.photos.length > 0 ? (
        <div className="flex gap-1 overflow-x-auto px-4">
          {annonce.photos.map((photo, i) => (
            <img
              key={i}
              src={photo}
              alt=""
              className="h-56 w-72 shrink-0 rounded-xl object-cover"
              loading="lazy"
            />
          ))}
        </div>
      ) : (
        <div className="mx-4 flex h-40 items-center justify-center rounded-xl bg-slate-800 text-4xl">
          🏝️
        </div>
      )}

      <div className="space-y-4 px-4 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-2xl font-semibold">{formaterPrix(annonce.prix_roupies)}</p>
            <p className="mt-1 text-slate-300">
              {nomSecteur}
              {annonce.type_bien && ` · ${LIBELLES_TYPE_BIEN[annonce.type_bien]}`}
            </p>
          </div>
          <BadgeScore score={annonce.score} />
        </div>

        {annonce.resume && (
          <div className="rounded-xl bg-slate-800 p-3">
            <p className="text-sm font-medium text-slate-400">Résumé</p>
            <p className="mt-1 text-slate-100">{annonce.resume}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-3 text-sm text-slate-300">
          {formaterSurface(annonce.surface_terrain_perches) && (
            <span>📐 {formaterSurface(annonce.surface_terrain_perches)}</span>
          )}
          {annonce.chambres !== null && annonce.type_bien !== 'terrain' && (
            <span>🛏️ {annonce.chambres} chambre(s)</span>
          )}
          {annonce.distance_plage_estimee_km !== null && (
            <span>🏖️ ~{annonce.distance_plage_estimee_km} km de la plage</span>
          )}
          {annonce.localisation_texte && <span>📍 {annonce.localisation_texte}</span>}
        </div>

        {annonce.drapeaux.length > 0 && (
          <div className="rounded-xl bg-amber-950 p-3">
            <p className="text-sm font-medium text-amber-400">Points de vigilance</p>
            <ul className="mt-1 list-inside list-disc text-amber-200">
              {annonce.drapeaux.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </div>
        )}

        {annonce.description_brute && (
          <details className="rounded-xl bg-slate-800 p-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-400">
              Texte brut de l'annonce
            </summary>
            <p className="mt-2 whitespace-pre-line text-sm text-slate-300">
              {annonce.description_brute}
            </p>
          </details>
        )}
      </div>

      <div className="fixed inset-x-0 bottom-0 grid grid-cols-2 gap-2 border-t border-slate-800 bg-slate-900 p-3 sm:grid-cols-4">
        <button
          disabled={!telephone}
          onClick={() => ouvrirLienExterne(urlWhatsApp(telephone!, messagePreRempli))}
          className="rounded-xl bg-emerald-600 py-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          WhatsApp
        </button>
        <button
          disabled={!telephone}
          onClick={() => ouvrirLienExterne(urlAppel(telephone!))}
          className="rounded-xl bg-slate-700 py-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          Appeler
        </button>
        <button
          disabled={annonce.latitude === null || annonce.longitude === null}
          onClick={() => ouvrirLienExterne(urlItineraire(annonce.latitude!, annonce.longitude!))}
          className="rounded-xl bg-slate-700 py-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          Itinéraire
        </button>
        <button
          onClick={() => ouvrirLienExterne(annonce.url)}
          className="rounded-xl bg-slate-700 py-3 text-sm font-semibold text-white"
        >
          Annonce d'origine
        </button>
      </div>

      <button
        onClick={() =>
          partager({ titre: annonce.titre ?? 'Annonce', texte: formaterPrix(annonce.prix_roupies), url: annonce.url })
        }
        className="fixed right-3 z-10 rounded-full bg-slate-700 p-3 text-lg shadow-lg"
        style={{ bottom: '5.5rem' }}
        aria-label="Partager"
      >
        ↗️
      </button>
    </div>
  )
}
