"""Live map for Admin (all vehicles) and Vendor (own vehicles)."""
from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user

from models import Duty, LocationPing, Site, Vendor, db, log
from realtime import broadcast_end, can_see
from views import role_guard

bp = Blueprint("live", __name__, url_prefix="/live")
bp.before_request(role_guard("admin", "vendor"))


@bp.route("/", endpoint="map")
def live_map():
    sites = Site.query.filter_by(active=True).order_by(Site.name).all()
    vendors = Vendor.query.filter_by(active=True).order_by(Vendor.name).all() if current_user.role == "admin" else []
    return render_template(
        "live.html", title="Live map",
        sites=[{"id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng} for s in sites],
        vendors=[{"id": v.id, "name": v.name} for v in vendors])


def _duty(duty_id):
    d = db.get_or_404(Duty, duty_id)
    if not can_see(current_user, d):
        abort(404)
    return d


@bp.route("/trail/<int:duty_id>")
def trail(duty_id):
    """Recent path of a vehicle on duty: [[lat, lng], ...] oldest first."""
    d = _duty(duty_id)
    minutes = min(request.args.get("minutes", 60, type=int), 24 * 60)
    since = datetime.utcnow() - timedelta(minutes=minutes)
    pings = (LocationPing.query.filter(LocationPing.duty_id == d.id, LocationPing.at >= since)
             .order_by(LocationPing.at).all())
    path = [[p.lat, p.lng] for p in pings]
    if d.lat is not None and (not path or path[-1] != [d.lat, d.lng]):
        path.append([d.lat, d.lng])
    return jsonify(path)


@bp.route("/duty/<int:duty_id>/end", methods=["POST"])
def end_duty(duty_id):
    """Force-end a duty (e.g. driver forgot to end it)."""
    d = _duty(duty_id)
    if d.ended_at is None:
        d.ended_at = datetime.utcnow()
        log("ended", "duty", d.id, f"{d.driver.name} in {d.vehicle.reg_no} (by {current_user.role})")
        db.session.commit()
        broadcast_end(d)
    return jsonify(ok=True)
