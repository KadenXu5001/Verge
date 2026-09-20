#!/usr/bin/env python3
"""Patch a copy of sensor_advice_server_voice_v3.sh:
  - code decides HEAT/COLD + severity (so the 1B model can't get it backwards),
  - the model speaks naturally, keeping the original few-sentence style,
  - the climber profile is injected so the advice fits the wearer.
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
    situation, severity, temp_line = "UNCLEAR", "watch it", "The temperature reading is unavailable."
elif temp > HI:
    situation = "HEAT"
    severity = "get out now" if temp > 35 else "get serious" if temp > 30 else "watch it"
    temp_line = "The air temperature is about %.0f C, above the safe range of %.0f to %.0f C." % (temp, LO, HI)
elif temp < LO:
    situation = "COLD"
    severity = "get out now" if temp < 10 else "get serious" if temp < 20 else "watch it"
    temp_line = "The air temperature is about %.0f C, below the safe range of %.0f to %.0f C." % (temp, LO, HI)
else:
    situation, severity = "UNCLEAR", "watch it"
    temp_line = "The air temperature is about %.0f C, within the safe range." % temp
'''

USER = '''user = "Situation: %s. Use the severity phrase: %s. %s" % (situation, severity, temp_line)
if climber:
    user += " " + climber
user += " Give your spoken advice now."
'''

EDITS = [
    # shell: run the profile helper
    (
        'anomaly_file="$3"\n',
        'anomaly_file="$3"\nbrief=$(python3 ' + HELPER + ' 2>/dev/null || true)\n',
    ),
    # shell: pass the brief into the prompt builder
    (
        'python3 - "$interval_file" "$anomaly_file" > "$request_file" <<\'PY\'',
        'CLIMBER_BRIEF="$brief" python3 - "$interval_file" "$anomaly_file" > "$request_file" <<\'PY\'',
    ),
    # py: import os
    (
        "import json, sys\ninterval = json.load(open(sys.argv[1]))",
        "import json, os, sys\ninterval = json.load(open(sys.argv[1]))",
    ),
    # py: decide situation + severity in code
    (
        "anomaly = json.load(open(sys.argv[2]))\n",
        "anomaly = json.load(open(sys.argv[2]))\n" + COMPUTE,
    ),
    # py: the model is told the situation, doesn't guess it
    (
        "Decide whether the dominant situation is COLD or HEAT. If both are present, speak to the one that will injure them sooner.\n",
        "You are told the situation (COLD or HEAT) and which severity phrase to use; speak to them and do not contradict them.\n",
    ),
    # py: inject the climber brief (keep original few-sentence format)
    (
        "say get out now.'''\n",
        "say get out now.'''\n"
        'climber = os.environ.get("CLIMBER_BRIEF", "").strip()\n'
        "if climber:\n"
        '    system += "\\n\\nThe climber you are guiding: " + climber + '
        '" Weigh their cold and heat tolerance when you choose the severity phrase and the steps."\n',
    ),
    # py: hand the model the computed facts, let it speak naturally
    (
        'user = json.dumps({"anomaly": anomaly, "interval_summary": interval.get("summary", {})}, separators=(",", ":"))\n',
        USER,
    ),
    # py: room for the fuller natural answer without truncating
    ('"max_tokens": 120', '"max_tokens": 200'),
    # py: steadier, less embellishment
    ('"temperature": 0.2', '"temperature": 0.1'),
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
