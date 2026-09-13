# Bascule vers un APK Capacitor — ce qu'il faudrait faire

Ce document existe pour que la décision de passer au natif (widget d'écran
d'accueil, push Firebase, historique hors ligne complet) reste simple à
prendre plus tard, sans avoir à ré-explorer le code. Capacitor **n'est pas
installé** — ceci est un plan, pas une configuration active.

## Pourquoi c'est censé être simple

Le code accède au navigateur uniquement à travers `src/lib/plateforme/` :
- `liens.ts` — ouverture de liens externes (annonce d'origine, WhatsApp, appel, itinéraire)
- `partage.ts` — partage natif
- `stockage.ts` — cache local (annonces déjà chargées)
- (à venir en M3) `notifications.ts` — abonnement et réception des notifications push

Aucun autre fichier de l'app n'appelle `window.open`, `navigator.share`,
`localStorage` ou l'API Push directement. Le routage est en mode hash
(`HashRouter`), compatible avec un `file://` ou une webview locale, sans
configuration serveur particulière.

## Étapes pour basculer

1. `npm install @capacitor/core @capacitor/cli @capacitor/android`
2. `npx cap init` (nom de l'app, identifiant du package)
3. `npx cap add android`
4. Adapter chaque fichier de `src/lib/plateforme/` :
   - `liens.ts` → `@capacitor/browser` (`Browser.open()`) au lieu de `window.open`
   - `partage.ts` → `@capacitor/share` (`Share.share()`) au lieu de l'API Web Share
   - `stockage.ts` → `@capacitor/preferences` au lieu de `localStorage`
   - `notifications.ts` → `@capacitor/push-notifications` + Firebase Cloud
     Messaging au lieu de Web Push/VAPID (remplace aussi la partie
     `pywebpush` côté job de collecte — les deux bouts de l'abstraction
     notifications doivent changer ensemble)
5. `npm run build && npx cap sync android`
6. `npx cap open android` (ouvre Android Studio pour builder l'APK)

## Ce qui ne change pas

- Les pages (`src/pages/`), les composants, les appels Supabase : rien à
  toucher, ils ne connaissent que les fonctions exportées par
  `src/lib/plateforme/`, pas leur implémentation.
- Le schéma de données et le job de collecte Python restent identiques.

## Ce qui devient possible seulement en natif

- Widget d'écran d'accueil (liste des dernières annonces)
- Notifications push même app fermée depuis plusieurs jours (Web Push a
  des limites de fiabilité sur Android en arrière-plan prolongé)
- Historique hors ligne complet (au-delà de ce que le cache localStorage
  actuel couvre)
