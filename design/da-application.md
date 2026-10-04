# Application de la direction artistique « carnet de cuisine pop » (design/direction-artistique-nourriture.md)

Fichier Figma `qJoKhsHeaDyMHf2JjBsFRe`, page « Écrans » (3:2). Ce document traduit la DA en décisions appliquables ; il complète (et remplace quand il contredit) le brief initial et audit_senior.md. Les corrections de l'audit (plan-corrections-audit.md) restent acquises : on restyle, on ne défait pas.

## 1. Décisions d'orchestration
- **On garde la sidebar** (clarté déjà acquise, l'audit le confirme) mais on adopte l'architecture proposée : destinations **Recettes · Menu · Courses**, action persistante **« Importer une recette »** (bouton en haut de la sidebar), **Réglages** en zone utilitaire basse avec le statut. La sidebar passe en **forêt** avec texte crème (7,4:1). La variante « barre supérieure crème » n'est pas réalisée (à tester plus tard).
- **Photos dominantes** : les cartes de recette et les créneaux de menu montrent le plat ; les grands aplats colorés disparaissent des cartes. La couleur sert aux étiquettes, aux surfaces éditoriales et aux couvertures graphiques de repli.
- **Deux accents saturés maximum par écran** : par défaut soleil + tomate (ou carotte). Kiwi et rose en appoint rare.
- **Trois signatures** : cadrage gourmand (photo ≥ 2/3 de la carte), étiquette de marché (une info, légère inclinaison -3°, soleil ou crème), trait de vapeur (3 courbes, logo + états vides + séparateurs éditoriaux).
- **Formes distinctes** : boutons = rectangle arrondi 14 ; chips = pilule ; badges d'état = rayon 6 ; étiquettes de marché = pilule inclinée ; champs = rayon 12 ; cartes = 16 à 24.
- Image de couverture : issue de la vidéo, remplaçable (« Changer la photo »), jamais générée. Le sélecteur propose 3 candidates « Images issues de la vidéo » + « Ajouter ma photo ».

## 2. Variables (nouvelles valeurs — même noms, les écrans se mettent à jour seuls)
| Variable | Valeur | Rôle DA | Texte dessus |
|---|---|---|---|
| bg/cream | #F3E8CC | Fond général, panneaux éditoriaux | encre #231D18 (13,7:1), forêt (7,4:1) |
| bg/paper | #FFFFFF | Champs, cartes de lecture | encre |
| bg/ink | #18542A | **Forêt** : sidebar, bouton principal, repères | crème #F3E8CC (7,4:1) |
| text/ink | #231D18 | Encre : corps, ingrédients, étapes | — |
| text/on-ink | #F3E8CC | Texte sur forêt / prune / tomate (grand) | — |
| text/muted | #6B6054 | Secondaire sur crème (5,1:1) et blanc (6:1) | — |
| text/accent | #B92319 | Quantités, chiffres clés (5,2:1 sur crème) | — |
| text/danger | #B92319 | Actions destructrices (libellé explicite) | — |
| line/soft | #E6D9BC | Filets décoratifs | — |
| line/strong | #8C7F68 | Bordures de champs (≥ 3,3:1) | — |
| accent/tomato | #D52518 | Marque : grand titre ponctuel, bandeau, logo | **blanc #FFFFFF** (5,1:1) ; crème seulement en grand texte |
| accent/yellow | #FFC926 | **Soleil** : étiquette de marché, mise en avant | encre (≥ 10:1) ou forêt (5,8:1) |
| accent/peach | #F96015 | **Carotte** : petites surfaces éditoriales | encre (5,3:1) |
| accent/lime | #9ABC05 | **Kiwi** : étiquette secondaire, sélection | encre (7,6:1) |
| accent/pink | #F6C0D0 | **Rose** : variation éditoriale limitée | prune (8,5:1) ou forêt |
| accent/plum | #5B1234 | **Prune** : titres sur rose, accent saisonnier | crème |
| accent/forest | #18542A | identique à bg/ink | crème |
| accent/violet | #5B1234 | aligné sur prune (plus de violet dans la DA) | crème |
| accent/sky | #CFE0D0 | Sauge claire : surfaces calmes (relecture, aide) | encre |
| accent/mint | #E8EEC4 | Kiwi pâle : fond d'information douce | encre |
Règle : tout texte sur tomate devient **blanc** (plus d'encre sur tomate) ; tout texte sur soleil/carotte/kiwi/rose/sauge reste encre ; crème sur forêt/prune.

## 3. Typographie
- Titres : **Bricolage Grotesque** — Display/XL 56/60 « 96pt ExtraBold » ; Display/L 40/44 ExtraBold ; Title/M 28/34 ExtraBold ; Title/S 20/26 Bold ; letterSpacing -1 % sur les Display, 0 ailleurs.
- Corps : **DM Sans** — Body/L 18/26 Bold ; Body/M 16/24 SemiBold ; Body/S 14/20 SemiBold ; Body/M Bold et Body/S Bold en ExtraBold ; Label 12/16 ExtraBold majuscules +6 %.
- Chiffres : Number/L et Number/M passent en **Bricolage Grotesque ExtraBold** (48/48 et 28/28) pour remplacer Anton (une famille de moins à l'écran).
- Nouveau style **Cuisine/Étape** : Bricolage Grotesque Bold 24/32 (mode cuisine) et **Cuisine/Lecture** : DM Sans SemiBold 20/30.
- Pas de capitales sur les étapes ; capitales réservées aux Labels courts.

## 4. Composants à restyler (agent composants)
1. **Sidebar** : fond bg/ink (forêt), logo = monogramme crème « N » sur disque soleil 28 px + « Nourriture » Title/S crème + **trait de vapeur** (3 courbes crème, 20 × 14 px) à droite du nom ; bouton **« Importer une recette »** (Bouton Style=Accent, pleine largeur) sous le logo ; items : Recettes (icon book), Menu (calendar), Courses (icon list) ; item actif = pilule crème texte forêt ; inactif = texte crème ; zone basse : « Réglages » (icon settings, texte crème) puis statut « IA locale prête » (point kiwi) et compteur. Axe `Actif` = Recettes | Menu | Courses | Réglages | Aucun (pour Importer).
2. **Bouton** : rayon 14 (plus pilule). Primaire = forêt / crème ; Accent = tomate / **blanc** ; Secondaire = paper + bordure 1,5 line/strong, texte encre ; Fantôme = texte forêt. États inchangés (survol : forêt #12421F, tomate #B92319 ; focus = anneau 2 px encre à 2 px).
3. **Chip** : pilule 40, Défaut = paper + bordure line/strong ; Actif = forêt / crème ; Couleur = soleil ou kiwi avec texte encre.
4. **Badge** (statut) : rayon 6, Label ; variantes Soleil (« Brouillon importé »), Kiwi (« Relue par vous »), Forêt (« Cuisinée », texte crème), Paper (bordure) ; **plus d'inclinaison**.
5. **ÉtiquetteMarché** (nouveau) : pilule 28, soleil ou crème avec bordure encre 1,5, Body/S Bold encre, rotation -3° autorisée sur l'instance, une seule info (« 35 min », « À vérifier », « Photo personnelle »).
6. **CarteRecette** : fond paper, rayon 20, padding 0 ; photo 4:3 en haut (rayon 20 en haut), **≈ 2/3 de la hauteur** ; sur la photo, ÉtiquetteMarché « 35 min » en haut à gauche et bouton cœur (favori) en haut à droite dans un disque crème ; dessous padding 16 : titre Title/S (2 lignes max), méta Body/S muted « Plat · 2 pers. · @chef_test », rangée statut (Badge si « À vérifier »). Variante `Couverture` = Photo | Graphique (repli : surface colorée persistante kiwi/soleil/rose/sauge avec motif vapeur crème et initiale du plat). Supprimer l'axe Tuile 8 couleurs.
7. **CréneauMenu** : paper, rayon 20, 300 × 128 : à gauche photo 96 × 96 rayon 12, à droite Label du jour (encre), titre Title/S, méta Body/S muted ; actions : « Remplacer » (icône dice, 36 px) et « Conserver » (icône lock) ; variantes `État` = Rempli | Vide | Conservé (bandeau fin soleil « Conservé »). Couleur stable = la photo ; plus de tuile colorée par jour.
8. **TuileStat** : surfaces sauge/soleil/crème-bordée seulement (plus de couleurs vives multiples), Number en Bricolage.
9. **LigneIngrédient / Étape / SourceTag / CaseÀCocher / Champ / Toast / Tooltip** : adopter rayon 12 pour les champs, bordure line/strong, quantités en text/accent, polices nouvelles ; rien d'autre ne change.
10. **Vapeur** (nouveau composant décoratif, 3 courbes stroke 2,5 round) en 2 tailles (20 px, 64 px) ; **Assiette** (illustration simple : disque crème bordé encre, 2 courbes de vapeur) pour l'état vide.
11. Tous les Display/Title des composants passent en Bricolage via les styles (automatique) ; vérifier les largeurs (Bricolage est plus étroite qu'Unbounded : réduire les hauteurs fixes si des cartes ont du vide).

## 5. Écrans (agents écrans)
- **Toutes les vues** : sidebar nouvelle version ; « Bibliothèque » devient **Recettes** (titres, fil d'Ariane) ; au plus deux accents saturés par écran ; étiquettes de marché à la place des badges de temps ; titres Bricolage.
- **01 Recettes** : grille 4 × 2 de CarteRecette version photo (hauteur ≈ 420) ; en-tête « Recettes » + sous-titre ; actions : « Restaurer des recettes » Secondaire (l'import est désormais dans la sidebar) ; bloc éditorial compact « À cuisiner cette semaine » (une carte horizontale : photo + titre + « Ouvrir ») au-dessus de la grille, sans repousser la recherche sous la ligne de flottaison ; filtres inchangés.
- **00 Recettes — vide** : illustration Assiette + vapeur, titre « Qu'est-ce qu'on cuisine ? », texte, bouton Primaire forêt « Importer une recette ».
- **02/02b/02c Importer** : fond crème, titre court, champ très lisible, bouton forêt « Analyser la recette » ; trait de vapeur près du titre ; aperçu de la couverture présélectionnée dès qu'une image existe (02b : vignette « Image issue de la vidéo » avec « Changer la photo ») ; détails moteur dans l'aide dépliable.
- **03 Vérifier** : surfaces calmes (sauge pour le bandeau, paper pour les cartes), aucune tuile saturée ; colonne droite : **sélecteur de couverture** (3 candidates 4:3 « Images issues de la vidéo », la première sélectionnée avec coche forêt, + « Choisir un autre moment », + « Ajouter ma photo », + « Afficher l'image entière ») au-dessus de la source ; titre et « 2 informations à vérifier » en premier.
- **04 Fiche** : photo généreuse (portrait possible), titre Display/XL Bricolage, source, étiquette de marché « 35 min » ; actions : **« Cuisiner »** Primaire forêt (seule primaire), **« Ajouter au menu »** Secondaire, Modifier / Favoris / Exporter en Fantôme dans la barre haute ; tuiles stats en sauge/soleil/paper ; notes = carte paper avec filet soleil à gauche (annotation de carnet), texte lisible ; Supprimer isolé (texte text/danger).
- **04b** inchangé (couleurs/typo via tokens) ; **04c Mode cuisine** : photo vignette 120, étape courante en Cuisine/Étape 24/32 sur paper, progression, portions, minuteur explicite ; très peu de couleur (soleil pour l'étape en cours uniquement).
- **05 Menu** : créneaux avec photo (CréneauMenu nouvelle version), jours stables en Label, « Conservé » sur Mardi ; paramètres sur paper ; résultat en 7 lignes ou grille 4 + 3 ; **05b** idem avec 2 créneaux vides.
- **Courses** : nouvel écran **08 · Courses** (x = 11480, y = 0) accessible depuis la sidebar : esprit ticket de marché — carte paper étroite centrée (720) avec en-tête « Courses de la semaine du 05/10 », rayons en Label avec filet pointillé, lignes 48 px activables (CaseÀCocher + article Body/M + quantité à acheter alignée à droite en text/accent), « Produits de base » en bas, « Ajouter un article », légende ; la section courses de 05 se résume à un résumé + bouton « Ouvrir les courses ».
- **06 Réglages** : surfaces sobres paper/crème, statut lisible, détails techniques repliés (déjà fait) ; **07 Installation** : idem.
- **Images** : réutiliser les imageHash existants (voir design/photos-hashes.json) pour cartes, créneaux et sélecteur (3 recadrages différents de la photo du curry pour les candidates).

## 6. Ordre d'exécution
1. Agent composants : variables (§2) → styles de texte (§3) → composants (§4) → ds-state.json et captures. Aucun écran touché.
2. Agents écrans (en parallèle après 1) : adaptation des écrans (§5), nouvel écran 08 · Courses, captures.
3. Orchestrateur : prototype (liens), captures finales, documentation.
