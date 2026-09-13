-- Active la sécurité au niveau ligne (RLS) et autorise la lecture seule,
-- anonyme, sur les tables consultées par l'application (clé publishable
-- côté navigateur — jamais la clé secrète, qui reste réservée au job de
-- collecte). Écriture (votes, statut...) : ajoutée quand ces fonctionnalités
-- seront construites, pas avant.

alter table annonces enable row level security;
alter table secteurs enable row level security;
alter table votes enable row level security;
alter table sources enable row level security;
alter table sources_proposees enable row level security;
alter table acteurs enable row level security;
alter table journal enable row level security;
alter table abonnements_push enable row level security;
alter table compteurs_usage enable row level security;

create policy "lecture publique des annonces" on annonces
    for select to anon using (true);

create policy "lecture publique des secteurs" on secteurs
    for select to anon using (true);

-- Toutes les autres tables restent fermées à la clé publique par défaut
-- (RLS activé, aucune policy = aucun accès) : sources/journal/acteurs/
-- compteurs_usage ne sont utiles qu'à l'admin (écran à venir en M5) et au
-- job de collecte (qui utilise la clé secrète, non soumise à RLS).
