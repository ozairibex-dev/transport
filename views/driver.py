"""Driver: start/end duty and share live GPS (the sharing itself runs over Socket.IO)."""
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from models import Duty, Site, Vehicle, db, log
from realtime import broadcast, broadcast_end
from views import role_guard

bp = Blueprint("driver", __name__, url_prefix="/driver")
bp.before_request(role_guard("driver"))


def my_duty():
    return Duty.active().filter_by(driver_id=current_user.id).first()


def available_vehicles():
    """Vendor's active vehicles that no other driver is currently on duty with."""
    busy = {d.vehicle_id for d in Duty.active()}
    return [v for v in Vehicle.query.filter_by(vendor_id=current_user.vendor_id, active=True).order_by(Vehicle.reg_no)
            if v.id not in busy]


@bp.route("/")
def duty():
    d = my_duty()
    return render_template("driver.html", duty=d, vehicles=[] if d else available_vehicles(),
                           sites=Site.query.filter_by(active=True).order_by(Site.name).all())


@bp.route("/start", methods=["POST"])
def start():
    if my_duty():
        return redirect(url_for("driver.duty"))
    vehicle = db.session.get(Vehicle, request.form.get("vehicle_id", type=int) or 0)
    if not vehicle or vehicle not in available_vehicles():
        flash("That vehicle isn't available. Pick another one.", "error")
        return redirect(url_for("driver.duty"))
    site_id = request.form.get("site_id", type=int)
    d = Duty(driver_id=current_user.id, vehicle_id=vehicle.id,
             site_id=site_id if site_id and db.session.get(Site, site_id) else None)
    db.session.add(d)
    try:
        db.session.flush()
    except IntegrityError:          # someone took this vehicle a moment ago
        db.session.rollback()
        flash("That vehicle was just taken by another driver. Pick another one.", "error")
        return redirect(url_for("driver.duty"))
    log("started", "duty", d.id, f"{current_user.name} in {vehicle.reg_no}")
    db.session.commit()
    broadcast(d)
    return redirect(url_for("driver.duty"))


@bp.route("/end", methods=["POST"])
def end():
    d = my_duty()
    if d:
        d.ended_at = datetime.utcnow()
        log("ended", "duty", d.id, f"{current_user.name} in {d.vehicle.reg_no}")
        db.session.commit()
        broadcast_end(d)
        flash("Duty ended. Location sharing stopped.", "ok")
    return redirect(url_for("driver.duty"))


@bp.route("/api/state")
def api_state():
    """JSON for scripts / a future native app: current duty, available vehicles, sites."""
    d = my_duty()
    return jsonify(
        duty={"id": d.id, "vehicle": d.vehicle.reg_no, "site_id": d.site_id} if d else None,
        vehicles=[{"id": v.id, "reg_no": v.reg_no} for v in ([] if d else available_vehicles())],
        sites=[{"id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng}
               for s in Site.query.filter_by(active=True).order_by(Site.name)],
    )
