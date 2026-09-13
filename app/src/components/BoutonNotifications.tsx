import { useEffect, useState } from 'react'
import {
  abonnerNotifications,
  desabonnerNotifications,
  etatNotifications,
  type EtatNotifications,
} from '../lib/plateforme/notifications'

const CLE_VAPID_PUBLIQUE = import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined

export function BoutonNotifications() {
  const [etat, setEtat] = useState<EtatNotifications>('inactif')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    etatNotifications().then(setEtat)
  }, [])

  if (etat === 'non-supporte' || !CLE_VAPID_PUBLIQUE) return null

  async function basculer() {
    setEnCours(true)
    try {
      if (etat === 'actif') {
        await desabonnerNotifications()
        setEtat('inactif')
      } else {
        const nouvelEtat = await abonnerNotifications(CLE_VAPID_PUBLIQUE!)
        setEtat(nouvelEtat)
      }
    } finally {
      setEnCours(false)
    }
  }

  const libelle =
    etat === 'actif' ? 'Notifications activées' : etat === 'refuse' ? 'Notifications bloquées' : 'Activer les notifications'

  return (
    <button
      onClick={basculer}
      disabled={enCours || etat === 'refuse'}
      aria-label={libelle}
      title={libelle}
      className={`shrink-0 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50 ${
        etat === 'actif' ? 'bg-emerald-700 text-white' : 'bg-slate-800 text-slate-100'
      }`}
    >
      {etat === 'actif' ? '🔔' : '🔕'}
    </button>
  )
}
