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


STYLE = """
:root{
  --paper:#f3efe7; --ink:#191817; --muted:#6f6a61;
  --line:#d7d1c4; --field:#fbf9f5; --accent:#c14a25;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.5;
}
.wrap{max-width:620px; margin:0 auto; padding:56px 24px 80px}
header{border-bottom:2px solid var(--ink); padding-bottom:18px; margin-bottom:34px}
.kicker{
  margin:0 0 10px; font-size:12px; font-weight:700; letter-spacing:.22em;
  text-transform:uppercase; color:var(--accent);
}
h1{
  margin:0; font-size:clamp(30px,7vw,46px); line-height:1.02;
  letter-spacing:-.02em; text-transform:uppercase; font-weight:800;
}
.lead{margin:16px 0 0; max-width:46ch; color:var(--muted); font-size:15px}
form{display:grid; gap:22px}
.row{display:grid; gap:22px; grid-template-columns:1fr 1fr}
@media(max-width:460px){.row{grid-template-columns:1fr}}
label{display:block}
.lab{
  display:block; margin:0 0 7px; font-size:11px; font-weight:700;
  letter-spacing:.14em; text-transform:uppercase; color:var(--muted);
}
input,select{
  width:100%; padding:12px 13px; font:inherit; color:var(--ink);
  background:var(--field); border:1px solid var(--line); border-radius:2px;
  -webkit-appearance:none; appearance:none;
}
input::placeholder{color:#b3ab9c}
input:focus,select:focus{outline:none; border-color:var(--ink)}
select{
  padding-right:38px;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%236f6a61' stroke-width='1.6'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:right 13px center;
}
button{
  justify-self:start; margin-top:4px; padding:14px 34px; font:inherit;
  font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--paper); background:var(--ink); border:0; border-radius:2px; cursor:pointer;
}
button:hover{background:var(--accent)}
.note{margin:0 0 26px; color:var(--muted); font-size:14px}
.summary{width:100%; border-collapse:collapse; margin:0 0 30px}
.summary th,.summary td{
  padding:13px 0; text-align:left; vertical-align:baseline;
  border-bottom:1px solid var(--line); font-size:15px;
}
.summary th{
  width:46%; font-size:11px; font-weight:700; letter-spacing:.12em;
  text-transform:uppercase; color:var(--muted);
}
.errs{list-style:none; margin:0 0 30px; padding:0; display:grid; gap:10px}
.errs li{
  padding:12px 14px; background:#fbeee9; border-left:3px solid var(--accent);
  color:#7a2f16; font-size:14px;
}
a.back{
  display:inline-block; font-size:12px; font-weight:700; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink); text-decoration:none;
  border-bottom:2px solid var(--accent); padding-bottom:3px;
}
"""


def page(title, body, kicker="Thermal Monitor"):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
<p class="kicker">{html.escape(kicker)}</p>
<h1>{html.escape(title)}</h1>
</header>
{body}
</div>
</body>
</html>
"""


FORM_PAGE = page("Setup Profile", """<p class="lead">Enter the wearer's measurements once. The device computes surface area and stores a profile the sensor reads.</p>
<form method="post" action="/submit">
<div class="row">
<label><span class="lab">Height &middot; cm</span><input name="height_cm" required inputmode="decimal" placeholder="100&ndash;250"></label>
<label><span class="lab">Weight &middot; kg</span><input name="weight_kg" required inputmode="decimal" placeholder="30&ndash;250"></label>
</div>
<div class="row">
<label><span class="lab">Age</span><input name="age" inputmode="numeric" placeholder="13&ndash;100"></label>
<label><span class="lab">Clothing layers</span><input name="clothing_layers" inputmode="numeric" placeholder="0&ndash;8"></label>
</div>
<div class="row">
<label><span class="lab">Sex</span><select name="sex">
<option value="">&mdash;</option>
<option value="m">Male</option>
<option value="f">Female</option>
</select></label>
<label><span class="lab">Fitness level</span><select name="fitness_level">
<option value="">&mdash;</option>
<option value="low">Low</option>
<option value="moderate">Moderate</option>
<option value="high">High</option>
</select></label>
</div>
<button type="submit">Save profile</button>
</form>""", kicker="One-time device setup")


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
    return page("Not Saved", f"""<p class="note">Nothing was written. Fix the following and try again.</p>
<ul class="errs">
{items}</ul>
<a class="back" href="/">Back to the form</a>""", kicker="Validation failed")


def confirmation_page(profile):
    def display(value):
        if value is None:
            return "not provided"
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

    rows = "".join(
        f'<tr><th>{html.escape(key.replace("_", " "))}</th><td>{html.escape(display(value))}</td></tr>\n'
        for key, value in profile.items()
    )
    return page("Profile Saved", f"""<p class="note">Written to {html.escape(PROFILE_PATH)} &middot; the sensor reads this file.</p>
<table class="summary">
{rows}</table>
<a class="back" href="/">Set up another</a>""", kicker="Setup complete")


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
