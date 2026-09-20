#!/usr/bin/env python3
"""Patch a copy of sensor_advice_server_voice_v3.sh into the hybrid advice:
  - code decides HEAT/COLD + severity and writes a guaranteed spoken opener,
  - the model writes only a short action sentence,
  - the climber profile is injected so the action fits the wearer.
Applied to the ORIGINAL script; exact-anchor edits, errors loudly if an anchor
is missing or ambiguous."""
import sys

HELPER = sys.argv[2] if len(sys.argv) > 2 else "/root/profile_brief.py"

COMPUTE = '''summary = interval.get("summary", {})
def _mean(n):
    m = summary.get(n, {}).get("mean")
    return m if isinstance(m, (int, float)) else None
LO, HI = 24.5, 26.5
temp = _mean("spa06_temp")
if temp is None:
    temp = _mean("dht_temp")
if temp is None:
    severity, temp_line, headword = "watch it", "The temperature reading is unavailable.", "Heads up."
    actions = "stop and reassess your condition"
elif temp > HI:
    severity = "get out now" if temp > 35 else "get serious" if temp > 30 else "watch it"
    temp_line = "It is hot, about %.0f degrees, above the safe range." % temp
    headword = "It's hot."
    actions = "get shade or breeze, loosen a layer, drink water if you have it, stop hard work"
elif temp < LO:
    severity = "get out now" if temp < 10 else "get serious" if temp < 20 else "watch it"
    temp_line = "It is cold, about %.0f degrees, below the safe range." % temp
    headword = "It's cold."
    actions = "get out of the wind, add a dry layer, cover head and hands, keep moving to shelter"
else:
    severity, temp_line, headword = "watch it", "The air is about %.0f degrees, within the safe range." % temp, "Heads up."
    actions = "stop and reassess your condition"
opener = headword + " " + severity[0].upper() + severity[1:] + "."
open(os.environ["OPENER_FILE"], "w").write(opener)
'''

USER = '''user = temp_line + " Good actions here: " + actions + ". In one short sentence, tell the climber the one or two most important of these to do now."
if climber:
    user += " " + climber
user += " Give only that one sentence."
'''

PARSER_OLD = '''python3 - "$response_file" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    text = data["choices"][0]["message"]["content"].strip()
    print(text or "Get serious. Stop and reassess your condition.")
except Exception:
    print("Get serious. Stop and reassess your condition.")
PY'''

PARSER_NEW = '''OPENER_FILE="$opener_file" python3 - "$response_file" <<'PY'
import json, os, sys
try:
    opener = open(os.environ["OPENER_FILE"]).read().strip()
except Exception:
    opener = ""
try:
    action = json.load(open(sys.argv[1]))["choices"][0]["message"]["content"].strip()
except Exception:
    action = ""
out = (opener + " " + action).strip()
print(out or "Get serious. Stop and reassess your condition.")
PY'''

INSTRUCTION_OLD = "Reply with only 3 to 6 short spoken sentences. In order: name the situation; use exactly one severity phrase: all clear, watch it, get serious, or get out now; explain why in human language; give two to four concrete next steps.\n"
INSTRUCTION_NEW = "Reply with only one short spoken sentence, under 20 words: the one or two most important actions to take now. Do not name the situation, do not use a severity phrase, do not use labels or preamble.\n"

EDITS = [
    # shell: run the profile helper and pick a temp file for the opener
    (
        'anomaly_file="$3"\n',
        'anomaly_file="$3"\nbrief=$(python3 ' + HELPER + ' 2>/dev/null || true)\nopener_file="/tmp/opener_$$.txt"\n',
    ),
    # shell: clean up the opener temp file too
    (
        'trap \'rm -f "$request_file" "$response_file"\' EXIT',
        'trap \'rm -f "$request_file" "$response_file" "$opener_file"\' EXIT',
    ),
    # shell: pass the brief and opener path into the prompt builder
    (
        'python3 - "$interval_file" "$anomaly_file" > "$request_file" <<\'PY\'',
        'OPENER_FILE="$opener_file" CLIMBER_BRIEF="$brief" python3 - "$interval_file" "$anomaly_file" > "$request_file" <<\'PY\'',
    ),
    # py: import os
    (
        "import json, sys\ninterval = json.load(open(sys.argv[1]))",
        "import json, os, sys\ninterval = json.load(open(sys.argv[1]))",
    ),
    # py: compute severity + opener in code, write the opener out
    (
        "anomaly = json.load(open(sys.argv[2]))\n",
        "anomaly = json.load(open(sys.argv[2]))\n" + COMPUTE,
    ),
    # py: the model no longer decides the situation
    (
        "Decide whether the dominant situation is COLD or HEAT. If both are present, speak to the one that will injure them sooner.\n",
        "You are told the situation already; do not restate it. Give only the next actions.\n",
    ),
    # py: model writes only a short action sentence
    (INSTRUCTION_OLD, INSTRUCTION_NEW),
    # py: inject the climber brief
    (
        "say get out now.'''\n",
        "say get out now.'''\n"
        'climber = os.environ.get("CLIMBER_BRIEF", "").strip()\n'
        "if climber:\n"
        '    system += "\\n\\nThe climber you are guiding: " + climber + '
        '" Choose the action to fit them."\n',
    ),
    # py: user message asks only for the action
    (
        'user = json.dumps({"anomaly": anomaly, "interval_summary": interval.get("summary", {})}, separators=(",", ":"))\n',
        USER,
    ),
    # py: short + fast (action only)
    ('"max_tokens": 120', '"max_tokens": 60'),
    ('"temperature": 0.2', '"temperature": 0.1'),
    # parser: prepend the code-written opener to the model's action
    (PARSER_OLD, PARSER_NEW),
]


def main():
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for old, new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"anchor not unique (found {n}x): {old!r}")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("patched OK:", path)


if __name__ == "__main__":
    main()
