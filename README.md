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

- **Quota Gemini gratuit très variable selon le modèle — à surveiller.**
  Vérifié en direct (sept. 2026) : le modèle complet `gemini-3.6-flash`
  est limité à **20 requêtes/jour** sur le plan gratuit, largement
  insuffisant pour 3 collectes/jour dès que le volume d'annonces
  retenues augmente (ce qui arrivera avec Facebook, M4). Le modèle par
  défaut est maintenant `gemini-3.5-flash-lite` (quota normalement bien
  plus généreux pour les variantes "Lite", non re-mesuré précisément
  pour ne pas épuiser le quota du jour en testant). **Vérifie le quota
  réel dans AI Studio** et ajuste `GEMINI_MODEL` si besoin — ce
  paysage change vite, ne fais pas confiance à ce README dans 6 mois
  sans revérifier. Quand le quota est atteint, l'annonce est conservée
  sans score plutôt que perdue (voir `collecte/gemini_client.py`).
- **3 sites sur 11 bloqués par un défi anti-bot Cloudflare** :
  lexpressproperty.com, propertycloud.mu, propertymap.mu. Un `httpx.get()`
  simple ne peut pas résoudre leur défi JS, contrairement à un navigateur
  complet. Pas de solution gratuite identifiée pour l'instant — le job
  continue normalement sur les autres sources (isolation des échecs par
  source), donc pas d'impact au-delà de ces 3 sites.
- **2 sites non résolus malgré une recherche superficielle** :
  Green-Acres Maurice (organisé par grande région, pas de page couvrant
  directement nos 7 secteurs trouvée) et Decordier Immobilier (sa page
  `/sale/` ne remonte que des liens YouTube). Faible priorité, à
  revisiter si besoin — voir les commentaires dans `config_initiale.yaml`.
- **Numéros de téléphone dans le HTML** : sur au moins un site testé, le
  numéro n'apparaît pas dans le texte visible mais dans un attribut HTML
  (`data-whatsappsend="230..."`) — l'extraction scanne donc aussi le HTML
  brut, pas seulement le texte affiché.
- **Idempotence plutôt que rattrapage dédié** : un run manqué (panne
  GitHub Actions, etc.) se rattrape tout seul au run suivant — l'upsert
  sur `(source_id, url)` et la clé de dédup téléphone+prix rendent la
  collecte naturellement rejouable sans état à réconcilier.
- **Changer l'`identifiant` d'une source existante dans le YAML** crée une
  nouvelle ligne en base au lieu de mettre à jour l'ancienne (l'upsert se
  fait sur `(type, identifiant)`) — désactive l'ancienne ligne à la main
  après migration. Voir le commentaire en tête de
  `scripts/migrer_config_vers_supabase.py`.

## Structure du projet

```
collecte/           pipeline Python (normalisation, dédup, extraction, notation, stockage)
config/              config_initiale.yaml — source de vérité migrée vers Supabase
supabase/migrations/ schéma SQL
scripts/             migration de la config vers Supabase
tests/               tests unitaires (prix, perches, téléphones, dédup)
.github/workflows/   collecte planifiée + tests CI
```
