# CLAUDE.md

## Commandes

```bash
# Lancer un benchmark
./bench-code.sh --prompt prompts/recipe-book.md --model <model-id> --max-turns 40

# Lancer le validator manuellement
./validators/recipe-book.sh <workdir> 8000

# Installer les dépendances Python du validator
pip install playwright requests
playwright install chromium
```

## Architecture

Harness de benchmark pour mesurer la capacité d'un LLM à générer une application fonctionnelle de zéro.

### Structure

```
bench-code/
├── bench-code.sh            # Script principal
├── prompts/                 # Specs des apps à générer (une par fichier)
│   └── recipe-book.md
├── validators/              # Scripts de validation par prompt
│   ├── recipe-book.sh       # Shell wrapper
│   └── recipe-book.py       # Implémentation Playwright
├── results/                 # gitignored sauf debrief.yaml
│   └── runs/
│       └── YYYY-MM-DD_<prompt>_<model>/
│           ├── debrief.yaml
│           └── workspace/   # code généré — jetable
├── tasks/
│   ├── template-task.md
│   └── completed/
├── CLAUDE.md
└── README.md
```

### Flux d'exécution

```
bench-code.sh
  ├── Crée RUNDIR et WORKDIR
  ├── Lance Claude Code (--dangerously-skip-permissions)
  ├── Parse les turns depuis stdout
  ├── Lance le validator
  └── Écrit debrief.yaml
```

### Format debrief.yaml

```yaml
run:
  date: "YYYY-MM-DDTHH:MM:SS"
  prompt: "recipe-book"
  model: "claude-haiku-4-5"
  max_turns_budget: 40

timing:
  start: "..."
  end: "..."
  duration_seconds: 1603

execution:
  turns_used: 34
  turns_budget: 40
  exit_code: 0
  timed_out: false

validation:
  success: true
  exit_code: 0
  details: |
    ...stdout du validator...

verdict: "success"   # success | failure_validation | failure_timeout | failure_crash
```

### Verdicts possibles

| Valeur | Condition |
|---|---|
| `success` | validator exit 0 |
| `failure_validation` | session terminée, validator exit 1 |
| `failure_timeout` | timeout global atteint |
| `failure_crash` | Claude Code exit code non-zéro |

## Stack technique

- **Scripts** : Bash (bench-code.sh, validators/*.sh)
- **Validators** : Python + Playwright (tests headless)
- **Prompts** : Markdown
- **Résultats** : YAML

## Workflow de développement — Task Context

Avant tout développement non trivial, créer un fichier de tâche dans `tasks/`.

### Procédure

1. **Créer** `tasks/<N>-<nom-court>.md` à partir de `tasks/template-task.md`
   - `<N>` = numéro séquentiel (voir le plus haut numéro dans `tasks/` ET `tasks/completed/`)
   - Nom court et descriptif
2. **Remplir** : contexte, objectif, périmètre, plan technique, todo initiale
3. **Afficher le contenu et attendre validation** avant de toucher au code
4. **Cocher** chaque item au fur et à mesure
5. **Une fois terminé** : déplacer vers `tasks/completed/`

### Structure

```
tasks/
  template-task.md
  <N>-<nom-en-cours>.md
  completed/
    <N>-<nom-terminé>.md
```

### Règles

- Une seule tâche **active** à la fois
- Pas de tâche pour des corrections triviales
- Les numéros sont uniques et **jamais réutilisés**

## Tests du validator

Le validator `recipe-book.py` utilise Playwright headless. Pour le lancer manuellement :

```bash
# Démarrer l'app dans un workdir
cd results/runs/<run>/workspace && python main.py &

# Lancer le validator
./validators/recipe-book.sh results/runs/<run>/workspace 8000
```

## Contrôle de sécurité — avant tout commit

- Ne jamais committer de credentials, tokens ou secrets
- `results/runs/*/workspace/` est gitignored (code généré jetable)
- Les `debrief.yaml` sont conservés et committés

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**.

```bash
rtk git status / log / diff
rtk ls <path>
rtk read <file>
rtk grep <pattern>
```
<!-- /rtk-instructions -->
