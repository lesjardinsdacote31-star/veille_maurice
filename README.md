# Veille Maurice

Application personnelle de veille immobilière pour l'Île Maurice (Nord :
Trou aux Biches, Mont Choisy, Pointe aux Canonniers, Grand Baie, Péreybère,
Bain Boeuf, Cap Malheureux). Budget 5-10 millions de roupies, maisons et
terrains constructibles, hors locations/PDS/IRS/RES/vente sur plan.

Conçue pour un coût zéro permanent (offres gratuites, pas d'essais) — voir
`.env.example` pour les garde-fous budgétaires.

## État d'avancement

- ✅ M1 — Collecte des sites vers Supabase
- ✅ M2 — Application en lecture (PWA), déployée sur Cloudflare
- ✅ M4 — Facebook, pages et groupes (Apify) (fait avant M3, Facebook
  étant la source à plus gros volume)
- ✅ **M3 — Notifications push (VAPID)** (ce jalon)
- ⬜ M5 — Boucles d'évolution (acteurs récurrents, nouveaux sites, auto-réparation, apprentissage)

## Mise en route (M1)

### 1. Créer le projet Supabase

1. [supabase.com](https://supabase.com) → New Project (plan gratuit).
2. Une fois créé, va dans **SQL Editor** et exécute, dans l'ordre, le
   contenu de chaque fichier dans `supabase/migrations/` (numéros
   croissants — chacun dépend du précédent) :
   [`0001_schema.sql`](supabase/migrations/0001_schema.sql),
   [`0002_lecture_publique.sql`](supabase/migrations/0002_lecture_publique.sql),
   [`0003_abonnements_push.sql`](supabase/migrations/0003_abonnements_push.sql).
3. Récupère dans **Project Settings > API Keys** :
   - `Project URL` → `SUPABASE_URL`
   - `Secret key` (anciennement `service_role`, ne jamais l'exposer côté
     front) → `SUPABASE_SERVICE_ROLE_KEY`
   - `Publishable key` → `VITE_SUPABASE_ANON_KEY` (utilisée par l'app,
     voir `app/.env.example`)

### 2. Créer la clé Google AI Studio (Gemini Flash)

1. [aistudio.google.com](https://aistudio.google.com) → **Get API key** → **Create API key**.
2. Choisis un projet Google Cloud existant ou nouveau, **sans jamais activer
   la facturation dessus** — l'activer supprime l'allocation gratuite au
   lieu de s'y ajouter.
3. Note le nom exact du modèle Flash actif sur le plan gratuit (visible
   dans AI Studio) → `GEMINI_MODEL` dans `.env` si différent du défaut.

### 3. Créer le compte Apify (collecte Facebook)

1. [console.apify.com](https://console.apify.com) → crée un compte (plan
   Free, 5$ de crédit gratuit renouvelé chaque mois).
2. **Settings > Integrations** → copie le **API token** → `APIFY_API_TOKEN`.
3. Aucune configuration d'acteur à faire à la main : le job appelle
   directement `apify/facebook-posts-scraper` (pages) et
   `apify/facebook-groups-scraper` (groupes), aucune connexion Facebook
   requise pour le contenu public (vérifié en conditions réelles).

### 4. Générer les clés VAPID (notifications push)

```bash
python -m scripts.generer_cles_vapid
```

**Une seule fois** — en régénérer invaliderait tous les abonnements déjà
enregistrés (chaque personne devrait réactiver les notifications). Aucun
service tiers : la clé privée sert au job Python (`pywebpush`), la clé
publique au navigateur pour créer l'abonnement.

### 5. Configurer l'environnement local

```bash
cp .env.example .env
# renseigne SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY,
# APIFY_API_TOKEN, VAPID_PRIVATE_KEY, VAPID_CONTACT_EMAIL
pip install -r requirements-dev.txt
```

### 6. Amorcer la base avec la configuration initiale

```bash
python -m scripts.migrer_config_vers_supabase
```

Migre `config/config_initiale.yaml` (secteurs, critères, 11 sites, 23 pages
et 39 groupes Facebook) vers Supabase. À relancer seulement si ce fichier
est modifié à la main — l'usage courant passe par l'écran d'administration
de l'app (à venir en M5).

### 7. Vérifier que tout tourne

```bash
pytest -v                        # tests unitaires (normalisation, dédup, fréquence, Facebook, notifications...)
python -m collecte.main --test   # collecte réelle, sans rien écrire ni envoyer
```

### 8. Secrets GitHub Actions (dépôt privé)

Dans **Settings > Secrets and variables > Actions** du dépôt :
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`,
`APIFY_API_TOKEN`, `VAPID_PRIVATE_KEY` (le bloc PEM complet,
BEGIN/END inclus), `VAPID_CONTACT_EMAIL`.

Le workflow [`collecte.yml`](.github/workflows/collecte.yml) tourne
3x/jour (08:00, 13:00, 20:00 heure de Maurice) et peut être lancé
manuellement (**Actions > Collecte immobilière > Run workflow**), avec une
option `mode_test`.

### 9. Déployer l'application (Cloudflare)

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Compute (Workers & Pages)**
   → **Workers & Pages** → connecte le dépôt GitHub (dépôts privés
   supportés).
2. Réglages de build : **Root directory** = `app`, **Build command** =
   `npm run build` (le fichier [`app/wrangler.jsonc`](app/wrangler.jsonc)
   fixe le reste — sans lui, Cloudflare déduit un répertoire de sortie
   incorrect et déploie les fichiers source au lieu du build).
3. **Settings > Builds > Variables and secrets** (variables de *build*,
   pas les "Variables and secrets" du Worker à l'exécution) :
   `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (la clé publishable, pas
   la clé secrète), `VITE_VAPID_PUBLIC_KEY` (la ligne publique générée à
   l'étape 4, pas le bloc PEM privé).
4. Déploie. L'app est servie sur `<nom>.<compte>.workers.dev`, installable
   comme PWA depuis Chrome Android.
5. Sur ton téléphone, ouvre l'app installée et appuie sur la cloche 🔕 en
   haut à droite pour activer les notifications (une seule fois par
   appareil).

## Points d'attention

- **Notifications testées uniquement côté génération de message et build**,
  pas le flux d'autorisation navigateur de bout en bout — l'environnement
  automatisé utilisé pour développer refuse les permissions de
  notification par défaut (restriction de sécurité du bac à sable),
  impossible à contourner depuis ce contexte. **Teste toi-même sur ton
  téléphone** une fois déployé (cloche 🔕 dans l'app) avant de considérer
  M3 pleinement validé.
- **Une notification par nouvelle annonce**, pas de regroupement — sur un
  run qui trouve plusieurs annonces d'un coup (rare vu le volume actuel),
  tu recevras plusieurs notifications successives. À revoir si le volume
  augmente sensiblement (regroupement en une seule notification "X
  nouvelles annonces").
- **Se désabonner depuis l'app ne supprime pas la ligne dans
  `abonnements_push`** (la clé publique n'a que le droit d'insertion, pas
  de suppression, par choix RLS) — elle se désactive automatiquement au
  prochain envoi échoué (réponse 404/410), pas immédiatement.
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
- **Incident de coût Apify (13 sept. 2026) : ~9$ des 10$ de crédit gratuit
  consommés en un seul passage réel.** Cause : l'architecture initiale
  lançait un acteur Apify par source (un par groupe/page Facebook), or
  Apify facture ces acteurs un **forfait fixe par lancement (~0,076$,
  mesuré via `/v2/actor-runs`), quasi indépendant du nombre de résultats
  rendus** — la tarification théorique "$/1000 posts" ne s'applique pas
  en pratique à ces acteurs. Avec ~60 sources Facebook, un seul passage
  = ~60 lancements = ~4,50$, et 2 passages ont suffi à épuiser le budget.
  **Corrigé** en regroupant toutes les sources d'un même type (pages OU
  groupes) dans un seul lancement Apify (`startUrls` multiples) —
  `resultsLimit` a été vérifié comme s'appliquant par URL et non
  globalement (2 URLs, resultsLimit=6 → 6 résultats par URL), donc
  regrouper N sources coûte le même forfait unique tout en retournant
  les mêmes résultats par source qu'un lancement individuel. Voir
  `collecte/sources_facebook.py` (`collecter_facebook_groupe`).
- **Budget Apify plafonné à 55 lancements/mois**
  (`PLAFOND_APIFY_LANCEMENTS_MENSUEL` dans `collecte/main.py`, unité =
  un lancement Apify groupé, pas un post) : 2 lancements/jour (1 pages +
  1 groupes) × 30 jours = 60, sous les ~65 lancements que couvrent les
  5$ gratuits mensuels au tarif réel de ~0,076$/lancement — marge de
  sécurité volontaire. Facebook n'est déclenché qu'une fois par jour
  (`COLLECTER_FACEBOOK`, voir `.github/workflows/collecte.yml`) pour ne
  jamais dépasser ce rythme. Le plafond est vérifié *avant* chaque appel
  Apify (jamais dépassé) et ne bloque jamais la collecte des sites. Le
  compteur (`compteurs_usage`, service `apify`) se remet à zéro chaque
  mois (nouvelle ligne par `periode`) ; il n'y a pas de carte bancaire
  liée au compte Apify, donc pas de risque de facturation au-delà du
  crédit gratuit — au pire la collecte Facebook du mois s'arrête.
- **Fréquence différenciée par priorité pour les groupes Facebook**
  (`sources.frequence` en base : `chaque_run` / `quotidien` /
  `hebdomadaire` / `manuel`, voir `collecte/frequence.py`) — les groupes
  généralistes à fort bruit (Priorité 4) ne sont vérifiés qu'une fois par
  semaine, les groupes ciblés (Priorité 1 et 3) à chaque passage. Chaque
  collecte ne redemande que les posts publiés depuis le dernier passage
  réussi sur cette source précise (`onlyPostsNewerThan`), pas une limite
  fixe — un groupe calme ne coûte presque rien entre deux passages.
- **3 groupes Facebook privés restent inactifs** (`sources.prive = true`) :
  nécessitent une adhésion + cookies de session, jamais mis en place
  (décision volontaire, voir historique du projet). Aucune action requise
  tant que tu ne demandes pas de les activer.
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
collecte/            pipeline Python (normalisation, dédup, extraction, notation,
                      stockage, sources_sites, sources_facebook, frequence, notifications)
app/                  PWA React + Vite + TS, déployée sur Cloudflare (app/CAPACITOR.md
                      documente la bascule future vers un APK). src/lib/plateforme/
                      = couche d'abstraction (liens, partage, stockage, notifications).
                      src/sw.ts = service worker personnalisé (précache + push).
config/               config_initiale.yaml — source de vérité migrée vers Supabase
supabase/migrations/  schéma SQL (appliquer dans l'ordre des numéros)
scripts/               migration de la config vers Supabase
tests/                tests unitaires (prix, perches, téléphones, dédup, fréquence,
                      conversion des posts Facebook, message de notification)
.github/workflows/    collecte planifiée + tests CI
```
