# bench-code

Benchmark de génération de code — mesure la capacité d'un LLM à produire une application fonctionnelle from scratch, en mode autonome.

## Principe

1. Le script injecte un prompt de spec applicative dans Claude Code (`--dangerously-skip-permissions`)
2. Le LLM itère librement jusqu'au budget de turns
3. Un validator Playwright teste l'app générée de façon déterministe
4. Un LLM judge note le JOURNAL.md et le code produit
5. Les métriques sont loguées dans `debrief.yaml` et `history.jsonl`

Le LLM ne décide pas s'il a réussi. Le validator est juge unique du succès/échec.

## Setup

```bash
# Dépendances Python pour le validator
pip install playwright requests
playwright install chromium

# Config
cp bench.conf.example bench.conf
# Éditer bench.conf : models, prompts, timeouts
```

## Lancer un benchmark

```bash
# Avec la config bench.conf
./bench-code.sh

# Overrides CLI
./bench-code.sh --models claude-haiku-4-5-20251001:cloud --prompts recipe-book --max-turns 40

# Modèle local (LM Studio requis)
./bench-code.sh --models qwen3.5-9b:local
```

## Structure

```
bench-code/
├── bench-code.sh            # Script principal
├── bench.conf.example       # Config versionnée (copier → bench.conf)
├── bench.conf               # Config locale (gitignored)
├── prompts/
│   ├── recipe-book.md       # Spec de l'app injectée dans le LLM
│   └── analyze.txt          # Prompt du LLM judge
├── validators/
│   ├── recipe-book.sh       # Wrapper shell
│   └── recipe-book.py       # Tests Playwright (5 scénarios)
├── results/
│   └── runs/
│       └── YYYY-MM-DD_HHMMSS/
│           ├── run.log
│           └── <model>__<prompt>/
│               ├── debrief.yaml   # Métriques complètes du run
│               ├── analysis.md    # Rapport du LLM judge
│               ├── trace.jsonl    # Stream brut Claude Code (gitignored)
│               └── workspace/     # Code généré (gitignored)
├── history.jsonl            # Historique global de tous les runs
└── tasks/                   # Suivi du développement du harness
```

## Métriques

| Métrique | Source |
|---|---|
| `verdict` | validator exit code |
| `turns_used` | stream-json Claude Code |
| `duration_seconds` | wall-clock |
| `completude` /20 | LLM judge |
| `qualite_code` /20 | LLM judge |
| `demarche` /20 | LLM judge (JOURNAL.md) |
| `total` /20 | LLM judge |

### Verdicts

| Valeur | Condition |
|---|---|
| `success` | validator exit 0 |
| `failure_validation` | session terminée, validator exit 1 |
| `failure_timeout` | timeout global atteint |
| `failure_crash` | Claude Code exit code non-zéro |

## JOURNAL.md

Le prompt demande au LLM de tenir un journal pendant son travail :
- **Analyse** : compréhension du brief, choix d'architecture
- **Implémentation** : décisions techniques, fichiers créés
- **Tests & corrections** : erreurs rencontrées et corrections
- **Auto-évaluation** : niveau de confiance par critère

Ce journal est lu par le LLM judge pour noter la démarche (`demarche /20`).

## Ajouter un prompt/app

1. Créer `prompts/<nom>.md` (spec + instruction JOURNAL.md en tête)
2. Créer `validators/<nom>.py` (tests Playwright)
3. Créer `validators/<nom>.sh` (wrapper, 3 lignes)
4. Ajouter `"<nom>"` dans `PROMPTS` de `bench.conf`

## Modèles supportés

- **Cloud** : `model-id:cloud` — utilise l'API Anthropic (`ANTHROPIC_API_KEY`)
- **Local** : `model-id:local` — utilise LM Studio (`lms` CLI, `http://127.0.0.1:1234`)
