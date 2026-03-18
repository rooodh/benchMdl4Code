# bench-code — spécification du benchmark

## Objectif

Mesurer la capacité d'un modèle LLM à générer une application fonctionnelle de zéro, en mode autonome, sans intervention humaine. Le modèle s'exécute via Claude Code en mode yolo et s'arrête quand le budget de turns est atteint. La validation est externe et déterministe.

---

## Principe général

1. Le script crée un workdir temporaire isolé
2. Il injecte le prompt de spec applicative dans Claude Code (`--dangerously-skip-permissions`)
3. Claude Code itère librement jusqu'à `--max-turns`
4. À la fin de la session, le validator externe tourne sur le workdir
5. Les métriques sont loguées dans un `debrief.yaml`

Le modèle ne décide pas lui-même s'il a terminé. Le validator est juge unique.

---

## Structure du repo

```
bench-code/
├── bench-code.sh            # script principal
├── prompts/                 # specs des apps à générer (une par fichier)
│   └── recipe-book.md
├── validators/              # scripts de validation par prompt
│   └── recipe-book.sh       # lance Playwright, retourne 0 (succès) ou 1 (échec)
├── results/                 # gitignored sauf summary
│   └── runs/
│       └── YYYY-MM-DD_<prompt>_<model>/
│           ├── debrief.yaml
│           └── workspace/   # code généré — jetable
└── README.md
```

---

## Script principal — `bench-code.sh`

### Usage

```bash
./bench-code.sh --prompt prompts/recipe-book.md \
                --model <model-id-or-alias> \
                --max-turns 40
```

### Paramètres

| Paramètre | Défaut | Description |
|---|---|---|
| `--prompt` | requis | chemin vers le fichier de spec applicative |
| `--model` | requis | identifiant du modèle (ex. `claude-haiku-4`, `qwen35b-mlx`) |
| `--max-turns` | `40` | budget dur de turns Claude Code |
| `--port` | `8000` | port sur lequel l'app doit écouter |
| `--timeout` | `300` | timeout global en secondes (kill si dépassé) |

### Déroulement

```
1. Créer RUNDIR = results/runs/YYYY-MM-DD_<prompt>_<model>/
2. Créer WORKDIR = RUNDIR/workspace/
3. Enregistrer : timestamp_start, model, prompt, max_turns
4. Lancer Claude Code :
     cd WORKDIR && claude --max-turns $MAX_TURNS \
       --dangerously-skip-permissions \
       -p "$(cat $PROMPT_FILE)"
5. Enregistrer : timestamp_end, exit_code, turns réels (parsés depuis stdout)
6. Lancer le validator :
     ./validators/<prompt-name>.sh $WORKDIR $PORT
7. Enregistrer : validator_exit_code, validator_output
8. Écrire debrief.yaml
```

---

## Format `debrief.yaml`

```yaml
run:
  date: "2026-03-18T14:32:00"
  prompt: "recipe-book"
  model: "qwen35b-mlx"
  max_turns_budget: 40

timing:
  start: "2026-03-18T14:32:00"
  end: "2026-03-18T14:58:43"
  duration_seconds: 1603

execution:
  turns_used: 34
  turns_budget: 40
  exit_code: 0          # exit code Claude Code
  timed_out: false

validation:
  success: true         # validator exit code == 0
  exit_code: 0
  details: |            # stdout/stderr du validator
    ✓ liste affiche 3 recettes seed
    ✓ navigation vers le détail
    ✓ ajustement des portions
    ✓ ajout d'une nouvelle recette
    ✓ recette visible après reload

verdict: "success"      # success | failure_validation | failure_timeout | failure_crash
```

### Valeurs possibles de `verdict`

| Valeur | Condition |
|---|---|
| `success` | validator exit 0 |
| `failure_validation` | session terminée, validator exit 1 |
| `failure_timeout` | timeout global atteint |
| `failure_crash` | Claude Code exit code non-zéro |

---

## Validator — contrat

Chaque validator est un script exécutable qui :

- Reçoit en argument : `$WORKDIR` et `$PORT`
- Démarre l'application si elle ne tourne pas déjà
- Exécute les tests (Playwright headless ou curl/httpx)
- Arrête l'application
- Retourne `0` (succès) ou `1` (échec)
- Écrit les résultats sur stdout (capturés dans `debrief.yaml`)

Le validator est indépendant du code généré — il teste le comportement observable, pas l'implémentation.

---

## Métriques comparées entre modèles

| Métrique | Description |
|---|---|
| `verdict` | succès ou type d'échec |
| `turns_used` | efficacité — moins = mieux |
| `duration_seconds` | temps wall-clock total |
| `turns_used / max_turns_budget` | ratio d'utilisation du budget |

---

## Isolation et reproductibilité

- Chaque run dans un workdir séparé — aucun état partagé entre runs
- Le workdir est jetable (`rm -rf results/runs/*/workspace/` pour nettoyer)
- Les `debrief.yaml` sont conservés indéfiniment
- Le port est libéré après chaque run (le validator arrête le serveur)
