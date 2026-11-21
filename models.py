"""Database models and shared extensions.

One `User` table holds every login (admin / vendor / driver / employee).
Role-specific columns are simply left empty for roles that don't use them,
which keeps the prototype small and easy to change.
"""
from datetime import datetime

from flask_login import LoginManager, UserMixin, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

# autoflush off: forms set attributes before validation queries run
db = SQLAlchemy(session_options={"autoflush": False})
login_manager = LoginManager()
login_manager.login_view = "auth.login"

ROLES = ("admin", "vendor", "driver", "employee")


class Site(db.Model):
    """An office location. Employees, rosters and trips belong to a site."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    active = db.Column(db.Boolean, default=True, nullable=False)


class Vendor(db.Model):
    """A transport company that supplies vehicles and drivers."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    contact_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True, nullable=False)

    vehicles = db.relationship("Vehicle", backref="vendor", lazy=True)
    users = db.relationship("User", backref="vendor", lazy=True)

    @property
    def drivers(self):
        return [u for u in self.users if u.role == "driver"]

    @property
    def login(self):
        """The vendor's own portal account (first vendor-role user)."""
        return next((u for u in self.users if u.role == "vendor"), None)


class Vehicle(db.Model):
    """A vehicle owned by a vendor. Not tied to a site - it can serve any site."""
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"), nullable=False)
    reg_no = db.Column(db.String(30), unique=True, nullable=False)
    model = db.Column(db.String(100))
    seats = db.Column(db.Integer, default=4)
    active = db.Column(db.Boolean, default=True, nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # vendor + driver
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    # driver
    license_no = db.Column(db.String(50))
    # employee
    employee_code = db.Column(db.String(50))
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"))
    home_address = db.Column(db.String(255))
    home_lat = db.Column(db.Float)
    home_lng = db.Column(db.Float)

    site = db.relationship("Site", backref="employees")

    @property
    def is_active(self):  # used by Flask-Login to block disabled accounts
        return self.active

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Duty(db.Model):
    """A driver's on-duty session in one vehicle. Active while ended_at is NULL.

    Holds the latest position so the live map never has to scan the ping history.
    """
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id"), nullable=False, index=True)
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"))      # site being served (optional)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, index=True)

    # latest known position
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    speed = db.Column(db.Float)       # km/h
    heading = db.Column(db.Float)     # degrees, 0 = north
    accuracy = db.Column(db.Float)    # metres
    last_seen = db.Column(db.DateTime)
    last_ping_at = db.Column(db.DateTime)   # when a LocationPing was last stored

    driver = db.relationship("User")
    vehicle = db.relationship("Vehicle")
    site = db.relationship("Site")

    # Database-level guarantee: one active duty per vehicle and per driver,
    # even if two phones press "Start duty" at the same instant.
    __table_args__ = (
        db.Index("uq_active_duty_vehicle", "vehicle_id", unique=True,
                 sqlite_where=db.text("ended_at IS NULL"), postgresql_where=db.text("ended_at IS NULL")),
        db.Index("uq_active_duty_driver", "driver_id", unique=True,
                 sqlite_where=db.text("ended_at IS NULL"), postgresql_where=db.text("ended_at IS NULL")),
    )

    @classmethod
    def active(cls):
        return cls.query.filter(cls.ended_at.is_(None))


class LocationPing(db.Model):
    """Position history (thinned: at most one every ~15 s or 50 m) for trails and reports."""
    id = db.Column(db.Integer, primary_key=True)
    duty_id = db.Column(db.Integer, db.ForeignKey("duty.id"), nullable=False, index=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float)
    at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class AuditLog(db.Model):
    """Who changed what, and when. Rosters/trips change constantly, so keep a trail."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(30), nullable=False)   # created / updated / enabled / disabled
    entity = db.Column(db.String(30), nullable=False)   # site / vendor / vehicle / driver / employee
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


def log(action, entity, entity_id=None, detail=""):
    """Add an audit entry to the current session (committed with the change)."""
    uid = current_user.id if current_user and current_user.is_authenticated else None
    db.session.add(AuditLog(user_id=uid, action=action, entity=entity, entity_id=entity_id, detail=detail[:255]))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
