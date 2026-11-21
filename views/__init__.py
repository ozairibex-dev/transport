"""Shared helpers for the view blueprints."""
from flask import abort, flash, redirect, render_template, request
from flask_login import current_user

from models import Site, db, log, login_manager


def role_guard(*roles):
    """Use with blueprint.before_request to restrict a whole blueprint to some roles."""
    def guard():
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role not in roles:
            abort(403)
    return guard


def status_badge(active):
    return ("Active", "green") if active else ("Disabled", "slate")


def toggle_active(obj, entity, label, back):
    """Enable/disable instead of delete, so history (trips, logs) stays intact."""
    obj.active = not obj.active
    log("enabled" if obj.active else "disabled", entity, obj.id, label)
    db.session.commit()
    flash(f"{label} {'enabled' if obj.active else 'disabled'}.", "ok")
    return redirect(back)


def render_form(title, fields, values, errors=(), back=None, map_cfg=None):
    for e in errors:
        flash(e, "error")
    return render_template("form.html", title=title, fields=fields, values=values,
                           back=back or request.referrer, map_cfg=map_cfg)


def site_options():
    return [("", "- select site -")] + [(s.id, s.name) for s in Site.query.order_by(Site.name)]
