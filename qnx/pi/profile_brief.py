#!/usr/bin/env python3
"""Turn the wearer's profile.json into a plain-language cold/heat tolerance
brief for the advice model. Interpretation lives here (deterministic) so the
1B model only has to phrase advice, never reason about raw physiology."""
import json
import os
import sys

PROFILE_PATH = os.environ.get("PROFILE_JSON", "/data/home/qnxuser/profile.json")

GENERIC = "No climber profile is on file; advise for an average adult."


def brief(p):
    parts = []

    ratio = p.get("sa_mass_ratio")
    if isinstance(ratio, (int, float)):
        if ratio >= 265:
            parts.append(
                "lean with a high surface-to-mass ratio, so loses body heat "
                "quickly: more vulnerable in cold, copes better in heat"
            )
        elif ratio < 240:
            parts.append(
                "heavier-built with a low surface-to-mass ratio, so retains "
                "body heat: copes better in cold, more vulnerable in heat"
            )
        else:
            parts.append("average build for heat exchange")

    layers = p.get("clothing_layers")
    if isinstance(layers, int):
        if layers <= 1:
            parts.append("lightly dressed, so little insulation against cold")
        elif layers >= 4:
            parts.append("heavily layered, which traps heat and slows cooling")
        else:
            parts.append(f"wearing {layers} layers")

    fitness = p.get("fitness_level")
    age = p.get("age")
    reg = []
    if fitness == "high":
        reg.append("fit")
    elif fitness == "low":
        reg.append("low fitness")
    if isinstance(age, int) and age >= 65:
        reg.append("older, so regulates temperature less well")
    elif isinstance(age, int) and age <= 15:
        reg.append("young, so regulates temperature less well")
    if reg:
        parts.append(" and ".join(reg))

    if not parts:
        return GENERIC
    text = "The climber is " + "; ".join(parts) + "."
    return text[0].upper() + text[1:]


def main():
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            profile = json.load(f)
    except (OSError, ValueError):
        print(GENERIC)
        return
    print(brief(profile))


if __name__ == "__main__":
    main()
