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
| 2. Live tracking | Drivers share GPS from phone; admin sees all cars moving (filter by site/vendor); vendor sees own cars | ⏳ Next |
| 3. Rosters | Daily roster per site/shift: upload CSV, copy yesterday & edit, employee "not travelling" | Planned |
| 4. Assignment | Admin picks a car on the live map and drags employees onto it; suggested stop order (OSRM); driver stop list; employee sees car + ETA | Planned |
| 5. Operations | Ad-hoc requests, notifications, settings screen, reports per site/vendor/day | Planned |
| 6. Go-live | PostgreSQL, deployment, installable app (PWA), native driver app if background GPS needs it | Planned |

---

## Roles

| Role | Who | Can do (Phase 1) |
|---|---|---|
| **Admin** | Office administration | Manage sites, vendors (+ their portal login), employees; view all vehicles & drivers; view change log |
| **Vendor** | Transport company | Manage own vehicles and drivers (incl. driver logins) |
| **Driver** | Vendor's driver, own login | View profile (live GPS sharing + stop list in Phase 2/4) |
| **Employee** | Office staff | View their site and home point (live car + ETA in Phase 4) |

Rules agreed so far:
- Drivers have their own login (created by their vendor).
- **Only the Admin assigns** employees to vehicles.
- Nothing is hard-deleted; records are **disabled** so trip history stays intact.
- Disabling a vendor locks its portal and all its driver logins.
- Every create/update/enable/disable is written to the **change log**.

---

## Quick start

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
| driver | driver123 | `--demo` only |
| employee | employee123 | `--demo` only |

Open the app on a phone on the same Wi-Fi via `http://<your-pc-ip>:5000`.
Note: phone browsers only allow GPS ("📍 use my location") on **HTTPS** or `localhost`.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | Session signing. **Set a random value in production.** |
| `DATABASE_URL` | `sqlite:///transport.db` | Any SQLAlchemy URL, e.g. `postgresql://user:pass@host/db` |
| `MAP_CENTER` | `20,0` | Map start point (`lat,lng`) before any site has a location |
| `PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | off | Set `1` for auto-reload while developing |

---

## Project structure

```
app.py              App setup, config, `flask seed` command
models.py           Database tables: Site, Vendor, Vehicle, User, AuditLog
forms.py            Tiny form helper (field list -> validation -> model)
views/
  __init__.py       Shared helpers (role guard, enable/disable, form rendering)
  auth.py           Login, logout, change password
  main.py           Role-aware dashboard
  admin.py          Sites, vendors, employees, fleet overview, change log
  vendor.py         Vendor's vehicles and drivers
templates/
  base.html         Layout + role-based menu
  list.html         Generic table page (used by every list screen)
  form.html         Generic form page (+ map picker when needed)
  dashboard.html, login.html, password.html
static/js/map.js    Leaflet map, location picker, Nominatim search
```

### Data model

- **Site**: office location (name, address, lat/lng).
- **Vendor**: transport company; has many **Vehicles** and many driver **Users**.
- **Vehicle**: belongs to a vendor, **not** to a site (can serve any site on any day).
- **User**: one table for every login; `role` = `admin | vendor | driver | employee`.
  Role-specific columns (vendor_id, license_no, site_id, home_lat/lng…) are empty for other roles.
- **AuditLog**: who changed what and when.

### Adding a new screen (pattern)

1. Define a list of `Field(...)` in the view (see `views/vendor.py`).
2. List page: build `rows` and render `list.html`.
3. Form page: `read_form()` to validate/save, `render_form()` to show `form.html`.
   Pass `map_cfg={"lat": ..., "lng": ..., "addr": ...}` to get the map picker.
4. Call `log(...)` before `db.session.commit()` so the change is recorded.

---

## Free map services: limits to know

- **OpenStreetMap tiles**: free with attribution; heavy use should move to a self-hosted or paid tile server.
- **Nominatim** (address search): max ~1 request/second, no type-ahead. The app only searches on
  Enter/Search and saves coordinates, so each address is looked up once.
- **OSRM** (routing/ETAs, from Phase 4): the public demo server is not for production. For go-live,
  self-host OSRM (free, Docker) with your country's map extract.
