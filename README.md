# Verge

**Catch heat, cold, and altitude danger before you feel it.**

Verge is a rugged climber's earpiece with the voice of a calm mountain guide.
It reads your body and your environment, and the moment you start heading into
danger it tells you — plainly — what's wrong and what to do. The AI runs fully
offline on a safety-critical operating system, so it works where there is no
signal and cannot simply crash. Advice is personalized to you: your body, your
fitness, and what you're wearing.

## How it works

```
sensors ──▶ monitor ──▶ anomaly check ──▶ AI advice ──▶ voice
(temp,      (30s        (code + model:     (local LLM,   (spoken
 pressure)   windows)    is this normal?)   personalized) in-ear)
```

1. **Sense** — temperature and pressure sensors stream readings to the device
   over UDP.
2. **Watch** — a monitor batches readings into short windows and checks each one
   for anomalies (out-of-range temperature, sensor disagreement, etc.).
3. **Decide** — when something is wrong, code determines the situation
   (hot vs. cold) and how urgent it is, rather than leaving that to the model.
4. **Advise** — a local language model turns the situation into short spoken
   guidance, tailored to the wearer's profile.
5. **Speak** — the advice is read aloud in the climber's ear.

## Personalization

Before a climb, the wearer fills in a one-time setup form. The device computes
body-surface metrics and stores a profile the advice reads, so the same reading
produces different guidance for a lean, lightly dressed climber than for a
heavier, layered one.

## Repository layout

| Path | What it is |
| --- | --- |
| `qnx/filesystem/root/setup_server.py` | One-time setup form (stdlib-only web server) that writes `profile.json`. |
| `qnx/pi/profile_brief.py` | Turns `profile.json` into a plain-language cold/heat tolerance brief for the advice model. |
| `qnx/pi/patch_advice.py` | Patches the device's advice script to decide hot/cold in code and inject the profile. |
| `qnx/pi/arm-setup-form.sh` | Brings up the device's demo network address and starts the form server. |
| `qnx/laptop/90-pi-setup-form` | Laptop hook that opens the form automatically over a direct cable. |
| `qnx/llama_prompt.sh` | Launcher for the local `llama.cpp` model on the QNX target. |
| `qnx/README.md` | Notes on running `llama.cpp` on QNX. |

The live sensor pipeline (UDP monitor, anomaly checker, voice advice scripts)
runs on the device itself.

## Stack

- **Raspberry Pi 5** running **QNX 8** — a real-time, safety-critical OS.
- **llama.cpp** serving a local **Llama 3.2 1B** model (fully offline).
- Python standard library only on the device — no internet, no package installs.
- Text-to-speech for the in-ear voice.

## Setup form

Run on the device:

```sh
python3 setup_server.py
```

Open `http://<device-address>:8080/` from a laptop on the same network, fill in
the wearer's details, and submit. The form validates input, computes the derived
metrics, and writes `profile.json` next to the script for the sensor pipeline to
read.

## What's next

- **Altitude-sickness warnings** from ascent rate (the pressure sensor already
  measures altitude).
- **Fall / "man-down" detection** via an accelerometer, with automatic alerts.
- **Off-grid SOS** over LoRa/mesh radio, and a group mode that warns a team lead
  when any climber is at risk.
- **Predictive advice** — "you're cooling fast, ~20 minutes to danger" — and
  two-way voice so the climber can ask questions.
- Smaller, tougher, longer-lasting hardware with bone-conduction audio.
