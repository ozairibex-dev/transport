"""Tiny form helper so every screen can share one generic form template.

A form is just a list of `Field`s. `read_form()` validates request.form and
copies values onto a model object. No WTForms needed for a prototype.
"""
from dataclasses import dataclass, field

from flask import request

from models import User


@dataclass
class Field:
    name: str
    label: str
    type: str = "text"  # text|email|tel|int|float|password|select|checkbox|textarea|heading
    required: bool = False
    options: list = field(default_factory=list)   # for select: [(value, label), ...]
    help: str = ""


def form_values(obj, fields):
    """Values to pre-fill the form: submitted data on POST, object attributes otherwise."""
    if request.method == "POST":
        return {f.name: (f.name in request.form) if f.type == "checkbox" else request.form.get(f.name, "")
                for f in fields}
    return {f.name: "" if obj is None or getattr(obj, f.name, None) is None else getattr(obj, f.name)
            for f in fields if f.type not in ("password", "heading")}


def read_form(obj, fields, skip=()):
    """Validate request.form and assign onto obj. Returns a list of error messages."""
    errors = []
    for f in fields:
        if f.name in skip or f.type in ("password", "heading"):
            continue
        raw = request.form.get(f.name, "").strip()
        if f.type == "checkbox":
            setattr(obj, f.name, f.name in request.form)
            continue
        if f.required and not raw:
            errors.append(f"{f.label} is required.")
            continue
        if f.type in ("int", "float") or (f.type == "select" and raw.isdigit()):
            try:
                val = (int if f.type in ("int", "select") else float)(raw) if raw else None
            except ValueError:
                errors.append(f"{f.label} must be a number.")
                continue
        else:
            val = raw or None
        setattr(obj, f.name, val)
    return errors


# ---- shared login fields for vendor / driver / employee accounts ----------
def login_fields(is_new):
    return [
        Field("_login", "Login", "heading"),
        Field("username", "Username", required=True),
        Field("password", "Password", "password", required=is_new,
              help="" if is_new else "Leave blank to keep the current password."),
        Field("active", "Account active", "checkbox"),
    ]


def apply_login(user, is_new):
    """Validate username uniqueness + password. Returns errors."""
    errors = []
    username = request.form.get("username", "").strip().lower()
    clash = User.query.filter(User.username == username, User.id != (user.id or 0)).first()
    if clash:
        errors.append("That username is already taken.")
    pwd = request.form.get("password", "")
    if is_new and len(pwd) < 6:
        errors.append("Password must be at least 6 characters.")
    elif pwd and len(pwd) < 6:
        errors.append("Password must be at least 6 characters.")
    if not errors:
        user.username = username
        user.active = "active" in request.form
        if pwd:
            user.set_password(pwd)
    return errors
