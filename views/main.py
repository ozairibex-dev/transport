"""Role-aware home page."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import Duty, Site, User, Vehicle, Vendor

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return redirect(url_for("main.dashboard" if current_user.is_authenticated else "auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    role = current_user.role
    stats, points = [], []
    if role == "driver":
        return redirect(url_for("driver.duty"))

    if role == "admin":
        stats = [
            ("On duty now", Duty.active().count(), url_for("live.map")),
            ("Sites", Site.query.filter_by(active=True).count(), url_for("admin.sites")),
            ("Vendors", Vendor.query.filter_by(active=True).count(), url_for("admin.vendors")),
            ("Vehicles", Vehicle.query.filter_by(active=True).count(), url_for("admin.fleet")),
            ("Drivers", User.query.filter_by(role="driver", active=True).count(), url_for("admin.fleet")),
            ("Employees", User.query.filter_by(role="employee", active=True).count(), url_for("admin.employees")),
        ]
        points = [{"lat": s.lat, "lng": s.lng, "label": s.name, "kind": "site"}
                  for s in Site.query.filter_by(active=True) if s.lat is not None]
        points += [{"lat": e.home_lat, "lng": e.home_lng, "label": e.name, "kind": "home"}
                   for e in User.query.filter_by(role="employee", active=True) if e.home_lat is not None]

    elif role == "vendor":
        v = current_user.vendor
        stats = [
            ("On duty now", Duty.active().join(Vehicle).filter(Vehicle.vendor_id == v.id).count(),
             url_for("live.map")),
            ("Vehicles", sum(x.active for x in v.vehicles), url_for("vendor.vehicles")),
            ("Drivers", sum(d.active for d in v.drivers), url_for("vendor.drivers")),
        ]

    elif role == "employee":
        s = current_user.site
        if s and s.lat is not None:
            points.append({"lat": s.lat, "lng": s.lng, "label": s.name, "kind": "site"})
        if current_user.home_lat is not None:
            points.append({"lat": current_user.home_lat, "lng": current_user.home_lng,
                           "label": "Home", "kind": "home"})

    return render_template("dashboard.html", stats=stats, points=points)
