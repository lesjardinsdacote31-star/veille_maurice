import { Link } from 'react-router-dom'
import type { Annonce } from '../types'
import { formaterPrix, formaterSurface, LIBELLES_TYPE_BIEN } from '../lib/format'
import { BadgeScore } from './BadgeScore'

interface Props {
  annonce: Annonce
  nomSecteur: string | null
}

export function CarteAnnonce({ annonce, nomSecteur }: Props) {
  const surface = formaterSurface(annonce.surface_terrain_perches)

  return (
    <Link
      to={`/annonce/${annonce.id}`}
      className="flex gap-3 rounded-xl bg-slate-800 p-3 active:bg-slate-700"
    >
      <div className="h-24 w-24 shrink-0 overflow-hidden rounded-lg bg-slate-700">
        {annonce.photos[0] ? (
          <img
            src={annonce.photos[0]}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-2xl">🏝️</div>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col justify-between py-0.5">
        <div>
          <p className="truncate text-base font-medium text-slate-50">
            {annonce.titre ?? 'Annonce sans titre'}
          </p>
          <p className="mt-0.5 text-sm text-slate-300">
            {nomSecteur ?? 'Secteur inconnu'}
            {annonce.type_bien && ` · ${LIBELLES_TYPE_BIEN[annonce.type_bien]}`}
            {surface && ` · ${surface}`}
          </p>
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-base font-semibold text-slate-50">
            {formaterPrix(annonce.prix_roupies)}
          </span>
          <BadgeScore score={annonce.score} />
        </div>
      </div>
    </Link>
  )
}
