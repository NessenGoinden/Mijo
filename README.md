# Mijo 🍲

*Nom de code de l'application : Nourriture.*

**[⬇️ Télécharger la dernière version (.dmg, Apple Silicon)](https://github.com/NessenGoinden/Mijo/releases/latest)** · [Code source](https://github.com/NessenGoinden/Mijo) · Licence MIT

**Transformez vos liens Instagram de recettes en une bibliothèque personnelle, puis laissez l'application tirer vos menus de la semaine.**
Tout tourne **sur votre Mac**, gratuitement, sans compte, sans serveur et sans abonnement.

- Collez un lien de post ou de reel Instagram → l'application récupère la description, la vidéo et les images.
- Si la recette est dans la description, elle l'utilise directement. Sinon, elle **transcrit la voix** (Whisper, en local) et **lit le texte affiché à l'écran** (framework Vision de macOS).
- Un modèle d'IA local (**Ollama**) rédige une recette structurée en français : titre, catégorie, étiquettes, portions, temps, ingrédients (quantités estimées signalées), étapes.
- Vous relisez et corrigez la recette avant de l'enregistrer.
- Bibliothèque : recherche par nom ou ingrédient, filtres par catégorie et étiquette, favoris, modification, suppression, export/import JSON pour s'échanger des recettes entre amis.
- Menu de la semaine : nombre de repas, filtres (catégorie, étiquettes, temps max), tirage aléatoire **sans doublon** qui varie protéines et cuisines, re-tirage d'un seul créneau, liste de courses agrégée par rayon, copie en texte.

Technologies, toutes libres et gratuites : [yt-dlp](https://github.com/yt-dlp/yt-dlp) (récupération), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (transcription), Apple Vision (OCR), [Ollama](https://ollama.com) (IA locale), SQLite (stockage), FastAPI + [pywebview](https://pywebview.flowrl.com) (interface native).

---

## Installation pour un ami (sans rien connaître au code)

### Option A — le fichier `.dmg` (le plus simple)

1. Ouvrez `Nourriture-x.y.z-arm64.dmg` et glissez **Nourriture** dans **Applications**.
2. Première ouverture : macOS affiche « Apple ne peut pas vérifier que cette app ne contient pas de logiciel malveillant » parce que l'app n'est pas signée par un compte développeur payant.
   **Clic droit sur Nourriture → Ouvrir → Ouvrir.** Si le bouton n'apparaît pas : *Réglages Système → Confidentialité et sécurité*, puis **Ouvrir quand même** en bas de page. C'est à faire une seule fois.
3. Installez **Ollama** (gratuit) : <https://ollama.com/download>. Ouvrez-le une fois : il se place dans la barre des menus.
4. Dans Nourriture → **Réglages**, cliquez **Télécharger le modèle** (Qwen 2.5 7B, ≈ 4,7 Go, une seule fois). Sur un Mac avec 8 Go de RAM, choisissez plutôt un modèle 3B ou 4B dans la liste.
5. Le modèle de transcription Whisper (≈ 500 Mo) se télécharge automatiquement au premier import.

Le `.dmg` est construit pour les Mac **Apple Silicon** (M1 à M5). Pour un Mac Intel, utilisez l'option B.

### Option B — le script d'installation (Intel ou Apple Silicon)

1. Décompressez le dossier du projet, puis **double-cliquez sur `install.command`** (ou dans le Terminal : `bash install.sh`).
   Le script installe `uv` (gestionnaire Python gratuit), Python 3.12 et les dépendances dans `~/Library/Application Support/Nourriture/app`, puis crée **Nourriture.app** dans Applications.
2. Suivez ensuite les étapes 3 à 5 de l'option A.

### Configuration minimale

- macOS 12 ou plus récent, 8 Go de RAM (16 Go recommandés pour le modèle 7B).
- ≈ 6 Go d'espace disque pour les modèles.
- Une connexion internet pour récupérer les publications Instagram et télécharger les modèles la première fois. Ensuite, l'analyse se fait hors ligne.

---

## Utilisation

1. **Importer** → collez le lien (`https://www.instagram.com/reel/…` ou `/p/…`) → *Importer*.
   La progression s'affiche : récupération, analyse locale (transcription + OCR), rédaction par l'IA, finalisation. Comptez 30 s à 2 min selon le Mac.
2. **Vérifiez la recette** générée : titre, catégorie, protéine, portions, temps, ingrédients (les quantités estimées par l'IA sont cochées « Estimée »), étapes. Corrigez, puis **Enregistrer dans la bibliothèque**.
   Si la description contenait déjà la recette, la vidéo n'a pas été analysée (plus rapide) : un bouton permet de **ré-analyser avec la vidéo**.
3. **Bibliothèque** : recherchez, filtrez, ouvrez une recette (ajustez les portions à la volée), modifiez-la, mettez-la en favori.
4. **Menu de la semaine** : choisissez le nombre de repas et les filtres → *Tirer un menu*. Re-tirez un créneau avec 🎲, enregistrez le menu, cochez la liste de courses, copiez le tout pour l'envoyer par message.
5. **Exporter / Importer** : le fichier JSON (miniatures incluses) se dépose dans *Téléchargements* ; un ami l'importe depuis *Bibliothèque → Importer un fichier*.

### Si Instagram bloque la récupération

Instagram limite parfois les accès anonymes (« connexion requise », « réessayez plus tard »). Trois solutions :

- Réessayer quelques minutes plus tard.
- **Réglages → Instagram** : choisir un navigateur où vous êtes connecté à Instagram (Firefox fonctionne sans mot de passe ; Chrome demandera l'accès au trousseau ; Safari nécessite l'accès complet au disque pour le Terminal/l'app).
- **Importer → Saisie manuelle / fichier** : collez la description du post et/ou déposez la vidéo enregistrée. L'analyse locale et l'IA fonctionnent exactement pareil.

### Où sont mes données ?

`~/Library/Application Support/Nourriture/` : `recipes.db` (SQLite), `images/` (miniatures), `models/` (Whisper), `settings.json`, `logs/`.
Rien n'est envoyé sur internet, à part les requêtes vers Instagram pour récupérer la publication et vers Hugging Face / Ollama pour télécharger les modèles la première fois.

---

## Pour les développeurs

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # une fois
uv sync --group dev                                   # Python 3.12 + dépendances
uv run nourriture                                     # fenêtre native
uv run nourriture --browser                           # ou dans le navigateur
uv run pytest                                         # tests
bash packaging/build_app.sh                           # → dist/Nourriture.app + dist/Nourriture-<version>-arm64.dmg
python tests/make_sample_video.py sample.mp4          # fausse « reel » pour tester sans Instagram
```

Variables utiles : `NOURRITURE_DATA_DIR` (dossier de données), `NOURRITURE_PORT`, `NOURRITURE_DEBUG=1`.

### Architecture

```
nourriture/
  app.py            point d'entrée : serveur local (uvicorn) + fenêtre pywebview
  server.py         API FastAPI (recettes, import, menus, réglages, export/import)
  pipeline.py       orchestration d'un import : récupération → analyse → IA → brouillon
  fetch/instagram.py   yt-dlp puis page « embed » publique en secours
  analyze/media.py     PyAV : audio 16 kHz pour Whisper, images clés, miniatures
  analyze/transcribe.py faster-whisper (CPU, int8)
  analyze/ocr.py       Vision (VNRecognizeTextRequest) via PyObjC
  llm/ollama.py, llm/prompts.py   client Ollama avec sorties structurées (schéma JSON strict)
  menu.py           tirage varié (protéine, cuisine, catégorie, usage récent) + liste de courses
  db.py, models.py  SQLite + modèles Pydantic
  static/           interface (HTML/CSS/JS sans dépendance)
packaging/          spec PyInstaller, icône, script de build, LISEZ-MOI du .dmg
install.sh          installation « sources » avec uv (Intel ou Apple Silicon)
```

### Modèles recommandés

| Usage | Modèle Ollama | RAM | Taille |
|---|---|---|---|
| Recommandé | `qwen2.5:7b` | 16 Go | 4,7 Go |
| Mac 8 Go | `qwen2.5:3b` ou `gemma3:4b` | 8 Go | 1,9 – 3,3 Go |
| Transcription | Whisper `small` (défaut), `medium` ou `large-v3-turbo` pour plus de précision | — | 0,5 – 1,6 Go |

Licence MIT. Les marques Instagram, Apple et Ollama appartiennent à leurs propriétaires ; l'application n'est affiliée à aucun d'eux. Respectez les droits des créateurs dont vous enregistrez les recettes : l'auteur et le lien source sont conservés sur chaque fiche.
