import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const cle = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !cle) {
  throw new Error(
    'VITE_SUPABASE_URL et VITE_SUPABASE_ANON_KEY doivent être définies (voir app/.env.example).'
  )
}

// Clé publique (publishable/anon) uniquement : la lecture est autorisée par
// les policies RLS de la base (voir supabase/migrations/0002_lecture_publique.sql),
// jamais la clé secrète, qui ne doit exister que côté job de collecte.
export const supabase = createClient(url, cle)
