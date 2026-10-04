# Nourriture — Brief de design Figma (desktop macOS)

Fichier Figma : fileKey `qJoKhsHeaDyMHf2JjBsFRe` (NOUVEAU fichier, l'ancien `fxBJe5i1Yjrqb1vXvSX8MY` est abandonné). Page cible « Écrans » : la trouver par son nom dans `figma.root.children`, la créer avec `figma.createPage()` si elle n'existe pas. La page « DA » (id `0:1`) contient 13 images de référence (moodboard), ne pas la modifier.

## Contraintes outillage (IMPORTANT)
- Utiliser UNIQUEMENT l'outil `mcp__plugin_figma_figma__use_figma` (charger son schéma via ToolSearch `select:mcp__plugin_figma_figma__use_figma`). Charger d'abord le skill `figma:figma-use` et respecter ses règles (createAutoLayout, fonts chargées avant tout texte, couleurs 0–1, HUG/FILL après appendChild, `await figma.setCurrentPageAsync(page)` une seule fois par appel, retourner les IDs).
- Compte Figma : plan Éducation, quota 200 appels MCP par jour et 10 par minute. Privilégier `use_figma` et regrouper le travail en appels copieux mais retry-safe ; espacer les appels (jamais plus de 6 par minute par agent) ; si une erreur de quota/rate limit survient, attendre 70 secondes puis réessayer le même appel. Éviter get_screenshot/get_metadata : pour vérifier visuellement, utiliser `await node.screenshot()` à l'intérieur de `use_figma` (une capture après composition, une après correction).
- Chaque appel `use_figma` commence par : `const page = figma.root.children.find(p => p.name === "Écrans"); await figma.setCurrentPageAsync(page);` (ou par l'identifiant de page communiqué par l'orchestrateur).
- Toujours `await figma.loadFontAsync({family, style})` pour chaque police utilisée avant de créer du texte. Polices disponibles : « Archivo Black » (Regular), « DM Sans » (Regular, Medium, SemiBold, Bold, ExtraBold), « Anton » (Regular).
- Tout en français, sans emoji dans les textes (sauf le logo 🍲 autorisé une fois dans la sidebar). Pas de « Lorem ipsum » : contenu réaliste de recettes.

## Direction artistique (synthèse de la page DA)
Style « éditorial pop / néo-brutaliste doux » : fond crème, grands blocs de couleurs saturées, typo très grasse et compacte pour les titres, coins très arrondis (cartes 24–28 px, pastilles 999 px), boutons noirs en pilule, étiquettes colorées type sticker, photos de plats dans des cadres arrondis posés sur des tuiles colorées, mosaïques de tuiles (façon widgets), Beaucoup d'air, hiérarchie nette, peu de bordures fines : la couleur structure.

## Tokens (collection de variables locales « Nourriture », un seul mode « Clair »)
Couleurs (hex) — palette DOUCE mais contrastée (mise à jour finale, valeurs des variables) :
- bg/cream #F6F1E9 (fond des écrans) · bg/paper #FFFFFF (cartes neutres) · bg/ink #17160F (sidebar, boutons primaires)
- text/ink #17160F · text/muted #6E675E · text/on-ink #F6F1E9 · line/soft #E5DDD0
- accent/tomato #EE6A3C (texte ink) · accent/lime #CDE26B (ink) · accent/yellow #F7CF5A (ink) · accent/pink #F48FB8 (ink) · accent/violet #6B5CE7 (clair) · accent/sky #6EC6F2 (ink) · accent/forest #237A52 (clair) · accent/plum #7A2B4E (clair) · accent/peach #F8B57A (ink) · accent/mint #8FE0B4 (ink)
Règle de contraste : texte ink sur lime, yellow, pink, sky, peach, mint et tomato ; texte clair (text/on-ink) sur violet, plum, forest, ink. Tous les couples vérifiés ≥ 4,5:1 (AA).
Rayons : radius/sm 10 · radius/md 16 · radius/lg 24 · radius/xl 28 · radius/pill 999
Espacements : space/4 8 12 16 20 24 32 40 48 64
Scopes explicites (FRAME_FILL/SHAPE_FILL pour les fonds, TEXT_FILL pour les textes, CORNER_RADIUS, GAP + WIDTH_HEIGHT pour les espacements).

## Styles de texte (créer des text styles locaux)
- Display/XL : Archivo Black 64, line 60 (0.94), letterSpacing -1.5 %
- Display/L : Archivo Black 44, line 44
- Title/M : Archivo Black 28, line 32
- Title/S : Archivo Black 20, line 24
- Body/L : DM Sans Medium 18, line 26
- Body/M : DM Sans Medium 16, line 24
- Body/S : DM Sans Medium 14, line 20
- Label : DM Sans Bold 12, line 16, letterSpacing +6 %, majuscules
- Chip : DM Sans SemiBold 14, line 20
- Number/L : Anton 48, line 48 (gros chiffres : minutes, portions)
- Number/M : Anton 28, line 28

## Composants (page « Écrans », section « Composants » placée en y = -2200, x = 0, en grille lisible)
Tous en auto layout, avec propriétés de composant texte quand c'est utile. Nommer exactement :
1. `Sidebar` — 240 × 900, fond ink, padding 24, gap 8. Haut : logo « 🍲 Nourriture » (Title/S, text/on-ink) + sous-titre « Recettes Instagram, en local » (Body/S, muted clair #B8B1A6). Nav : 4 items pilule (hauteur 44, padding 0 16, gap 12, icône 20 + libellé Body/M) : Bibliothèque, Importer, Menu de la semaine, Réglages. Variante active : fond lime, texte ink. Inactif : texte on-ink. Bas : pastille statut « IA locale prête » (point vert #3DDC84 + Body/S) et « 24 recettes » (Body/S muted). Propriété variante `Actif` = Bibliothèque | Importer | Menu | Réglages.
2. `Bouton` — variantes `Style` = Primaire (fond ink, texte on-ink) | Accent (fond tomato, texte blanc) | Secondaire (fond paper, bordure 2 ink, texte ink) | Fantôme (transparent, texte ink) ; `Taille` = L (hauteur 48, padding 0 22, Body/M Bold) | M (hauteur 40, padding 0 16, Body/S Bold). Pilule. Propriété texte `Libellé`, propriété booléenne `Icône` (icône 18 à gauche).
3. `Chip` — pilule hauteur 36, padding 0 14, Chip style. Variantes `État` = Défaut (paper + bordure 1.5 line/soft) | Actif (ink + texte on-ink) | Couleur (fond accent au choix via override, texte ink). Propriété texte `Libellé`, booléen `Compteur` (petit nombre muted).
4. `Badge` — sticker pilule hauteur 26, padding 0 10, Label style ; variantes `Couleur` = Lime | Pink | Yellow | Peach ; légère rotation -3° autorisée sur l'instance. Propriété texte.
5. `CarteRecette` — 300 × 380, radius/lg, padding 16, gap 12, fond = tuile couleur (propriété variante `Tuile` = Tomato | Lime | Yellow | Pink | Violet | Sky | Plum | Mint). Haut : rangée auteur (pilule paper « @chef_test », Body/S) + pilule temps « 25 min ». Milieu : `photo` = frame 268 × 190, radius/md, fond #E9E2D6 avec un cercle central plus foncé #D9D0C0 (placeholder image, nommer « photo »). Bas : titre Title/S (ink sur tuiles claires, on-ink sur Tomato/Violet/Plum/Forest), rangée méta « Plat · 4 pers. » Body/S, rangée badges (Badge « Rapide »). Propriétés texte : Titre, Auteur, Temps, Méta.
6. `ChampRecherche` — pilule hauteur 48, fond paper, padding 0 20, icône loupe 20 + texte placeholder « Rechercher un plat, un ingrédient… » (Body/M muted). Largeur FILL.
7. `Champ` — champ de formulaire : libellé Label au-dessus, boîte hauteur 44, fond paper, radius/md, bordure 1.5 line/soft, texte Body/M. Propriétés texte Libellé/Valeur.
8. `TuileStat` — tuile widget 160 × 120, radius/lg, fond accent (variante Couleur), libellé Label en haut, Number/L dessous, unité Body/S. (temps de préparation, cuisson, portions…)
9. `CréneauMenu` — 300 × 200, radius/lg, fond accent par jour (variante `Jour` = Lundi…Dimanche avec couleurs : Lundi tomato, Mardi lime, Mercredi yellow, Jeudi sky, Vendredi pink, Samedi violet, Dimanche mint). Haut : libellé jour Label + bouton rond 32 (icône dé « re-tirer ») ; bas : titre recette Title/S + méta Body/S (temps · protéine). Variante `État` = Rempli | Vide (texte « Aucune recette » centré, fond paper pointillé).
10. `LigneIngrédient` — rangée hauteur 44 : quantité Number/M (tomato) largeur 96 + nom Body/M + badge optionnel « estimée ». Variante `Estimée` = Non | Oui.
11. `Étape` — rangée : pastille ronde 32 (fond lime, numéro DM Sans Bold 14) + texte Body/M FILL.
12. `ÉlémentCourses` — rangée : case 22 radius 6 (bordure 2 ink ; variante Coché = fond ink + coche) + texte Body/M + mention Body/S muted « — Poulet curry ».
13. `Icônes` — composants 20 × 20 nommés `icon/<nom>` créés avec `figma.createNodeFromSvg` (stroke 2, round caps, couleur ink #121212, viewBox 0 0 24 24) : search, plus, download, book, calendar, settings, heart, clock, users, dice, check, x, chevron-right, chevron-left, edit, trash, upload, external, sparkles, refresh, camera, play, filter, copy. Regroupés dans un frame « Icônes ».
14. (SUPPRIMÉ) Aucun visage ni mascotte dans l'application : les composants `Visage/*` ne doivent plus être utilisés et seront retirés. Pour les états vides, utiliser un disque 96 px lié à `accent/lime` contenant une icône (`icon/book`, `icon/dice`…) de 44 px.

## Écrans (1440 × 900 chacun, fond bg/cream, auto layout horizontal : Sidebar 240 + zone contenu FILL avec padding 40 48, gap 32)
Grille de placement sur la page « Écrans » (x de départ, y = 0, espacement 200 entre écrans) :
- `01 · Bibliothèque` x = 0
- `02 · Importer` x = 1640 ; variante `02b · Importer — en cours` x = 1640, y = 1100
- `03 · Vérifier la recette` x = 3280
- `04 · Fiche recette` x = 4920
- `05 · Menu de la semaine` x = 6560
- `06 · Réglages` x = 8200
- `00 · Bibliothèque — vide` x = 0, y = 1100
Chaque écran est un frame auto layout nommé comme ci-dessus ; les titres d'écran dans le contenu utilisent Display/L.

### 01 · Bibliothèque
En-tête : titre « Bibliothèque » (Display/L) + sous-titre « 24 recettes enregistrées » (Body/M muted) ; à droite boutons « Exporter » (Secondaire M, icône upload), « Importer un fichier » (Secondaire M), « + Importer d'Instagram » (Primaire L). Barre : ChampRecherche FILL + select « Plus récentes » (Champ compact) + chip « ♥ Favoris ». Rangée de chips catégories : Toutes (Actif), Entrée, Plat (12), Dessert (5), Petit-déjeuner, Snack, Boisson, Accompagnement, Sauce. Rangée de chips étiquettes en couleur : #rapide (lime), #végétarien (mint), #healthy (yellow), #batch cooking (pink), #italien (peach), #asiatique (sky). Grille 4 × 2 de CarteRecette avec tuiles variées et vrais titres : Poulet curry express (Tomato, @chef_test, 25 min), Gratin dauphinois (Yellow, @mamie, 1 h 30), Dahl de lentilles corail (Lime), Saumon teriyaki (Sky), Pâtes carbonara (Peach/Pink), Banana bread moelleux (Violet), Chili con carne (Plum), Salade César (Mint).
### 00 · Bibliothèque — vide
Même en-tête ; au centre, carte paper 640 de large, radius/xl, padding 48 : disque lime 96 px avec `icon/book` 44 px, « Votre bibliothèque est vide » (Title/M), « Collez un lien Instagram pour importer votre première recette. » (Body/M muted), bouton Accent L « Importer une recette ».
### 02 · Importer
Titre « Importer une recette » + texte explicatif (Body/M muted, max 720 px). Grande carte paper radius/xl padding 32 : onglets chips « Lien Instagram » (Actif) / « Saisie manuelle / fichier » ; champ URL géant hauteur 56 (pilule, placeholder « https://www.instagram.com/reel/… ») + bouton Accent L « Importer » ; case à cocher « Analyser la vidéo même si la description contient la recette ». Dessous, mosaïque de 4 TuileStat expliquant la chaîne (« 1 Récupération » tomato, « 2 Analyse locale » lime, « 3 Rédaction IA » yellow, « 4 Vérification » pink) avec Label + texte court Body/S. Encart rassurant en bas : « Tout reste sur votre Mac. Aucune donnée envoyée. » avec icône sparkles sur fond mint.
### 02b · Importer — en cours
Même écran ; la carte montre la progression : 4 tuiles d'étapes, celle en cours (« Rédaction IA ») en tomato avec spinner stylisé, les précédentes en lime avec coche, la suivante en paper ; barre de progression 75 % (fond line/soft, remplissage tomato, pilule) ; journal (fond ink radius/md, texte on-ink DM Sans Regular 13 mono-like) avec 5 lignes horodatées « 17:25:04 Transcription terminée (351 caractères, fr) ».
### 03 · Vérifier la recette
Titre « Vérifiez la recette » + sous-titre. Bandeau info sur fond mint radius/md : « La description ne contenait pas la recette · Vidéo analysée : transcription (351 caractères, fr), 14 lignes de texte à l'écran · 2 quantités estimées · Confiance haute ». Deux colonnes : gauche (FILL) formulaire : photo 180 × 180 + Champ Titre « Poulet curry express », rangée de Champs Catégorie / Protéine / Cuisine, rangée Portions / Préparation / Cuisson ; carte « Ingrédients » avec 5 LigneIngrédient (2 blancs de poulet ; 400 ml lait de coco ; 1 oignon (estimée) ; 2 c. à soupe pâte de curry ; ½ botte coriandre (estimée)) + bouton Fantôme « + Ajouter » ; carte « Étapes » avec 5 Étape ; droite (360 px) : carte conseils sur fond yellow « Relisez avant d'enregistrer », rangée de Badges. Barre d'action collante en bas : « Annuler » Secondaire + « Enregistrer dans la bibliothèque » Primaire L.
### 04 · Fiche recette
Deux colonnes : gauche FILL : fil d'Ariane « ← Bibliothèque », titre Display/XL « Poulet curry express », ligne auteur/source « @chef_test · Voir sur Instagram ↗ · ajoutée le 4 oct. 2026 », chips étiquettes couleur, section « Ingrédients » avec compteur de portions (pilule : « − 2 portions + ») et 5 LigneIngrédient, section « Préparation » avec 5 Étape, « Notes ». Droite 360 : grande photo 360 × 440 radius/xl sur tuile tomato ; mosaïque de 4 TuileStat (Préparation 20 min / Cuisson 15 min / Portions 2 / Protéine poulet) ; boutons « Modifier » Secondaire, « Favori », « Exporter », « Supprimer » (Fantôme rouge).
### 05 · Menu de la semaine
Titre « Menu de la semaine » + sous-titre « Tirage aléatoire sans doublon, en variant protéines et cuisines. ». Carte paramètres paper : Champs « Nombre de repas 7 », « Moments Dîners », « Temps total max ≤ 45 min », « Portions 4 », « Semaine du 05/10/2026 » ; chips catégories ; bouton Accent L « Tirer un menu » avec icône dé. Résultat : titre « Semaine du 05/10/2026 » + boutons « Copier menu + courses » Secondaire et « Enregistrer » Primaire ; rangée de 7 CréneauMenu (Lundi → Dimanche) avec titres : Poulet curry express, Dahl de lentilles corail, Saumon teriyaki, Pâtes carbonara, Chili con carne, Salade César, Gratin dauphinois (2 rangées : 4 + 3). Section « Liste de courses » en 3 colonnes par rayon (Fruits & légumes, Viandes & poissons, Crèmerie & œufs, Épicerie) avec ÉlémentCourses (quelques cochés).
### 06 · Réglages
Titre « Réglages ». Cartes paper radius/xl padding 32 empilées : « Intelligence artificielle locale (Ollama) » (ligne statut point vert « Ollama 0.35 est lancé », Champ « Modèle » = Qwen 2.5 7B — recommandé, Champ « Adresse », conseil Body/S) ; « Transcription et lecture d'écran » (Champ modèle Whisper small, cases à cocher Transcrire l'audio / Lire le texte à l'écran / Toujours analyser la vidéo) ; « Instagram » (texte explicatif + Champ Navigateur pour les cookies) ; « Données » (chemin en style code, boutons Afficher dans le Finder / Exporter / Importer / Journaux ; Champ Thème). Pied : « Nourriture 0.1.0 — 100 % local et gratuit ».

## Qualité attendue
- 100 % auto layout (aucune position absolue à l'intérieur des écrans), dimensionnements FILL/HUG cohérents, textes qui ne débordent pas (textAutoResize HEIGHT + largeur fixe pour les paragraphes).
- Instances de composants (pas de copies à plat) ; overrides de texte via setProperties quand une propriété existe, sinon characters.
- Nommage propre des calques en français ; sections regroupées ; aucun shimmer `placeholder` laissé actif.
- Une capture `await frame.screenshot()` à la fin de chaque écran, corriger si débordement/chevauchement, puis une capture finale.
