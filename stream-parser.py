#!/usr/bin/env python3
"""
Lit le stream-json de Claude Code sur stdin.
Affiche la progression en temps réel sur stderr (visible dans le terminal).
Écrit le trace complet dans trace.jsonl.
Écrit turns/tokens dans tokens.txt à la fin.
"""
import sys
import json
import os
import time

trace_path = sys.argv[1]
tokens_path = sys.argv[2]

input_tokens = output_tokens = num_turns = "?"
turn_count = 0
start_time = time.time()

def elapsed():
    s = int(time.time() - start_time)
    return f"{s//60:02d}:{s%60:02d}"

with open(trace_path, "w") as trace:
    for line in sys.stdin:
        raw = line.rstrip("\n")
        if not raw:
            continue
        trace.write(raw + "\n")
        trace.flush()
        try:
            d = json.loads(raw)
            t = d.get("type", "")

            if t == "assistant":
                turn_count += 1
                for block in d.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        tool = block.get("name", "?")
                        inp  = block.get("input", {})
                        desc = ""
                        if "command" in inp:
                            desc = str(inp["command"])[:80]
                        elif "file_path" in inp:
                            desc = str(inp["file_path"])
                        elif "path" in inp:
                            desc = str(inp["path"])
                        elif "pattern" in inp:
                            desc = str(inp["pattern"])[:60]
                        print(f"  {elapsed()} [{turn_count:>2}] {tool:<12} {desc}", flush=True)
                    elif block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            first_line = text.split("\n")[0][:80]
                            print(f"  {elapsed()} [{turn_count:>2}] thinking    {first_line}", flush=True)

            elif t == "result":
                u = d.get("usage", {})
                input_tokens  = u.get("input_tokens", "?")
                output_tokens = u.get("output_tokens", "?")
                num_turns     = d.get("num_turns", turn_count)

        except Exception:
            pass

with open(tokens_path, "w") as f:
    f.write(f"{input_tokens} {output_tokens} {num_turns}\n")
