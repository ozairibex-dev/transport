# Office Transport (Pick & Drop)

Staff pick & drop management for an office with **multiple sites**, run by the **Office Admin**, using
**vendor-supplied vehicles and drivers**. Rosters and routes change daily, so the system is designed
around a **live map and flexible trips** instead of fixed routes.

Built with free tools only: Python, Flask, Tailwind CSS, Leaflet + OpenStreetMap, Nominatim (address search).
No API keys needed.

---

## Status

| Phase | Scope | Status |
|---|---|---|
| 1. Foundation | Logins & roles, sites, vendors, vehicles, drivers, employees (home location on map), change log | ✅ Done |
| 2. Live tracking | Drivers share GPS from phone; admin sees all cars moving (filter by site/vendor); vendor sees own cars | ✅ Done |
| 3. Rosters | Daily roster per site/shift: upload CSV, copy yesterday & edit, employee "not travelling" | ⏳ Next |
| 4. Assignment | Admin picks a car on the live map and drags employees onto it; suggested stop order (OSRM); driver stop list; employee sees car + ETA | Planned |
| 5. Operations | Ad-hoc requests, notifications, settings screen, reports per site/vendor/day | Planned |
| 6. Go-live | PostgreSQL, deployment, installable app (PWA), native driver app if background GPS needs it | Planned |

---

## Roles

| Role | Who | Can do (Phase 1) |
|---|---|---|
| **Admin** | Office administration | Live map of all vehicles; manage sites, vendors (+ their portal login), employees; view all vehicles & drivers; end any duty; change log |
| **Vendor** | Transport company | Live map of own vehicles; manage own vehicles and drivers (incl. driver logins) |
| **Driver** | Vendor's driver, own login | Start duty in a vehicle → phone shares GPS live → end duty |
| **Employee** | Office staff | View their site and home point (live car + ETA in Phase 4) |

Rules agreed so far:
- One vehicle can only be on duty with one driver at a time, and a driver can only be on duty in one vehicle
  (enforced by the database, so two phones can't grab the same vehicle at once).
- Drivers have their own login (created by their vendor).
- **Only the Admin assigns** employees to vehicles.
- Nothing is hard-deleted; records are **disabled** so trip history stays intact.
- Disabling a vendor locks its portal and all its driver logins.
- Every create/update/enable/disable is written to the **change log**.

---

## Run on your laptop (one command)

You need **Python 3.10+** ([python.org](https://www.python.org/downloads/); on Windows tick
"Add python.exe to PATH") and **Git**.

```bash
git clone -b claude/exciting-meitner-9l12nm https://github.com/ozairibex-dev/transport.git
```
```bash
cd transport
```

**Windows:** double-click `start.bat` (or run `start.bat demo` in Command Prompt for demo data).
**Mac/Linux:** `./start.sh` (or `./start.sh demo`).

The script creates the virtual environment, installs libraries (only when `requirements.txt` changes),
creates the admin account and starts the app at http://localhost:5000. Run the same script every time.
To update later: `git pull`, then run the script again.

### Let phones on the road connect (free HTTPS tunnel)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. With the app running, in a second terminal: `cloudflared tunnel --url http://localhost:5000`
3. Open the printed `https://….trycloudflare.com` address on the phone, log in as a driver,
   tap **Start duty** and allow location. Watch it on the admin **Live map**.

The address changes each time the tunnel restarts and stops when the laptop sleeps, so this is for
testing and demos. **Before sharing it:** change the `admin` password and don't use the demo logins.
The session secret key is generated automatically on first run (`instance/secret_key`, not committed).

## Manual setup (alternative to the start scripts)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app seed --demo        # creates admin (+ demo data with --demo)
python app.py                      # open http://localhost:5000
```

Logins created by `seed`:

| Username | Password | Notes |
|---|---|---|
| admin | admin123 | Always created. **Change it after first login** (⚙ icon). |
| vendor | vendor123 | `--demo` only |
| driver, driver2, driver3 | driver123 | `--demo` only |
| employee | employee123 | `--demo` only |

### See live tracking without real drivers

With the server running, open a second terminal (activate `.venv` again) and run:

```bash
python simulate.py
```

It logs in as the demo drivers, starts their duty and drives them in loops around the first site.
Log in as `admin` → **Live map** to watch. `Ctrl+C` stops it and ends the duties.
Use `--drivers user:pass ...` for your own driver accounts and `--center lat,lng` to choose the area.

### Testing on a real phone

Phone browsers only share GPS on **HTTPS** pages (or `localhost`). To test over office Wi-Fi:

```bash
pip install cryptography
```
```bash
HTTPS=1 python app.py          # Windows PowerShell: $env:HTTPS="1"; python app.py
```

Open `https://<your-pc-ip>:5000` on the phone, accept the "not secure" warning (self-signed certificate),
log in as a driver and tap **Start duty**. For real use, put the app behind a proper HTTPS certificate.

### How live tracking works

1. Driver taps **Start duty** and picks a vehicle (and optionally the site they serve).
2. The phone sends its position every 5 s (and every 30 s while parked) over a WebSocket (Socket.IO).
3. The server saves the latest position on the duty and broadcasts it to the admin map and that vendor's map.
4. History is thinned to one point per 15 s or 50 m, used for the "Show trail" line (last 60 min).
5. Markers turn **amber** after 1 min without updates and **grey** after 5 min (phone locked, no signal…).

Known limit: a phone browser stops sending when the screen locks or the browser is closed. The page asks the
phone to keep the screen on. If this isn't reliable enough, Phase 6 wraps the driver screen in a native app
that can track in the background.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | auto-generated | Session signing key. If unset, a random key is created once in `instance/secret_key`. |
| `DATABASE_URL` | `sqlite:///transport.db` | Any SQLAlchemy URL, e.g. `postgresql://user:pass@host/db` |
| `MAP_CENTER` | `20,0` | Map start point (`lat,lng`) before any site has a location |
| `PORT` | `5000` | Web server port |
| `HTTPS` | off | Set `1` to serve a self-signed HTTPS certificate (phone GPS testing) |
| `FLASK_DEBUG` | off | Set `1` for auto-reload while developing |

---

## Project structure

```
app.py              App setup, config, `flask seed` command
models.py           Database tables: Site, Vendor, Vehicle, User, Duty, LocationPing, AuditLog
realtime.py         Socket.IO: receives driver GPS, pushes updates to live maps
simulate.py         Demo: drives vehicles around using real driver logins
forms.py            Tiny form helper (field list -> validation -> model)
views/
  __init__.py       Shared helpers (role guard, enable/disable, form rendering)
  auth.py           Login, logout, change password
  main.py           Role-aware dashboard
  admin.py          Sites, vendors, employees, fleet overview, change log
  vendor.py         Vendor's vehicles and drivers
  driver.py         Driver: start/end duty (+ JSON state for scripts / future app)
  live.py           Live map, vehicle trail, force-end duty
templates/
  base.html         Layout + role-based menu
  list.html         Generic table page (used by every list screen)
  form.html         Generic form page (+ map picker when needed)
  driver.html       Driver duty screen (GPS sharing)
  live.html         Live map + vehicle list with filters
  dashboard.html, login.html, password.html
static/js/map.js    Leaflet map, location picker, Nominatim search
```

### Data model

- **Site**: office location (name, address, lat/lng).
- **Vendor**: transport company; has many **Vehicles** and many driver **Users**.
- **Vehicle**: belongs to a vendor, **not** to a site (can serve any site on any day).
- **User**: one table for every login; `role` = `admin | vendor | driver | employee`.
  Role-specific columns (vendor_id, license_no, site_id, home_lat/lng…) are empty for other roles.
- **Duty**: a driver on duty in a vehicle (optionally for a site). Active while `ended_at` is empty;
  stores the latest position so the live map is fast.
- **LocationPing**: thinned position history per duty (for trails, later for reports/km).
- **AuditLog**: who changed what and when (includes duty start/end).

### Adding a new screen (pattern)

1. Define a list of `Field(...)` in the view (see `views/vendor.py`).
2. List page: build `rows` and render `list.html`.
3. Form page: `read_form()` to validate/save, `render_form()` to show `form.html`.
   Pass `map_cfg={"lat": ..., "lng": ..., "addr": ...}` to get the map picker.
4. Call `log(...)` before `db.session.commit()` so the change is recorded.

### Production notes

- The built-in server is fine for a pilot. For more users run with gunicorn (one worker, many threads,
  because live updates are held in memory per process):
  `pip install gunicorn && gunicorn -w 1 --threads 100 -b 0.0.0.0:5000 app:app`
- Run behind HTTPS (e.g. nginx or Caddy with a real certificate) so phones can share GPS.
- Change the `admin` password. Keep `instance/secret_key` (or set `SECRET_KEY`) so logins survive restarts.

---

## Free map services: limits to know

- **OpenStreetMap tiles**: free with attribution; heavy use should move to a self-hosted or paid tile server.
- **Nominatim** (address search): max ~1 request/second, no type-ahead. The app only searches on
  Enter/Search and saves coordinates, so each address is looked up once.
- **OSRM** (routing/ETAs, from Phase 4): the public demo server is not for production. For go-live,
  self-host OSRM (free, Docker) with your country's map extract.
