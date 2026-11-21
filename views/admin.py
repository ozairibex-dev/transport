"""Office Admin: sites, vendors, employees, fleet overview, change log."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from forms import Field, apply_login, form_values, login_fields, read_form
from models import AuditLog, Site, User, Vehicle, Vendor, db, log
from views import render_form, role_guard, site_options, status_badge, toggle_active

bp = Blueprint("admin", __name__, url_prefix="/admin")
bp.before_request(role_guard("admin"))

ADDRESS_MAP = {"lat": "lat", "lng": "lng", "addr": "address"}
HOME_MAP = {"lat": "home_lat", "lng": "home_lng", "addr": "home_address"}


def coords(lat, lng):
    return f"{lat:.5f}, {lng:.5f}" if lat is not None and lng is not None else "-"


# --------------------------------------------------------------------------- #
# Sites
# --------------------------------------------------------------------------- #
SITE_FIELDS = [
    Field("name", "Site name", required=True),
    Field("address", "Address", help="Search or click the map to set the location."),
    Field("lat", "Latitude", "float"),
    Field("lng", "Longitude", "float"),
    Field("active", "Active", "checkbox"),
]


@bp.route("/sites")
def sites():
    rows = [{
        "cells": [s.name, s.address or "-", coords(s.lat, s.lng),
                  sum(e.active for e in s.employees), status_badge(s.active)],
        "edit": url_for("admin.site_form", site_id=s.id),
        "toggle": url_for("admin.toggle", entity="site", obj_id=s.id),
        "active": s.active,
    } for s in Site.query.order_by(Site.name)]
    return render_template("list.html", title="Sites", tables=[{
        "new": url_for("admin.site_form"),
        "columns": ["Name", "Address", "Location", "Employees", "Status"], "rows": rows}])


@bp.route("/sites/new", methods=["GET", "POST"])
@bp.route("/sites/<int:site_id>", methods=["GET", "POST"])
def site_form(site_id=None):
    site = db.get_or_404(Site, site_id) if site_id else Site(active=True)
    if request.method == "POST":
        errors = read_form(site, SITE_FIELDS)
        if Site.query.filter(Site.name == site.name, Site.id != (site.id or 0)).first():
            errors.append("A site with that name already exists.")
        if not errors:
            is_new = site.id is None
            db.session.add(site)
            db.session.flush()
            log("created" if is_new else "updated", "site", site.id, site.name)
            db.session.commit()
            flash(f"Site '{site.name}' saved.", "ok")
            return redirect(url_for("admin.sites"))
        db.session.rollback()
        return render_form("Site", SITE_FIELDS, form_values(site, SITE_FIELDS), errors,
                           url_for("admin.sites"), ADDRESS_MAP)
    return render_form("Edit site" if site_id else "New site", SITE_FIELDS, form_values(site, SITE_FIELDS),
                       back=url_for("admin.sites"), map_cfg=ADDRESS_MAP)


# --------------------------------------------------------------------------- #
# Vendors (each vendor gets one portal login)
# --------------------------------------------------------------------------- #
VENDOR_FIELDS = [
    Field("name", "Company name", required=True),
    Field("contact_name", "Contact person"),
    Field("phone", "Phone", "tel"),
    Field("email", "Email", "email"),
]


@bp.route("/vendors")
def vendors():
    rows = [{
        "cells": [v.name, v.contact_name or "-", v.phone or "-",
                  sum(x.active for x in v.vehicles), sum(d.active for d in v.drivers),
                  v.login.username if v.login else "-", status_badge(v.active)],
        "edit": url_for("admin.vendor_form", vendor_id=v.id),
        "toggle": url_for("admin.toggle", entity="vendor", obj_id=v.id),
        "active": v.active,
    } for v in Vendor.query.order_by(Vendor.name)]
    return render_template("list.html", title="Vendors", tables=[{
        "new": url_for("admin.vendor_form"),
        "columns": ["Vendor", "Contact", "Phone", "Vehicles", "Drivers", "Login", "Status"], "rows": rows}])


@bp.route("/vendors/new", methods=["GET", "POST"])
@bp.route("/vendors/<int:vendor_id>", methods=["GET", "POST"])
def vendor_form(vendor_id=None):
    vendor = db.get_or_404(Vendor, vendor_id) if vendor_id else Vendor(active=True)
    user = (vendor.login if vendor_id else None) or User(role="vendor", active=True)
    is_new_user = user.id is None
    fields = VENDOR_FIELDS + login_fields(is_new_user)

    if request.method == "POST":
        errors = read_form(vendor, VENDOR_FIELDS)
        if Vendor.query.filter(Vendor.name == vendor.name, Vendor.id != (vendor.id or 0)).first():
            errors.append("A vendor with that name already exists.")
        errors += apply_login(user, is_new_user)
        if not errors:
            is_new = vendor.id is None
            vendor.active = user.active   # vendor + its login are enabled together
            db.session.add(vendor)
            db.session.flush()
            user.vendor_id, user.name, user.phone = vendor.id, vendor.contact_name or vendor.name, vendor.phone
            db.session.add(user)
            log("created" if is_new else "updated", "vendor", vendor.id, vendor.name)
            db.session.commit()
            flash(f"Vendor '{vendor.name}' saved.", "ok")
            return redirect(url_for("admin.vendors"))
        db.session.rollback()
        return render_form("Vendor", fields, form_values(None, fields), errors, url_for("admin.vendors"))

    values = form_values(vendor, VENDOR_FIELDS)
    values.update(username=user.username or "", active=vendor.active)
    return render_form("Edit vendor" if vendor_id else "New vendor", fields, values, back=url_for("admin.vendors"))


# --------------------------------------------------------------------------- #
# Employees
# --------------------------------------------------------------------------- #
def employee_fields(is_new):
    return [
        Field("name", "Full name", required=True),
        Field("employee_code", "Employee code"),
        Field("phone", "Phone", "tel"),
        Field("site_id", "Site", "select", required=True, options=site_options()),
        Field("home_address", "Home address", help="Pickup/drop point. Search or click the map."),
        Field("home_lat", "Home latitude", "float"),
        Field("home_lng", "Home longitude", "float"),
    ] + login_fields(is_new)


@bp.route("/employees")
def employees():
    q = User.query.filter_by(role="employee")
    site_id = request.args.get("site", type=int)
    if site_id:
        q = q.filter_by(site_id=site_id)
    rows = [{
        "cells": [e.employee_code or "-", e.name, e.site.name if e.site else "-", e.phone or "-",
                  e.home_address or coords(e.home_lat, e.home_lng), e.username, status_badge(e.active)],
        "edit": url_for("admin.employee_form", user_id=e.id),
        "toggle": url_for("admin.toggle", entity="employee", obj_id=e.id),
        "active": e.active,
    } for e in q.order_by(User.name)]
    return render_template("list.html", title="Employees", site_filter=True, sites=Site.query.order_by(Site.name).all(),
                           site_id=site_id, tables=[{
                               "new": url_for("admin.employee_form"),
                               "columns": ["Code", "Name", "Site", "Phone", "Home", "Username", "Status"],
                               "rows": rows}])


@bp.route("/employees/new", methods=["GET", "POST"])
@bp.route("/employees/<int:user_id>", methods=["GET", "POST"])
def employee_form(user_id=None):
    emp = db.get_or_404(User, user_id) if user_id else User(role="employee", active=True)
    if emp.role != "employee":
        return redirect(url_for("admin.employees"))
    is_new = emp.id is None
    fields = employee_fields(is_new)
    if request.method == "POST":
        errors = read_form(emp, fields) + apply_login(emp, is_new)
        if not errors:
            db.session.add(emp)
            db.session.flush()
            log("created" if is_new else "updated", "employee", emp.id, emp.name)
            db.session.commit()
            flash(f"Employee '{emp.name}' saved.", "ok")
            return redirect(url_for("admin.employees"))
        db.session.rollback()
        return render_form("Employee", fields, form_values(emp, fields), errors, url_for("admin.employees"), HOME_MAP)
    return render_form("Edit employee" if user_id else "New employee", fields, form_values(emp, fields),
                       back=url_for("admin.employees"), map_cfg=HOME_MAP)


# --------------------------------------------------------------------------- #
# Fleet overview (read-only - vendors manage their own vehicles/drivers)
# --------------------------------------------------------------------------- #
@bp.route("/fleet")
def fleet():
    vehicles = [{"cells": [v.reg_no, v.model or "-", v.seats or "-", v.vendor.name, status_badge(v.active)]}
                for v in Vehicle.query.join(Vendor).order_by(Vendor.name, Vehicle.reg_no)]
    drivers = [{"cells": [d.name, d.phone or "-", d.license_no or "-", d.vendor.name if d.vendor else "-",
                          status_badge(d.active)]}
               for d in User.query.filter_by(role="driver").order_by(User.name)]
    return render_template("list.html", title="Fleet", tables=[
        {"title": "Vehicles", "columns": ["Reg. no", "Model", "Seats", "Vendor", "Status"], "rows": vehicles},
        {"title": "Drivers", "columns": ["Name", "Phone", "License", "Vendor", "Status"], "rows": drivers},
    ])


# --------------------------------------------------------------------------- #
# Change log + enable/disable
# --------------------------------------------------------------------------- #
@bp.route("/log")
def audit():
    rows = [{"cells": [a.created_at.strftime("%Y-%m-%d %H:%M"), a.user.name if a.user else "-",
                       a.action, a.entity, a.detail or "-"]}
            for a in AuditLog.query.order_by(AuditLog.id.desc()).limit(300)]
    return render_template("list.html", title="Change log", tables=[
        {"columns": ["When (UTC)", "By", "Action", "What", "Detail"], "rows": rows}])


@bp.route("/toggle/<entity>/<int:obj_id>", methods=["POST"])
def toggle(entity, obj_id):
    if entity == "site":
        s = db.get_or_404(Site, obj_id)
        return toggle_active(s, "site", s.name, url_for("admin.sites"))
    if entity == "vendor":
        v = db.get_or_404(Vendor, obj_id)
        enabling = not v.active
        for u in v.users:   # disabling locks the vendor's portal + driver logins;
            if not enabling or u.role == "vendor":   # enabling restores only the portal login
                u.active = enabling
        return toggle_active(v, "vendor", v.name, url_for("admin.vendors"))
    if entity == "employee":
        e = db.get_or_404(User, obj_id)
        return toggle_active(e, "employee", e.name, url_for("admin.employees"))
    return redirect(url_for("main.dashboard"))
