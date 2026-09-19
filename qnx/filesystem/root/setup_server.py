import errno
import html
import json
import math
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = 8080
PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.json")
MAX_BODY_BYTES = 64 * 1024


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
</head>
<body>
<h1>{html.escape(title)}</h1>
{body}
</body>
</html>
"""


FORM_PAGE = page("Thermal monitor setup", """<form method="post" action="/submit">
<h2>Profile</h2>
<p><label for="height_cm">Height in cm (100 to 250, required)</label> <input id="height_cm" name="height_cm" required></p>
<p><label for="weight_kg">Weight in kg (30 to 250, required)</label> <input id="weight_kg" name="weight_kg" required></p>
<p><label for="age">Age (13 to 100)</label> <input id="age" name="age"></p>
<p><label for="sex">Sex</label> <select id="sex" name="sex">
<option value="">Not specified</option>
<option value="m">Male</option>
<option value="f">Female</option>
</select></p>
<p><label for="fitness_level">Fitness level</label> <select id="fitness_level" name="fitness_level">
<option value="">Not specified</option>
<option value="low">Low</option>
<option value="moderate">Moderate</option>
<option value="high">High</option>
</select></p>
<p><label for="clothing_layers">Clothing layers (0 to 8)</label> <input id="clothing_layers" name="clothing_layers"></p>
<h2>Reaction time baseline</h2>
<p>Click the box to start a round. After a short random delay it turns green; click it again as soon as it does. Five rounds are needed. Clicking before it turns green voids that round.</p>
<p><button type="button" id="box"><svg width="240" height="120"><rect id="rect" width="240" height="120" fill="gray"></rect></svg></button></p>
<p id="status">Click the box to start round 1 of 5.</p>
<input type="hidden" id="baseline_ms" name="baseline_ms">
<p><button type="submit" id="submit" disabled>Save profile</button></p>
</form>
<script>
(function () {
  var ROUNDS = 5;
  var box = document.getElementById("box");
  var rect = document.getElementById("rect");
  var statusLine = document.getElementById("status");
  var baseline = document.getElementById("baseline_ms");
  var submit = document.getElementById("submit");
  var times = [];
  var state = "idle";
  var timer = null;
  var greenAt = 0;

  // The page carries no CSS, so the box colour is the SVG fill attribute.
  function setBox(fill, message) {
    rect.setAttribute("fill", fill);
    statusLine.textContent = message;
  }

  function startRound(prefix) {
    state = "waiting";
    setBox("red", prefix + "Round " + (times.length + 1) + " of " + ROUNDS + ": wait for green.");
    timer = setTimeout(function () {
      state = "green";
      greenAt = performance.now();
      setBox("green", "Click!");
    }, 1000 + Math.random() * 2000);
  }

  function finish() {
    state = "done";
    var kept = times.slice().sort(function (a, b) { return a - b; }).slice(0, ROUNDS - 1);
    var sum = 0;
    for (var i = 0; i < kept.length; i++) sum += kept[i];
    var mean = sum / kept.length;
    var rounded = times.map(function (t) { return Math.round(t); });
    baseline.value = mean.toFixed(1);
    box.disabled = true;
    submit.disabled = false;
    setBox("gray", "Baseline " + mean.toFixed(1) + " ms: mean of the fastest 4 of " + rounded.join(", ") + " ms. You can now save the profile.");
  }

  box.addEventListener("click", function () {
    if (state === "idle") {
      startRound("");
    } else if (state === "waiting") {
      clearTimeout(timer);
      startRound("Too early, round repeats. ");
    } else if (state === "green") {
      var ms = performance.now() - greenAt;
      times.push(ms);
      if (times.length === ROUNDS) {
        finish();
      } else {
        state = "idle";
        setBox("gray", Math.round(ms) + " ms. Click the box to start round " + (times.length + 1) + " of " + ROUNDS + ".");
      }
    }
  });
})();
</script>""")


def validate(fields):
    errors = []

    def raw(name):
        values = fields.get(name)
        return values[0].strip() if values else ""

    def number(name, low, high, required=False):
        text = raw(name)
        if text == "":
            if required:
                errors.append(f"{name} is required")
            return None
        try:
            value = float(text)
        except ValueError:
            value = math.nan
        if not (math.isfinite(value) and low <= value <= high):
            errors.append(f"{name} must be a number between {low} and {high}")
            return None
        return value

    def integer(name, low, high):
        text = raw(name)
        if text == "":
            return None
        try:
            value = int(text)
        except ValueError:
            value = None
        if value is None or not low <= value <= high:
            errors.append(f"{name} must be a whole number between {low} and {high}")
            return None
        return value

    def choice(name, allowed):
        text = raw(name)
        if text == "":
            return None
        if text not in allowed:
            errors.append(f"{name} must be one of: {', '.join(allowed)}")
            return None
        return text

    height_cm = number("height_cm", 100, 250, required=True)
    weight_kg = number("weight_kg", 30, 250, required=True)
    age = integer("age", 13, 100)
    sex = choice("sex", ("m", "f"))
    fitness_level = choice("fitness_level", ("low", "moderate", "high"))
    clothing_layers = integer("clothing_layers", 0, 8)
    baseline_ms = number("baseline_ms", 80, 2000, required=True)
    if errors:
        return None, errors

    bsa_m2 = 0.007184 * height_cm ** 0.725 * weight_kg ** 0.425
    profile = {
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "bsa_m2": bsa_m2,
        "sa_mass_ratio": bsa_m2 * 10000 / weight_kg,
        "age": age,
        "sex": sex,
        "fitness_level": fitness_level,
        "clothing_layers": clothing_layers,
        "baseline_ms": baseline_ms,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return profile, []


def write_profile(profile):
    # Sibling temp file, fsync, then rename: the sensor process can never
    # open a half-written profile.json, and a power cut after the rename
    # cannot leave an empty one behind.
    tmp_path = PROFILE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, PROFILE_PATH)


def error_page(errors):
    items = "".join(f"<li>{html.escape(e)}</li>\n" for e in errors)
    return page("Profile not saved", f"""<ul>
{items}</ul>
<p><a href="/">Back to the form</a></p>""")


def confirmation_page(profile):
    def display(value):
        if value is None:
            return "not provided"
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

    rows = "".join(
        f"<dt>{html.escape(key)}</dt><dd>{html.escape(display(value))}</dd>\n"
        for key, value in profile.items()
    )
    return page("Profile saved", f"""<p>Written to {html.escape(PROFILE_PATH)}</p>
<dl>
{rows}</dl>""")


class SetupHandler(BaseHTTPRequestHandler):
    # The server is single-threaded; without a socket timeout a client that
    # stalls mid-request would block everyone else indefinitely.
    timeout = 10

    def do_GET(self):
        if urlsplit(self.path).path != "/":
            self.send_error(404)
            return
        self.send_page(200, FORM_PAGE)

    def do_POST(self):
        if urlsplit(self.path).path != "/submit":
            self.send_error(404)
            return
        body = self.read_body()
        if body is None:
            self.send_page(400, error_page(["Missing or malformed request body"]))
            return
        profile, errors = validate(parse_qs(body, keep_blank_values=True))
        if errors:
            self.send_page(400, error_page(errors))
            return
        try:
            write_profile(profile)
        except OSError as e:
            self.send_page(500, error_page([f"Could not write {PROFILE_PATH}: {e}"]))
            return
        self.send_page(200, confirmation_page(profile))

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        # A bogus Content-Length would make read() wait for bytes that never come.
        if not 0 <= length <= MAX_BODY_BYTES:
            return None
        try:
            return self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            return None

    def send_page(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    try:
        server = HTTPServer(("0.0.0.0", PORT), SetupHandler)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            sys.exit(f"Port {PORT} is already in use. Stop whatever is listening on it and run this again.")
        sys.exit(f"Could not listen on port {PORT}: {e}")
    print(f"Listening on port {PORT}. Open http://<device address>:{PORT}/ from the laptop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
