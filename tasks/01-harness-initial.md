# Task 01 : harness initial

## Contexte

Construire le harness bench-code en s'inspirant de benchMDL (multi-modèles, config, streaming, analyse).
Le benchmark mesure la capacité d'un LLM à générer une app fonctionnelle from scratch.

Différence clé vs benchMDL : ici le LLM génère du code applicatif (pas juste un CLAUDE.md),
et doit tracer son travail dans un JOURNAL.md pour permettre la notation qualitative.

## Objectif

Un harness opérationnel qui :
1. Itère sur N modèles x M prompts (comme benchMDL)
2. Lance Claude Code en mode autonome sur chaque combo
3. Capture le stream-json pour extraire turns/tokens
4. Lance le validator Playwright post-run
5. Fait noter le JOURNAL.md par un LLM judge
6. Produit debrief.yaml + summary.csv + history.jsonl

## Périmètre

**Fichiers concernés :**
- `bench-code.sh` — script principal
- `bench.conf.example` — config versionnée (models, variants, timeouts)
- `bench.conf` — config locale (gitignored)
- `prompts/recipe-book.md` — spec app injectée dans le LLM
- `prompts/analyze.txt` — prompt du LLM judge (note JOURNAL.md + validator output)
- `validators/recipe-book.sh` — wrapper shell
- `validators/recipe-book.py` — tests Playwright Python
- `.gitignore`
- `README.md`

**Hors périmètre :**
- Dashboard web de visualisation
- CI/CD
- Autres prompts/apps que recipe-book

## Plan technique

### bench-code.sh

Inspiré de `bench-models.sh` de benchMDL :

```
for MODEL in MODELS:
  for PROMPT in PROMPTS:
    - Créer RUNDIR/workspace/
    - Lancer claude --output-format stream-json (capture turns/tokens)
    - Lancer validator (exit 0/1)
    - Lancer LLM judge sur JOURNAL.md
    - Écrire debrief.yaml
    - Append history.jsonl
- Écrire summary.csv
- Afficher tableau récap
```

**Gestion modèles** : même format `name:cloud` / `name:local` (LM Studio via lms)
**Signal handling** : Ctrl+C skip modèle en cours, second Ctrl+C = quit
**Timeout** : via timeout BSD/GNU (détecter l'OS)

### JOURNAL.md — traçabilité du LLM

Le prompt injecté demande au LLM de tenir un journal dans `JOURNAL.md` :
- Phase de spec/analyse (ce qu'il a compris du brief)
- Phase d'implémentation (choix techniques, difficultés)
- Phase de tests/correction (erreurs rencontrées, corrections)
- Auto-évaluation finale

Ce fichier est récupéré après le run et noté par le LLM judge.

### Scoring

| Dimension | Source | Poids |
|---|---|---|
| Validation | validator exit code (binaire) | Critère éliminatoire |
| Complétude | LLM judge sur JOURNAL.md | /20 |
| Qualité code | LLM judge sur code généré | /20 |
| Efficacité | turns_used / turns_budget | indicatif |

### debrief.yaml

```yaml
run:
  date: "..."
  prompt: "recipe-book"
  model: "claude-haiku-4-5"
  max_turns_budget: 40
timing:
  start / end / duration_seconds
execution:
  turns_used / turns_budget / exit_code / timed_out
validation:
  success / exit_code / details
scoring:
  completude: 15
  qualite_code: 12
  judge_comment: "..."
verdict: "success"
```

### Prompt injecté — ajout JOURNAL.md

Le prompt app (recipe-book.md) est préfixé d'une instruction :
```
Au fur et à mesure de ton travail, tiens un journal dans JOURNAL.md :
- ## Analyse : ce que tu as compris du brief
- ## Implémentation : tes choix techniques
- ## Tests & corrections : erreurs rencontrées et corrections
- ## Auto-évaluation : ce qui fonctionne, ce qui manque
```

## Todo

- [x] Créer la structure de répertoires
- [x] Créer CLAUDE.md et template-task.md
- [ ] Créer `bench.conf.example`
- [ ] Créer `bench-code.sh` (boucle models x prompts, stream-json, signal handling)
- [ ] Créer `prompts/recipe-book.md` (spec + instruction JOURNAL.md)
- [ ] Créer `prompts/analyze.txt` (LLM judge : JOURNAL.md + code + validator output)
- [ ] Créer `validators/recipe-book.py` (5 scénarios Playwright)
- [ ] Créer `validators/recipe-book.sh` (wrapper)
- [ ] Créer `.gitignore`
- [ ] Créer `README.md`
- [ ] Tester le validator manuellement sur un workspace valide

## Tests

**Manuels :**
- [ ] `./bench-code.sh --help` affiche l'usage
- [ ] Run complet avec 1 modèle cloud produit un debrief.yaml valide
- [ ] `history.jsonl` contient une entrée après le run
- [ ] Le validator retourne exit 0 sur une app valide

## Notes

- Parsing turns : stream-json type `result` contient `num_turns` (voir benchMDL)
- Timeout macOS : `gtimeout` (coreutils) ou fallback via background + kill
- `bench.conf` gitignored comme dans benchMDL
- JOURNAL.md peut être absent si le LLM l'ignore — le judge doit gérer ce cas

## Statut final

- [ ] Run complet testé avec succès
- [ ] ✅ Terminé — déplacer vers `tasks/completed/`
