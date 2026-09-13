-- Autorise la clé publique à créer un abonnement push (mais pas à lire les
-- abonnements existants — un seul utilisateur, aucun besoin de lecture
-- côté navigateur, et ça évite d'exposer les endpoints d'abonnement).

create policy "creation publique d'abonnements push" on abonnements_push
    for insert to anon with check (true);
