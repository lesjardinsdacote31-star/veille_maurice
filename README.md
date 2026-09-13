# Veille Maurice

Application personnelle de veille immobilière pour l'Île Maurice (Nord :
Trou aux Biches, Mont Choisy, Pointe aux Canonniers, Grand Baie, Péreybère,
Bain Boeuf, Cap Malheureux). Budget 5-10 millions de roupies, maisons et
terrains constructibles, hors locations/PDS/IRS/RES/vente sur plan.

Conçue pour un coût zéro permanent (offres gratuites, pas d'essais) — voir
`.env.example` pour les garde-fous budgétaires.

## État d'avancement

- ✅ **M1 — Collecte des sites vers Supabase** (ce jalon)
- ⬜ M2 — Application en lecture (PWA)
- ⬜ M3 — Notifications push
- ⬜ M4 — Facebook (Apify)
- ⬜ M5 — Boucles d'évolution (acteurs récurrents, nouveaux sites, auto-réparation, apprentissage)

## Mise en route (M1)

### 1. Créer le projet Supabase

1. [supabase.com](https://supabase.com) → New Project (plan gratuit).
2. Une fois créé, va dans **SQL Editor** et exécute le contenu de
   [`supabase/migrations/0001_schema.sql`](supabase/migrations/0001_schema.sql).
3. Récupère dans **Project Settings > API** :
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key (secrète, ne jamais l'exposer côté front) → `SUPABASE_SERVICE_ROLE_KEY`

### 2. Créer la clé Google AI Studio (Gemini Flash)

1. [aistudio.google.com](https://aistudio.google.com) → **Get API key** → **Create API key**.
2. Choisis un projet Google Cloud existant ou nouveau, **sans jamais activer
   la facturation dessus** — l'activer supprime l'allocation gratuite au
   lieu de s'y ajouter.
3. Note le nom exact du modèle Flash actif sur le plan gratuit (visible
   dans AI Studio) → `GEMINI_MODEL` dans `.env` si différent du défaut.

### 3. Configurer l'environnement local

```bash
cp .env.example .env
# renseigne SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY
pip install -r requirements-dev.txt
```

### 4. Amorcer la base avec la configuration initiale

```bash
python -m scripts.migrer_config_vers_supabase
```

Migre `config/config_initiale.yaml` (secteurs, critères, 11 sites, 23 pages
et 39 groupes Facebook) vers Supabase. À relancer seulement si ce fichier
est modifié à la main — l'usage courant passe par l'écran d'administration
de l'app (à venir en M5).

### 5. Vérifier que tout tourne

```bash
pytest -v                        # tests de normalisation et de dédup
python -m collecte.main --test   # collecte réelle, sans rien écrire ni envoyer
```

### 6. Secrets GitHub Actions (dépôt privé)

Dans **Settings > Secrets and variables > Actions** du dépôt :
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`.

Le workflow [`collecte.yml`](.github/workflows/collecte.yml) tourne
3x/jour (08:00, 13:00, 20:00 heure de Maurice) et peut être lancé
manuellement (**Actions > Collecte immobilière > Run workflow**), avec une
option `mode_test`.

## Points d'attention

- **Sources à valider avant le premier run réel** : `config_initiale.yaml`
  pointe la plupart des sites vers leur page d'accueil, pas leur page de
  recherche/liste réelle. Seul lexpressproperty.com a été vérifié en
  direct (`/en/buy-mauritius/`, rendu HTML côté serveur, compatible httpx).
  Corrige `identifiant` dans le YAML (ou directement en base une fois
  migré) pour chaque site avant de compter sur sa collecte.
- **propertycloud.mu** est protégé par un défi anti-bot Cloudflare qui
  bloque même un navigateur automatisé standard — attends-toi à des
  échecs récurrents sur cette source tant qu'une solution n'est pas
  trouvée (proxy résidentiel payant, API alternative...). Le job continue
  normalement sur les autres sources (isolation des échecs par source).
- **Numéros de téléphone dans le HTML** : sur au moins un site testé, le
  numéro n'apparaît pas dans le texte visible mais dans un attribut HTML
  (`data-whatsappsend="230..."`) — l'extraction scanne donc aussi le HTML
  brut, pas seulement le texte affiché.
- **Idempotence plutôt que rattrapage dédié** : un run manqué (panne
  GitHub Actions, etc.) se rattrape tout seul au run suivant — l'upsert
  sur `(source_id, url)` et la clé de dédup téléphone+prix rendent la
  collecte naturellement rejouable sans état à réconcilier.

## Structure du projet

```
collecte/           pipeline Python (normalisation, dédup, extraction, notation, stockage)
config/              config_initiale.yaml — source de vérité migrée vers Supabase
supabase/migrations/ schéma SQL
scripts/             migration de la config vers Supabase
tests/               tests unitaires (prix, perches, téléphones, dédup)
.github/workflows/   collecte planifiée + tests CI
```
