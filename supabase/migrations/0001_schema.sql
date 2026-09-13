-- Schéma initial — veille immobilière Île Maurice
-- Convention : tout est en français (tables, colonnes), timestamps en UTC.

create extension if not exists pg_trgm;

-- ---------------------------------------------------------------------------
-- Paramètres globaux (remplace la partie "critères" de config.yaml)
-- ---------------------------------------------------------------------------
create table parametres (
    cle text primary key,
    valeur jsonb not null,
    maj_le timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Secteurs surveillés (les 7 zones du Nord + alias pour la détection texte)
-- ---------------------------------------------------------------------------
create table secteurs (
    id text primary key,               -- slug, ex: 'grand_baie'
    nom text not null,                 -- ex: 'Grand Baie'
    alias text[] not null default '{}',
    actif boolean not null default true
);

-- ---------------------------------------------------------------------------
-- Sources (sites, pages Facebook, groupes Facebook)
-- ---------------------------------------------------------------------------
create table sources (
    id uuid primary key default gen_random_uuid(),
    type text not null check (type in ('site', 'page_facebook', 'groupe_facebook')),
    identifiant text not null,         -- URL du site, ou URL/ID de la page ou du groupe
    nom text not null,
    priorite smallint not null default 2,   -- 1 = prioritaire, 2 = normal, 3 = faible
    frequence text not null default 'chaque_run'
        check (frequence in ('chaque_run', 'quotidien', 'hebdomadaire', 'manuel')),
    prive boolean not null default false,   -- groupe Facebook privé : nécessite connexion, inactif tant que non résolu
    config_extraction jsonb not null default '{}',
    active boolean not null default true,
    derniere_collecte_le timestamptz,
    derniere_collecte_ok boolean,
    derniere_collecte_nb_resultats integer,
    echecs_consecutifs integer not null default 0,
    cree_le timestamptz not null default now(),
    notes text,
    unique (type, identifiant)
);

create index idx_sources_actives on sources (type, active) where active;

-- ---------------------------------------------------------------------------
-- File d'attente des sources découvertes automatiquement, en attente de validation
-- ---------------------------------------------------------------------------
create table sources_proposees (
    id uuid primary key default gen_random_uuid(),
    type text not null check (type in ('site', 'page_facebook', 'groupe_facebook')),
    identifiant text not null,
    nom text,
    raison text not null,   -- 'acteur_recurrent' | 'recherche_google' | 'auto_reparation' | 'manuel'
    donnees jsonb not null default '{}',   -- contexte : ex. lien de recherche Facebook, proposition de config
    statut text not null default 'en_attente'
        check (statut in ('en_attente', 'validee', 'rejetee')),
    propose_le timestamptz not null default now(),
    traite_le timestamptz,
    unique (type, identifiant, raison)
);

-- ---------------------------------------------------------------------------
-- Annonces
-- ---------------------------------------------------------------------------
create table annonces (
    id uuid primary key default gen_random_uuid(),
    source_id uuid not null references sources(id),
    url text not null,
    titre text,
    description_brute text,
    prix_roupies numeric,
    secteur_id text references secteurs(id),
    localisation_texte text,            -- localisation brute/précise extraite (ville, lotissement...)
    type_bien text check (type_bien in ('maison', 'terrain', 'autre')),
    chambres smallint,
    surface_terrain_perches numeric,
    surface_batie_m2 numeric,
    telephones text[] not null default '{}',   -- numéros normalisés 230XXXXXXXX
    photos jsonb not null default '[]',
    latitude double precision,
    longitude double precision,
    distance_plage_estimee_km numeric,
    score numeric,                      -- note Gemini sur 10
    resume text,
    drapeaux jsonb not null default '[]',   -- liste de points de vigilance
    vendeur_type text check (vendeur_type in ('particulier', 'agence', 'inconnu')),
    cle_dedup text,                     -- téléphone principal + tranche de prix, ou repli texte
    groupe_dedup_id uuid,               -- relie les republications détectées comme doublons
    statut text not null default 'nouveau'
        check (statut in ('nouveau', 'vu', 'contacte', 'visite', 'ecarte')),
    decouverte_le timestamptz not null default now(),
    envoyee_le timestamptz,
    derniere_maj timestamptz not null default now(),
    unique (source_id, url)
);

create index idx_annonces_statut on annonces (statut);
create index idx_annonces_score on annonces (score desc);
create index idx_annonces_cle_dedup on annonces (cle_dedup);
create index idx_annonces_titre_trgm on annonces using gin (titre gin_trgm_ops);
create index idx_annonces_description_trgm on annonces using gin (description_brute gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Votes (retours 👍/🚫 de l'utilisateur, servent aussi à affiner le prompt Gemini)
-- ---------------------------------------------------------------------------
create table votes (
    id uuid primary key default gen_random_uuid(),
    annonce_id uuid not null references annonces(id),
    valeur text not null check (valeur in ('pour', 'contre')),
    cree_le timestamptz not null default now(),
    unique (annonce_id)
);

-- ---------------------------------------------------------------------------
-- Acteurs (numéros de téléphone récurrents, y compris sur annonces filtrées)
-- ---------------------------------------------------------------------------
create table acteurs (
    id uuid primary key default gen_random_uuid(),
    telephone_normalise text not null unique,
    nom_observe text,
    nb_occurrences integer not null default 1,
    nb_annonces_filtrees integer not null default 0,
    statut text not null default 'nouveau'
        check (statut in ('nouveau', 'propose', 'valide', 'ignore')),
    lien_recherche_facebook text,
    premiere_vue timestamptz not null default now(),
    derniere_vue timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Journal d'exécution (une ligne par événement, pour diagnostiquer sans relancer)
-- ---------------------------------------------------------------------------
create table journal (
    id uuid primary key default gen_random_uuid(),
    execution_id uuid not null,
    horodatage timestamptz not null default now(),
    source_id uuid references sources(id),
    niveau text not null check (niveau in ('info', 'avertissement', 'erreur')),
    message text not null,
    details jsonb not null default '{}'
);

create index idx_journal_execution on journal (execution_id);

-- ---------------------------------------------------------------------------
-- Abonnements push (Web Push / VAPID)
-- ---------------------------------------------------------------------------
create table abonnements_push (
    id uuid primary key default gen_random_uuid(),
    endpoint text not null unique,
    clefs jsonb not null,   -- {p256dh, auth}
    actif boolean not null default true,
    cree_le timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Compteurs d'usage (garde-fous budgétaires Apify / Gemini / Google CSE)
-- ---------------------------------------------------------------------------
create table compteurs_usage (
    id uuid primary key default gen_random_uuid(),
    service text not null check (service in ('apify', 'gemini', 'google_cse')),
    periode text not null,   -- 'AAAA-MM' pour un compteur mensuel, 'AAAA-MM-JJ' pour un quota journalier
    utilises integer not null default 0,
    plafond integer not null,
    maj_le timestamptz not null default now(),
    unique (service, periode)
);

-- ---------------------------------------------------------------------------
-- Repli de dédup par similarité (pas de téléphone détecté) : rapproche une
-- annonce candidate des annonces existantes du même secteur, à prix proche
-- (±3 % par défaut) et au titre textuellement similaire (trigrammes).
-- ---------------------------------------------------------------------------
create or replace function rechercher_doublons_par_similarite(
    p_titre text,
    p_secteur_id text,
    p_prix numeric,
    p_tolerance_prix numeric default 0.03,
    p_seuil_similarite real default 0.45
) returns setof annonces
language sql
stable
as $$
    select *
    from annonces
    where secteur_id = p_secteur_id
      and prix_roupies between p_prix * (1 - p_tolerance_prix) and p_prix * (1 + p_tolerance_prix)
      and titre is not null
      and similarity(titre, p_titre) >= p_seuil_similarite
    order by similarity(titre, p_titre) desc
    limit 5;
$$;

-- ---------------------------------------------------------------------------
-- Incrémente un compteur d'usage de façon atomique et retourne s'il reste
-- de la marge sous le plafond (false = plafond atteint, ne pas consommer).
-- ---------------------------------------------------------------------------
create or replace function incrementer_compteur_usage(
    p_service text,
    p_periode text,
    p_plafond integer,
    p_montant integer default 1
) returns boolean
language plpgsql
as $$
declare
    v_utilises integer;
begin
    insert into compteurs_usage (service, periode, utilises, plafond)
    values (p_service, p_periode, 0, p_plafond)
    on conflict (service, periode) do nothing;

    select utilises into v_utilises
    from compteurs_usage
    where service = p_service and periode = p_periode
    for update;

    if v_utilises + p_montant > p_plafond then
        return false;
    end if;

    update compteurs_usage
    set utilises = utilises + p_montant, maj_le = now()
    where service = p_service and periode = p_periode;

    return true;
end;
$$;
