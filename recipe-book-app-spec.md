# Spec applicative — Carnet de recettes

> Fichier utilisé comme prompt injecté dans Claude Code pour le bench-code.
> Le modèle reçoit ce contenu intégralement et doit livrer une application fonctionnelle.

---

## Prompt Claude Code

Crée une application web de carnet de recettes. L'application doit être fonctionnelle, visuellement propre, et démarrable avec une seule commande.

### Stack technique

- **Backend** : Python, FastAPI, SQLite (via sqlite3 standard — pas d'ORM)
- **Frontend** : HTML + CSS + JavaScript vanilla (pas de framework, pas de build step)
- **Serveur** : Uvicorn sur le port 8000
- **Point d'entrée** : `python main.py` démarre tout

### Données initiales

Au premier démarrage, insère automatiquement 3 recettes de démonstration dans la base pour que l'application ne soit pas vide. Les recettes doivent avoir des données réalistes (ingrédients et étapes renseignés).

### Écran 1 — Liste des recettes

- Affiche toutes les recettes sous forme de grille de cards
- Chaque card contient : nom de la recette, temps de préparation (en minutes), nombre de portions
- Un champ de recherche en haut filtre les recettes par nom en temps réel (sans rechargement de page)
- Un bouton "Ajouter une recette" en haut à droite navigue vers le formulaire d'ajout
- Cliquer sur une card navigue vers le détail de la recette

### Écran 2 — Détail d'une recette

- Affiche : nom, temps de préparation, nombre de portions de base
- Un sélecteur de portions (x1 / x2 / x4) recalcule toutes les quantités des ingrédients dynamiquement en JavaScript, sans rechargement
- Liste des ingrédients avec quantité et unité
- Liste des étapes numérotées
- Un bouton "Supprimer" supprime la recette et revient à la liste
- Un lien "Retour" revient à la liste

### Écran 3 — Formulaire d'ajout

- Champs : nom (texte), temps de préparation (nombre, en minutes), portions (nombre)
- Section ingrédients : liste dynamique — un bouton "Ajouter un ingrédient" ajoute une ligne avec trois champs : quantité (nombre), unité (texte), nom (texte). Un bouton "×" sur chaque ligne permet de la supprimer
- Section étapes : liste dynamique — un bouton "Ajouter une étape" ajoute une zone de texte. Un bouton "×" sur chaque étape permet de la supprimer
- Bouton "Enregistrer" soumet le formulaire, sauvegarde en base, et redirige vers la liste
- Bouton "Annuler" revient à la liste sans sauvegarder

### API backend (consommée par le frontend en fetch)

| Méthode | Route | Description |
|---|---|---|
| GET | `/recipes` | Retourne la liste de toutes les recettes (id, name, prep_time, servings) |
| GET | `/recipes/{id}` | Retourne une recette complète avec ingrédients et étapes |
| POST | `/recipes` | Crée une nouvelle recette |
| DELETE | `/recipes/{id}` | Supprime une recette |

Le frontend est servi statiquement par FastAPI (`StaticFiles` ou route GET `/`).

### Exigences techniques

- L'application doit démarrer sans erreur avec `python main.py`
- La base SQLite est créée automatiquement au premier démarrage
- Les recettes seed sont insérées seulement si la base est vide
- La navigation entre écrans se fait en JavaScript (SPA minimaliste ou manipulation de `window.location`)
- Aucune dépendance externe autre que `fastapi` et `uvicorn` — pas de SQLAlchemy, pas de Pydantic v2 complexe, pas de bibliothèques JS

### Critères de succès

L'application est considérée réussie si :

1. `python main.py` démarre sans erreur sur le port 8000
2. La page principale affiche une liste de recettes non vide
3. Cliquer sur une recette affiche ses ingrédients et étapes
4. Le sélecteur de portions modifie les quantités affichées sans rechargement
5. Le formulaire d'ajout permet de créer une nouvelle recette qui apparaît ensuite dans la liste
6. La liste est toujours à jour après un rechargement complet de la page (`F5`)

---

## Validator Playwright — `validators/recipe-book.sh`

Ce script est exécuté par `bench-code.sh` après la session Claude Code.

### Scénario de test

```
1. Démarrer l'application (python main.py &), attendre que le port 8000 réponde
2. Ouvrir http://localhost:8000 dans Playwright headless

Test 1 — Liste non vide
  - Vérifier que la page contient au moins 1 card de recette

Test 2 — Navigation vers le détail
  - Cliquer sur la première card
  - Vérifier que la page affiche une liste d'ingrédients (élément présent dans le DOM)
  - Vérifier que la page affiche des étapes

Test 3 — Ajustement des portions
  - Sur la page détail, cliquer sur "x2"
  - Vérifier qu'au moins une quantité a changé dans le DOM

Test 4 — Ajout d'une recette
  - Naviguer vers le formulaire d'ajout
  - Remplir le nom : "Recette Test Bench"
  - Remplir le temps : 15
  - Remplir les portions : 2
  - Ajouter un ingrédient : 200 / g / farine
  - Ajouter une étape : "Mélanger les ingrédients"
  - Soumettre le formulaire
  - Vérifier que la liste contient "Recette Test Bench"

Test 5 — Persistance
  - Recharger la page (navigation vers /)
  - Vérifier que "Recette Test Bench" est toujours présente

3. Arrêter l'application
4. Retourner exit 0 si tous les tests passent, exit 1 sinon
```

### Implémentation recommandée

```python
# validators/recipe-book.py (appelé par recipe-book.sh)
from playwright.sync_api import sync_playwright
import subprocess, sys, time, requests

def wait_for_server(port=8000, timeout=30):
    for _ in range(timeout):
        try:
            requests.get(f"http://localhost:{port}", timeout=1)
            return True
        except:
            time.sleep(1)
    return False

workdir = sys.argv[1]
proc = subprocess.Popen(["python", "main.py"], cwd=workdir)

if not wait_for_server():
    proc.kill()
    sys.exit(1)

success = True
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    # ... tests ...
    browser.close()

proc.kill()
sys.exit(0 if success else 1)
```
