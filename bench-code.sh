#!/usr/bin/env bash
# bench-code.sh — Harness de benchmark LLM code generation
# Usage: ./bench-code.sh [--models m1:cloud,m2:local] [--prompts recipe-book] [--max-time 40]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─── Couleurs ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ─── Signal handling (Ctrl+C : skip modèle, 2x = quit) ───────────────────────
SKIP_CURRENT=0
QUIT_REQUESTED=0
CLAUDE_PID=""

_sigint_handler() {
  if [[ "$SKIP_CURRENT" -eq 1 ]]; then
    QUIT_REQUESTED=1
    echo -e "\n${RED}Second Ctrl+C — arrêt après nettoyage.${NC}" >&2
  else
    SKIP_CURRENT=1
    echo -e "\n${YELLOW}Ctrl+C — skip du modèle en cours (Ctrl+C à nouveau pour quitter).${NC}" >&2
  fi
  [[ -n "$CLAUDE_PID" ]] && kill "$CLAUDE_PID" 2>/dev/null || true
}
trap '_sigint_handler' INT

# ─── Config par défaut ────────────────────────────────────────────────────────
CONF="$SCRIPT_DIR/bench.conf"
if [[ ! -f "$CONF" ]]; then
  echo "❌ bench.conf introuvable — copie bench.conf.example vers bench.conf et édite-le"
  exit 1
fi
source "$CONF"

# ─── Parsing des arguments CLI (override bench.conf) ─────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --models)    IFS=',' read -ra MODELS   <<< "$2"; shift 2 ;;
    --prompts)   IFS=',' read -ra PROMPTS  <<< "$2"; shift 2 ;;
    --max-time) MAX_TIME="$2";                      shift 2 ;;
    --port)      PORT="$2";                            shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--models m1:cloud,m2:local] [--prompts recipe-book] [--max-time 30] [--port 8000]"
      exit 0 ;;
    *) echo "Option inconnue: $1"; exit 1 ;;
  esac
done

# ─── Répertoires ─────────────────────────────────────────────────────────────
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
RUN_DIR="$SCRIPT_DIR/results/runs/$TIMESTAMP"
mkdir -p "$RUN_DIR"

LOG_FILE="$RUN_DIR/run.log"

# ─── Détection timeout BSD vs GNU ────────────────────────────────────────────
if command -v gtimeout &>/dev/null; then
  TIMEOUT_CMD="gtimeout"
elif timeout --version &>/dev/null 2>&1; then
  TIMEOUT_CMD="timeout"
else
  # fallback : pas de timeout externe, on gère via kill
  TIMEOUT_CMD=""
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────
log() { echo -e "$*" | tee -a "$LOG_FILE"; }

get_journal() {
  local workdir="$1"
  if [[ -f "$workdir/JOURNAL.md" ]]; then
    cat "$workdir/JOURNAL.md"
  else
    echo "(JOURNAL.md absent — le modèle n'a pas tenu de journal)"
  fi
}

get_code_summary() {
  local workdir="$1"
  # Récupère les fichiers source principaux (max 200 lignes chacun, hors venv)
  local out=""
  for f in "$workdir"/*.py "$workdir"/*.js "$workdir/static"/*.js "$workdir/static"/*.html "$workdir"/*.html; do
    [[ -f "$f" ]] || continue
    [[ "$f" == *"/venv/"* ]] && continue
    local relpath="${f#$workdir/}"
    out+="### $relpath\n\`\`\`\n$(head -n 200 "$f")\n\`\`\`\n\n"
  done
  if [[ -z "$out" ]]; then
    echo "(aucun fichier source trouvé dans le workdir)"
  else
    echo -e "$out"
  fi
}

write_debrief() {
  local outfile="$1"
  local model="$2"
  local prompt="$3"
  local ts_start="$4"
  local ts_end="$5"
  local duration="$6"
  local turns_used="$7"
  local time_budget="$8"
  local tokens_in="$9"
  local tokens_out="${10}"
  local claude_exit="${11}"
  local timed_out="${12}"
  local validator_exit="${13}"
  local validator_output="${14}"
  local completude="${15}"
  local qualite_code="${16}"
  local demarche="${17}"
  local total="${18}"
  local judge_comment="${19}"
  local verdict="${20}"

  cat > "$outfile" <<EOF
run:
  date: "$ts_start"
  prompt: "$prompt"
  model: "$model"
  max_time_budget_min: $time_budget

timing:
  start: "$ts_start"
  end: "$ts_end"
  duration_seconds: $duration

execution:
  turns_used: $turns_used
  tokens_in: $tokens_in
  tokens_out: $tokens_out
  exit_code: $claude_exit
  timed_out: $timed_out

validation:
  success: $([ "$validator_exit" -eq 0 ] && echo "true" || echo "false")
  exit_code: $validator_exit
  details: |
$(echo "$validator_output" | sed 's/^/    /')

scoring:
  completude: $completude
  qualite_code: $qualite_code
  demarche: $demarche
  total: $total
  judge_comment: "$judge_comment"

verdict: "$verdict"
EOF
}

run_judge() {
  local model_name="$1"
  local prompt_name="$2"
  local workdir="$3"
  local validator_exit="$4"
  local validator_output="$5"
  local analyze_model="${MODEL_ANALYZE%%:*}"

  local journal
  journal=$(get_journal "$workdir")
  local code_summary
  code_summary=$(get_code_summary "$workdir")

  local prompt_content
  prompt_content=$(cat "$SCRIPT_DIR/prompts/analyze.txt")
  prompt_content="${prompt_content//\$\{MODEL\}/$model_name}"
  prompt_content="${prompt_content//\$\{PROMPT_NAME\}/$prompt_name}"
  prompt_content="${prompt_content//\$\{VALIDATOR_EXIT\}/$validator_exit}"
  prompt_content="${prompt_content//\$\{VALIDATOR_OUTPUT\}/$validator_output}"
  prompt_content="${prompt_content//\$\{JOURNAL_CONTENT\}/$journal}"
  prompt_content="${prompt_content//\$\{CODE_CONTENT\}/$code_summary}"

  # Appel cloud uniquement pour le judge
  unset ANTHROPIC_BASE_URL 2>/dev/null || true
  unset ANTHROPIC_API_KEY  2>/dev/null || true

  claude \
    --model "$analyze_model" \
    --dangerously-skip-permissions \
    --output-format text \
    --print \
    "$prompt_content" \
    2>/dev/null || echo "(judge unavailable)"
}

parse_scores() {
  local analysis="$1"
  # Extrait la ligne de données dans le bloc <!-- SCORES ... -->
  local scores_block
  scores_block=$(echo "$analysis" | python3 -c "
import sys, re
content = sys.stdin.read()
m = re.search(r'<!-- SCORES\n.*?\n(.+?)\n-->', content, re.DOTALL)
if m:
    # Prendre la dernière ligne non-vide avant -->
    lines = [l for l in m.group(0).split('\n') if l.strip() and 'SCORES' not in l and '-->' not in l and '<!--' not in l]
    print(lines[-1] if lines else '')
" 2>/dev/null)
  IFS='|' read -r completude qualite_code demarche total judge_comment <<< "$scores_block"
  echo "${completude:-0} ${qualite_code:-0} ${demarche:-0} ${total:-0} ${judge_comment:-N/A}"
}

# ─── En-tête ─────────────────────────────────────────────────────────────────
log ""
log "bench-code — $(date)"
log "Models  : ${MODELS[*]}"
log "Prompts : ${PROMPTS[*]}"
# Convertir MAX_TIME (minutes) → secondes pour le timeout système
TIMEOUT_SECS=$(( MAX_TIME * 60 ))
log "Max time : ${MAX_TIME}min (${TIMEOUT_SECS}s) | Port: ${PORT}"
log "Results : $RUN_DIR"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Boucle principale ────────────────────────────────────────────────────────
for ENTRY in "${MODELS[@]}"; do
  MODEL_NAME="${ENTRY%%:*}"
  MODEL_TYPE="${ENTRY##*:}"
  MODEL_SLUG="${MODEL_NAME//[\/]/-}"

  [[ "$QUIT_REQUESTED" -eq 1 ]] && break

  # Setup modèle local
  if [[ "$MODEL_TYPE" == "local" ]]; then
    log "\n${YELLOW}=== $MODEL_NAME (local) ===${NC}"
    if ! lms ls 2>/dev/null | grep -q "$MODEL_NAME"; then
      log "${RED}❌ '$MODEL_NAME' introuvable dans lms — skip${NC}"
      continue
    fi
    lms unload --all >/dev/null 2>&1
    if ! lms load "$MODEL_NAME" --gpu 1.0 --yes >/dev/null 2>&1; then
      log "${RED}❌ Échec chargement '$MODEL_NAME' — skip${NC}"
      continue
    fi
    sleep 5
    export ANTHROPIC_BASE_URL="http://127.0.0.1:1234"
    export ANTHROPIC_API_KEY="lm-studio"
  else
    log "\n${YELLOW}=== $MODEL_NAME (cloud) ===${NC}"
    unset ANTHROPIC_BASE_URL 2>/dev/null || true
    unset ANTHROPIC_API_KEY  2>/dev/null || true
  fi

  for PROMPT_NAME in "${PROMPTS[@]}"; do
    [[ "$QUIT_REQUESTED" -eq 1 ]] && break
    SKIP_CURRENT=0

    PROMPT_FILE="$SCRIPT_DIR/prompts/${PROMPT_NAME}.md"
    if [[ ! -f "$PROMPT_FILE" ]]; then
      log "${RED}❌ Prompt introuvable: $PROMPT_FILE — skip${NC}"
      continue
    fi

    RUN_NAME="${MODEL_SLUG}__${PROMPT_NAME}"
    MODEL_RUN_DIR="$RUN_DIR/$RUN_NAME"
    WORKDIR="$MODEL_RUN_DIR/workspace"
    DEBRIEF="$MODEL_RUN_DIR/debrief.yaml"
    ANALYSIS_FILE="$MODEL_RUN_DIR/analysis.md"
    TRACE_LOG="$MODEL_RUN_DIR/trace.jsonl"
    TOKENS_FILE="$MODEL_RUN_DIR/tokens.txt"
    mkdir -p "$WORKDIR"

    log "\n▶ $MODEL_NAME / $PROMPT_NAME"

    # ── Créer le venv Python et pré-installer les dépendances de base ───────
    VENV_DIR="$MODEL_RUN_DIR/venv"
    log "  Création du venv Python..."
    uv venv "$VENV_DIR" --quiet
    uv pip install --python "$VENV_DIR" fastapi uvicorn --quiet
    VENV_PYTHON="$VENV_DIR/bin/python"
    log "  Venv prêt : $VENV_PYTHON (fastapi, uvicorn pré-installés)"

    TS_START=$(date +%Y-%m-%dT%H:%M:%S)
    START_SEC=$(date +%s)

    [[ "${DISABLE_CACHING:-1}" == "1" ]] && export DISABLE_PROMPT_CACHING=1

    # ── Construire le prompt avec le workdir et venv injectés ────────────────
    INJECTED_PROMPT="Current working directory: ${WORKDIR}
All files MUST be created in THIS directory using absolute paths.
Never write to ~/.claude/ or any other directory.

A Python virtual environment is ready at: ${VENV_DIR}
Use this interpreter for everything: ${VENV_PYTHON}
fastapi and uvicorn are already installed in this venv.
You may install additional packages with: uv pip install --python ${VENV_PYTHON} <package>
Do NOT use pip install --system or --break-system-packages.

$(cat "$PROMPT_FILE")"

    # ── Lancer Claude Code depuis le workdir ────────────────────────────────
    CLAUDE_FIFO=$(mktemp -u)
    mkfifo "$CLAUDE_FIFO"
    set +e

    # Note: --max-time n'existe pas dans claude --print, le budget est géré par --timeout
    if [[ -n "$TIMEOUT_CMD" ]]; then
      (cd "$WORKDIR" && $TIMEOUT_CMD "$TIMEOUT_SECS" claude \
        --model "$MODEL_NAME" \
        --dangerously-skip-permissions \
        --output-format stream-json \
        --verbose \
        --print \
        "$INJECTED_PROMPT") \
        > "$CLAUDE_FIFO" 2>/dev/null &
    else
      (cd "$WORKDIR" && claude \
        --model "$MODEL_NAME" \
        --dangerously-skip-permissions \
        --output-format stream-json \
        --verbose \
        --print \
        "$INJECTED_PROMPT") \
        > "$CLAUDE_FIFO" 2>/dev/null &
    fi
    CLAUDE_PID=$!

    # Parser le stream-json pour extraire turns/tokens
    python3 "$SCRIPT_DIR/stream-parser.py" "$TRACE_LOG" "$TOKENS_FILE" < "$CLAUDE_FIFO"

    wait "$CLAUDE_PID"
    CLAUDE_EXIT=$?
    CLAUDE_PID=""
    rm -f "$CLAUDE_FIFO"
    set -e

    END_SEC=$(date +%s)
    TS_END=$(date +%Y-%m-%dT%H:%M:%S)
    DURATION=$((END_SEC - START_SEC))

    TOKENS_IN="?"; TOKENS_OUT="?"; TURNS="?"
    [[ -f "$TOKENS_FILE" ]] && read -r TOKENS_IN TOKENS_OUT TURNS < "$TOKENS_FILE"

    TIMED_OUT="false"
    if [[ "$SKIP_CURRENT" -eq 1 && "$TURNS" == "?" ]]; then
      TURNS="skipped"
      TIMED_OUT="false"
    elif [[ "${CLAUDE_EXIT}" -eq 124 ]]; then
      TIMED_OUT="true"
    fi

    log "  Claude exit=${CLAUDE_EXIT} | turns=${TURNS} | tokens in=${TOKENS_IN} out=${TOKENS_OUT} | ${DURATION}s"

    # ── Déplacer le code généré dans WORKDIR ────────────────────────────────
    # Claude Code travaille dans le CWD courant — on a lancé depuis WORKDIR...
    # En réalité claude --print travaille dans le CWD du shell. On relance dans WORKDIR.
    # Note: le code est déjà dans WORKDIR car on a passé le prompt avec instructions de CWD.
    # Si pas de fichiers : le modèle n'a rien créé.

    CODE_FILES=$(find "$WORKDIR" -maxdepth 3 -type f ! -name "*.pyc" ! -path "*/__pycache__/*" 2>/dev/null | wc -l | tr -d ' ')
    log "  Fichiers générés: $CODE_FILES"

    # ── Lancer le validator ─────────────────────────────────────────────────
    VALIDATOR_EXIT=1
    VALIDATOR_OUTPUT=""
    if [[ "$CODE_FILES" -gt 0 ]]; then
      log "  Running validator..."
      VALIDATOR_SCRIPT="$SCRIPT_DIR/validators/${PROMPT_NAME}.sh"
      if [[ -f "$VALIDATOR_SCRIPT" ]]; then
        set +e
        VALIDATOR_OUTPUT=$(bash "$VALIDATOR_SCRIPT" "$WORKDIR" "$PORT" "$VENV_DIR" 2>&1)
        VALIDATOR_EXIT=$?
        set -e
        if [[ "$VALIDATOR_EXIT" -eq 2 ]]; then
          log "  ${RED}Validator: problème d'environnement (exit 2) — installer les dépendances${NC}"
          log "  ${YELLOW}Run: pip install playwright && playwright install chromium${NC}"
        else
          log "  Validator exit=${VALIDATOR_EXIT}"
        fi
      else
        VALIDATOR_OUTPUT="Validator introuvable: $VALIDATOR_SCRIPT"
        log "  ${RED}Validator introuvable${NC}"
      fi
    else
      VALIDATOR_OUTPUT="Aucun fichier généré — validator non lancé"
      log "  ${RED}Aucun code généré — validator skipped${NC}"
    fi

    # ── Déterminer le verdict ───────────────────────────────────────────────
    if [[ "$TIMED_OUT" == "true" ]]; then
      VERDICT="failure_timeout"
    elif [[ "$CLAUDE_EXIT" -ne 0 && "$TURNS" != "skipped" ]]; then
      VERDICT="failure_crash"
    elif [[ "$VALIDATOR_EXIT" -eq 0 ]]; then
      VERDICT="success"
    else
      VERDICT="failure_validation"
    fi

    # ── LLM Judge ──────────────────────────────────────────────────────────
    COMPLETUDE=0; QUALITE_CODE=0; DEMARCHE=0; TOTAL=0; JUDGE_COMMENT="N/A"
    ANALYSIS_OUTPUT=""

    if [[ -n "${MODEL_ANALYZE:-}" ]]; then
      log "  Running LLM judge..."
      ANALYSIS_OUTPUT=$(run_judge \
        "$MODEL_NAME" "$PROMPT_NAME" "$WORKDIR" \
        "$VALIDATOR_EXIT" "$VALIDATOR_OUTPUT" 2>/dev/null || echo "")
      echo "$ANALYSIS_OUTPUT" > "$ANALYSIS_FILE"

      if [[ -n "$ANALYSIS_OUTPUT" ]]; then
        read -r COMPLETUDE QUALITE_CODE DEMARCHE TOTAL JUDGE_COMMENT \
          <<< "$(parse_scores "$ANALYSIS_OUTPUT")"
      fi
      log "  Scores: complétude=${COMPLETUDE} qualité=${QUALITE_CODE} démarche=${DEMARCHE} total=${TOTAL}"
    fi

    # ── Écrire debrief.yaml ────────────────────────────────────────────────
    write_debrief \
      "$DEBRIEF" \
      "$MODEL_NAME" "$PROMPT_NAME" \
      "$TS_START" "$TS_END" "$DURATION" \
      "$TURNS" "$MAX_TIME" \
      "$TOKENS_IN" "$TOKENS_OUT" \
      "$CLAUDE_EXIT" "$TIMED_OUT" \
      "$VALIDATOR_EXIT" "$VALIDATOR_OUTPUT" \
      "$COMPLETUDE" "$QUALITE_CODE" "$DEMARCHE" "$TOTAL" "$JUDGE_COMMENT" \
      "$VERDICT"

    log "  debrief.yaml → $DEBRIEF"

    # ── Append history.jsonl ───────────────────────────────────────────────
    python3 -c "
import json
print(json.dumps({
  'date': '$TS_START',
  'run': '$TIMESTAMP',
  'model': '$MODEL_NAME',
  'type': '$MODEL_TYPE',
  'prompt': '$PROMPT_NAME',
  'duration_s': $DURATION,
  'turns': '$TURNS',
  'max_time': $MAX_TIME,
  'tokens_in': '$TOKENS_IN',
  'tokens_out': '$TOKENS_OUT',
  'validator_exit': $VALIDATOR_EXIT,
  'completude': $COMPLETUDE,
  'qualite_code': $QUALITE_CODE,
  'demarche': $DEMARCHE,
  'total': $TOTAL,
  'verdict': '$VERDICT'
}))
" >> "$SCRIPT_DIR/history.jsonl"

    # ── Résumé ligne ───────────────────────────────────────────────────────
    if [[ "$VERDICT" == "success" ]]; then
      STATUS_ICON="${GREEN}✅${NC}"
    else
      STATUS_ICON="${RED}❌${NC}"
    fi
    log "  ${STATUS_ICON} ${VERDICT} | score=${TOTAL}/20 | ${DURATION}s | turns=${TURNS}"

  done

  if [[ "$MODEL_TYPE" == "local" ]]; then
    lms unload --all >/dev/null 2>&1
  fi
done

# ─── Tableau récapitulatif ────────────────────────────────────────────────────
log "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "RESULTATS — $TIMESTAMP"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "%-45s %-8s %-7s %-8s %-10s %-10s %-10s %-8s\n" \
  "Run" "Verdict" "Turns" "Time(s)" "In tokens" "Out tokens" "Score/20" "Valid" | tee -a "$LOG_FILE"
echo "────────────────────────────────────────────────────────────────────────────────────────────────────────────────" | tee -a "$LOG_FILE"

for ENTRY in "${MODELS[@]}"; do
  MODEL_NAME="${ENTRY%%:*}"
  MODEL_SLUG="${MODEL_NAME//[\/]/-}"
  for PROMPT_NAME in "${PROMPTS[@]}"; do
    RUN_NAME="${MODEL_SLUG}__${PROMPT_NAME}"
    DEBRIEF="$RUN_DIR/$RUN_NAME/debrief.yaml"
    if [[ -f "$DEBRIEF" ]]; then
      python3 - "$DEBRIEF" "$RUN_NAME" <<'PYEOF' | tee -a "$LOG_FILE"
import sys, re
try:
    content = open(sys.argv[1]).read()
    def val(key, indent=r'\s*'):
        # Cherche la clé avec n'importe quelle indentation
        m = re.search(rf'^{indent}{re.escape(key)}:\s*(.+)$', content, re.MULTILINE)
        return m.group(1).strip().strip('"') if m else "?"
    verdict = val("verdict", indent=r'')   # racine, 0 indentation
    turns   = val("turns_used")
    dur     = val("duration_seconds")
    tin     = val("tokens_in")
    tout    = val("tokens_out")
    total   = val("total")
    v_ok    = val("success")
    print(f"{sys.argv[2]:<45} {verdict:<20} {turns:<7} {dur:<8} {tin:<10} {tout:<10} {total:<10} {v_ok:<8}")
except Exception as e:
    print(f"{sys.argv[2]:<45} ERROR: {e}")
PYEOF
    fi
  done
done

log "\n${GREEN}Résultats complets : $RUN_DIR${NC}"
log "history.jsonl mis à jour : $SCRIPT_DIR/history.jsonl"
