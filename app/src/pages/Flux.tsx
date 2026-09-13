import { useMemo, useState } from 'react'
import { useAnnonces } from '../hooks/useAnnonces'
import { useSecteurs } from '../hooks/useSecteurs'
import { CarteAnnonce } from '../components/CarteAnnonce'
import { LIBELLES_STATUT, LIBELLES_TYPE_BIEN } from '../lib/format'

export function Flux() {
  const { annonces, chargement, erreur, horsLigne, recharger } = useAnnonces()
  const secteurs = useSecteurs()

  const [secteurId, setSecteurId] = useState('')
  const [typeBien, setTypeBien] = useState('')
  const [statut, setStatut] = useState('')

  const nomSecteurParId = useMemo(() => {
    const carte = new Map(secteurs.map((s) => [s.id, s.nom]))
    return (id: string | null) => (id ? (carte.get(id) ?? id) : null)
  }, [secteurs])

  const annoncesFiltrees = useMemo(() => {
    return annonces.filter((a) => {
      if (secteurId && a.secteur_id !== secteurId) return false
      if (typeBien && a.type_bien !== typeBien) return false
      if (statut && a.statut !== statut) return false
      return true
    })
  }, [annonces, secteurId, typeBien, statut])

  return (
    <div className="flex min-h-full flex-col bg-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900/95 px-4 pb-3 pt-4 backdrop-blur">
        <h1 className="text-xl font-semibold text-slate-50">Veille Maurice</h1>
        {horsLigne && (
          <p className="mt-1 text-sm text-amber-400">Hors ligne — dernières données chargées</p>
        )}
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          <select
            value={secteurId}
            onChange={(e) => setSecteurId(e.target.value)}
            className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            <option value="">Tous secteurs</option>
            {secteurs.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nom}
              </option>
            ))}
          </select>
          <select
            value={typeBien}
            onChange={(e) => setTypeBien(e.target.value)}
            className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            <option value="">Tous types</option>
            {Object.entries(LIBELLES_TYPE_BIEN).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
          <select
            value={statut}
            onChange={(e) => setStatut(e.target.value)}
            className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            <option value="">Tous statuts</option>
            {Object.entries(LIBELLES_STATUT).map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>
                {libelle}
              </option>
            ))}
          </select>
        </div>
      </header>

      <main className="flex-1 px-4 py-3">
        {chargement && annonces.length === 0 && (
          <p className="py-10 text-center text-slate-400">Chargement…</p>
        )}

        {erreur && (
          <div className="rounded-lg bg-red-950 p-4 text-red-200">
            <p>Impossible de charger les annonces : {erreur}</p>
            <button
              onClick={() => recharger()}
              className="mt-2 rounded-lg bg-red-800 px-3 py-1.5 text-sm font-medium"
            >
              Réessayer
            </button>
          </div>
        )}

        {!chargement && !erreur && annoncesFiltrees.length === 0 && (
          <p className="py-10 text-center text-slate-400">Aucune annonce ne correspond.</p>
        )}

        <div className="flex flex-col gap-2">
          {annoncesFiltrees.map((annonce) => (
            <CarteAnnonce
              key={annonce.id}
              annonce={annonce}
              nomSecteur={nomSecteurParId(annonce.secteur_id)}
            />
          ))}
        </div>
      </main>
    </div>
  )
}
