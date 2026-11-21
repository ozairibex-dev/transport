"""Vendor portal: manage own vehicles and drivers."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from forms import Field, apply_login, form_values, login_fields, read_form
from models import User, Vehicle, db, log
from views import render_form, role_guard, status_badge, toggle_active

bp = Blueprint("vendor", __name__, url_prefix="/vendor")
bp.before_request(role_guard("vendor"))

VEHICLE_FIELDS = [
    Field("reg_no", "Registration no.", required=True),
    Field("model", "Make / model", help="e.g. Toyota Hiace"),
    Field("seats", "Passenger seats", "int", required=True),
    Field("active", "Active", "checkbox"),
]


def own(obj):
    """404 unless the record belongs to the logged-in vendor."""
    if obj.vendor_id != current_user.vendor_id:
        abort(404)
    return obj


# --------------------------------------------------------------------------- #
# Vehicles
# --------------------------------------------------------------------------- #
@bp.route("/vehicles")
def vehicles():
    rows = [{
        "cells": [v.reg_no, v.model or "-", v.seats or "-", status_badge(v.active)],
        "edit": url_for("vendor.vehicle_form", vehicle_id=v.id),
        "toggle": url_for("vendor.toggle", entity="vehicle", obj_id=v.id),
        "active": v.active,
    } for v in Vehicle.query.filter_by(vendor_id=current_user.vendor_id).order_by(Vehicle.reg_no)]
    return render_template("list.html", title="Vehicles", tables=[{
        "new": url_for("vendor.vehicle_form"), "columns": ["Reg. no", "Model", "Seats", "Status"], "rows": rows}])


@bp.route("/vehicles/new", methods=["GET", "POST"])
@bp.route("/vehicles/<int:vehicle_id>", methods=["GET", "POST"])
def vehicle_form(vehicle_id=None):
    v = own(db.get_or_404(Vehicle, vehicle_id)) if vehicle_id else Vehicle(vendor_id=current_user.vendor_id,
                                                                            active=True, seats=4)
    if request.method == "POST":
        errors = read_form(v, VEHICLE_FIELDS)
        if v.reg_no:
            v.reg_no = v.reg_no.upper()
            if Vehicle.query.filter(Vehicle.reg_no == v.reg_no, Vehicle.id != (v.id or 0)).first():
                errors.append("A vehicle with that registration already exists.")
        if not errors:
            is_new = v.id is None
            db.session.add(v)
            db.session.flush()
            log("created" if is_new else "updated", "vehicle", v.id, v.reg_no)
            db.session.commit()
            flash(f"Vehicle {v.reg_no} saved.", "ok")
            return redirect(url_for("vendor.vehicles"))
        db.session.rollback()
        return render_form("Vehicle", VEHICLE_FIELDS, form_values(v, VEHICLE_FIELDS), errors, url_for("vendor.vehicles"))
    return render_form("Edit vehicle" if vehicle_id else "New vehicle", VEHICLE_FIELDS,
                       form_values(v, VEHICLE_FIELDS), back=url_for("vendor.vehicles"))


# --------------------------------------------------------------------------- #
# Drivers (each driver has their own login)
# --------------------------------------------------------------------------- #
def driver_fields(is_new):
    return [
        Field("name", "Full name", required=True),
        Field("phone", "Phone", "tel", required=True),
        Field("license_no", "Driving license no."),
    ] + login_fields(is_new)


@bp.route("/drivers")
def drivers():
    rows = [{
        "cells": [d.name, d.phone or "-", d.license_no or "-", d.username, status_badge(d.active)],
        "edit": url_for("vendor.driver_form", user_id=d.id),
        "toggle": url_for("vendor.toggle", entity="driver", obj_id=d.id),
        "active": d.active,
    } for d in User.query.filter_by(role="driver", vendor_id=current_user.vendor_id).order_by(User.name)]
    return render_template("list.html", title="Drivers", tables=[{
        "new": url_for("vendor.driver_form"), "columns": ["Name", "Phone", "License", "Username", "Status"],
        "rows": rows}])


@bp.route("/drivers/new", methods=["GET", "POST"])
@bp.route("/drivers/<int:user_id>", methods=["GET", "POST"])
def driver_form(user_id=None):
    d = own(db.get_or_404(User, user_id)) if user_id else User(role="driver", vendor_id=current_user.vendor_id,
                                                               active=True)
    if d.role != "driver":
        abort(404)
    is_new = d.id is None
    fields = driver_fields(is_new)
    if request.method == "POST":
        errors = read_form(d, fields) + apply_login(d, is_new)
        if not errors:
            db.session.add(d)
            db.session.flush()
            log("created" if is_new else "updated", "driver", d.id, d.name)
            db.session.commit()
            flash(f"Driver '{d.name}' saved.", "ok")
            return redirect(url_for("vendor.drivers"))
        db.session.rollback()
        return render_form("Driver", fields, form_values(d, fields), errors, url_for("vendor.drivers"))
    return render_form("Edit driver" if user_id else "New driver", fields, form_values(d, fields),
                       back=url_for("vendor.drivers"))


@bp.route("/toggle/<entity>/<int:obj_id>", methods=["POST"])
def toggle(entity, obj_id):
    if entity == "vehicle":
        v = own(db.get_or_404(Vehicle, obj_id))
        return toggle_active(v, "vehicle", v.reg_no, url_for("vendor.vehicles"))
    if entity == "driver":
        d = own(db.get_or_404(User, obj_id))
        if d.role == "driver":
            return toggle_active(d, "driver", d.name, url_for("vendor.drivers"))
    abort(404)
