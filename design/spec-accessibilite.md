# Spécification d'accessibilité fonctionnelle — Nourriture (desktop macOS)

Référentiel : WCAG 2.2 niveau AA, Apple Human Interface Guidelines (macOS), pattern WAI-ARIA « dialog (modal) ». Cette spécification répond au point A04 de l'audit : elle décrit les comportements attendus dans l'application, que la maquette Figma ne peut pas démontrer. Elle s'applique à l'interface web embarquée (`nourriture/static`) rendue dans la fenêtre native.

## 1. Clavier et ordre de lecture
- Tout ce qui se fait à la souris se fait au clavier : navigation latérale, recherche, filtres (chips), tri, cartes de recettes, compteur de portions, lignes d'ingrédients et d'étapes en édition, créneaux du menu, cases des courses, boutons icône.
- Ordre de tabulation = ordre visuel : sidebar → en-tête (titre, actions) → outils → contenu → barre d'action. Aucun piège clavier ; Échap ferme menus, infobulles, modales et le mode cuisine (avec confirmation si une progression serait perdue).
- Raccourcis macOS attendus : ⌘N (Importer), ⌘F (Rechercher), ⌘S (Enregistrer dans la relecture), ⌘⌫ (Supprimer avec confirmation), ←/→ (étape précédente/suivante en mode cuisine), Espace (cocher une course). Les raccourcis sont affichés dans les infobulles, jamais indispensables.
- Les chips de filtres se comportent comme des cases à cocher (`role="checkbox"`, `aria-checked`) ; « Toutes » est un bouton radio implicite qui désactive les autres.
- Les listes (cartes, créneaux, courses) utilisent les flèches pour se déplacer entre éléments et Entrée pour ouvrir ; Tab sort de la liste.

## 2. Focus visible et non masqué (2.4.7, 2.4.11, 2.4.12)
- Indicateur unique : anneau de 2 px `text/ink` à 2 px du contrôle (`outline: 2px solid; outline-offset: 2px`), jamais supprimé par `outline: none` sans remplacement équivalent.
- Les barres fixes (barre d'action de la relecture, en-tête collant) ne recouvrent jamais l'élément focalisé : `scroll-padding-bottom` ≥ hauteur de la barre + 16 px ; en mode cuisine, les boutons « Étape précédente / suivante » restent visibles sans défilement.
- Après une action qui retire l'élément focalisé (suppression de ligne, de recette, fermeture de modale), le focus revient à un élément logique : la ligne suivante, le déclencheur, ou le titre de la vue.

## 3. Noms accessibles et sémantique (1.1.1, 1.3.1, 4.1.2)
- Chaque bouton icône porte un `aria-label` explicite : « Augmenter le nombre de portions », « Réduire le nombre de portions », « Remplacer le repas du mercredi », « Conserver le repas du mardi », « Retirer l'ingrédient lait de coco », « Monter l'étape 3 », « Lancer le minuteur de 10 minutes », « Fermer ».
- Les images de recettes sont décoratives dans les cartes (`alt=""`) et informatives dans la fiche (`alt` = « Photo du reel de @chef_test : poulet au curry dans un bol »). Les icônes décoratives sont `aria-hidden`.
- Structure : un `h1` par vue (titre de l'écran), `h2` pour les sections (Ingrédients, Préparation, Liste de courses), listes (`ul`/`ol`) pour ingrédients, étapes, courses ; la navigation latérale est un `nav` avec `aria-current="page"` sur l'élément actif.
- Les statuts (« Brouillon importé », « Relue par vous », « Quantité estimée », origine « vidéo 0:12 ») sont du texte réel, pas seulement une couleur ou une icône.

## 4. Messages de statut et progression (4.1.3)
- Toasts (« Recette enregistrée », « Jeudi remplacé · Annuler ») dans une zone `role="status"` (`aria-live="polite"`) ; ils ne prennent pas le focus. Le bouton « Annuler » est atteignable au clavier pendant les 10 s ; la durée se prolonge au survol/focus.
- Progression d'import : la zone « Étape 3 sur 3 · 42 s écoulées » est `aria-live="polite"` et n'annonce qu'aux changements d'étape ; le journal technique n'est pas annoncé (il est replié par défaut et marqué `aria-live="off"`).
- Erreurs de formulaire : message texte sous le champ, lié par `aria-describedby`, champ marqué `aria-invalid="true"`, focus déplacé sur le premier champ en erreur après la soumission. La valeur saisie est conservée.

## 5. Modales (dialog)
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` (titre) et `aria-describedby` (texte). Focus initial sur l'action la plus sûre (« Annuler »). Tab et Maj+Tab restent dans la modale. Échap et le clic sur le voile ferment. À la fermeture, le focus revient au bouton déclencheur (« Supprimer la recette »).
- Après confirmation d'une suppression : retour à la Bibliothèque, focus sur le titre de la vue, toast « Recette supprimée · Annuler » pendant 10 s ; la recette est retirée des menus enregistrés et un texte le signale dans la modale avant confirmation.

## 6. Zoom, redistribution et espacement (1.4.4, 1.4.10, 1.4.12)
- Texte agrandi à 200 % sans perte : les grilles passent de 4 à 2 colonnes, puis 1 ; la sidebar se réduit à des icônes avec libellés en infobulle à partir de 1 024 px de large de fenêtre.
- Aucun défilement horizontal pour une largeur de 320 px CSS équivalente ; les tableaux d'ingrédients deviennent des cartes empilées.
- Les espacements de texte personnalisés (interligne 1,5 ; paragraphes 2 ; lettres 0,12 em ; mots 0,16 em) ne coupent ni ne masquent aucun texte : pas de hauteur fixe sur les blocs de texte.

## 7. Contraste et couleur (1.4.1, 1.4.3, 1.4.11)
- Texte ink sur toutes les tuiles claires (lime, yellow, pink, sky, peach, mint, tomato) ; texte clair sur violet #5B4BD6, plum, forest et ink. Quantités en `text/accent` #C9441A sur blanc (4,9:1). Actions destructrices en `text/danger` #B83232 sur crème (5,3:1).
- Bordures des champs en `line/strong` #8A8276 (≥ 3:1 sur blanc et crème) ; cases à cocher avec bordure 2 px ink.
- Aucun état n'est signalé par la couleur seule : actif (fond ink + texte), coché (coche), estimé (badge texte), conservé (icône + libellé), erreur (icône + texte).

## 8. Cibles et pointeur (2.5.8, 2.5.7)
- Cibles minimales 24 × 24 px CSS ; recommandé 40 × 40 partout et **44 × 44 en mode cuisine** et pour les cases des courses (toute la ligne est cliquable).
- Le réordonnancement des étapes dispose des boutons « Monter / Descendre » (alternative au glisser-déposer). Aucune fonction ne dépend du survol : les infobulles complètent, elles ne remplacent pas un libellé.

## 9. Infobulles (1.4.13)
- Apparaissent au survol et au focus clavier, se ferment avec Échap, restent affichées tant que le pointeur est dessus, n'obstruent pas le contrôle. Le nom accessible du bouton ne dépend pas de l'infobulle.

## 10. Vérifications avant publication
- Parcours complet au clavier seul : importer → relire/corriger → enregistrer → retrouver → mode cuisine ; puis au lecteur d'écran VoiceOver.
- Contrôle automatique des contrastes sur chaque état (défaut, survol, pressé, focus, désactivé, erreur) et test manuel à 200 % de zoom et à 320 px.
- Test avec deux ou trois personnes utilisatrices de technologies d'assistance en plus des 5 à 8 participants du test qualitatif.
