"""
Office Pick & Drop - staff transport management.

Run:
    pip install -r requirements.txt
    flask --app app seed        # creates the admin (+ demo data with --demo)
    python app.py               # http://localhost:5000
    python simulate.py          # (optional) drive demo vehicles around

See README.md for the full guide.
"""
import os

import click
from flask import Flask

from models import Site, User, Vehicle, Vendor, db, login_manager
from realtime import socketio


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///" + os.path.join(app.root_path, "transport.db")),
        # Map starts here when no site has coordinates yet ("lat,lng")
        MAP_CENTER=[float(x) for x in os.environ.get("MAP_CENTER", "20,0").split(",")],
        # Lax cookies: browsers won't send them on cross-site POSTs (basic CSRF protection)
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SAMESITE="Lax",
    )
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, async_mode="threading")

    from views import admin, auth, driver, live, main, vendor
    for module in (auth, main, admin, vendor, driver, live):
        app.register_blueprint(module.bp)

    @app.context_processor
    def inject_map_center():
        site = Site.query.filter(Site.lat.isnot(None)).first()
        return {"map_center": [site.lat, site.lng] if site else app.config["MAP_CENTER"],
                "map_zoom": 12 if site else 3}

    with app.app_context():
        db.create_all()

    app.cli.add_command(seed)
    return app


@click.command("seed")
@click.option("--demo", is_flag=True, help="Also add a demo site, vendor, vehicle, driver and employee.")
def seed(demo):
    """Create the first admin account (admin / admin123)."""
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", name="Office Admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        click.echo("Created admin  -> username: admin  password: admin123  (change it after login)")
    if demo and not Site.query.first():
        site = Site(name="Head Office", address="Demo address", lat=51.5072, lng=-0.1276)
        vendor = Vendor(name="Demo Transport Co", contact_name="Vendor Manager", phone="0000000")
        db.session.add_all([site, vendor])
        db.session.flush()
        for reg, model, seats in [("DEMO-101", "Toyota Hiace", 10), ("DEMO-102", "Suzuki APV", 7),
                                  ("DEMO-103", "Toyota Corolla", 4)]:
            db.session.add(Vehicle(vendor_id=vendor.id, reg_no=reg, model=model, seats=seats))
        for uname, role, extra in [
            ("vendor", "vendor", {}),
            ("driver", "driver", {"license_no": "LIC-001"}),
            ("driver2", "driver", {"license_no": "LIC-002"}),
            ("driver3", "driver", {"license_no": "LIC-003"}),
            ("employee", "employee", {"site_id": site.id, "employee_code": "E-001",
                                      "home_lat": 51.5155, "home_lng": -0.0922, "home_address": "Demo home"}),
        ]:
            u = User(username=uname, name=f"Demo {uname.title().replace('2', ' 2').replace('3', ' 3')}", role=role,
                     vendor_id=vendor.id if role in ("vendor", "driver") else None, **extra)
            u.set_password(f"{role}123")   # demo drivers all use driver123
            db.session.add(u)
        click.echo("Demo logins    -> vendor/vendor123, driver|driver2|driver3 / driver123, employee/employee123")
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    # HTTPS=1 serves a self-signed certificate (needs `pip install cryptography`).
    # Phones only allow GPS on HTTPS pages, so use this when testing drivers over Wi-Fi.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
                 debug=os.environ.get("FLASK_DEBUG") == "1", allow_unsafe_werkzeug=True,
                 ssl_context="adhoc" if os.environ.get("HTTPS") == "1" else None)
