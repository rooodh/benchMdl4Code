Tout au long de ton travail, tiens un journal dans le fichier `JOURNAL.md` à la racine du projet.
Structure obligatoire du journal :

## Analyse
Ce que tu as compris du brief, les contraintes identifiées, les choix d'architecture.

## Implémentation
Tes décisions techniques, les bibliothèques utilisées, la structure des fichiers créés.

## Tests & corrections
Les erreurs rencontrées, comment tu les as corrigées, ce que tu as vérifié.

## Auto-évaluation
Ce qui fonctionne, ce qui pourrait manquer, ton niveau de confiance sur chaque critère de succès.

---

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
- Aucune dépendance externe autre que `fastapi` et `uvicorn`

### Critères de succès

1. `python main.py` démarre sans erreur sur le port 8000
2. La page principale affiche une liste de recettes non vide
3. Cliquer sur une recette affiche ses ingrédients et étapes
4. Le sélecteur de portions modifie les quantités affichées sans rechargement
5. Le formulaire d'ajout permet de créer une nouvelle recette qui apparaît ensuite dans la liste
6. La liste est toujours à jour après un rechargement complet de la page (`F5`)
