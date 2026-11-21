"""Realtime layer (Socket.IO): drivers push GPS, admin/vendor live maps receive it.

Rooms
  admin          every vehicle on duty
  vendor:<id>    that vendor's vehicles only
Events  (server -> browser)
  fleet:snapshot [duty, ...]   sent once on connect
  fleet:update   duty          position or duty change
  fleet:remove   {id}          duty ended
Events  (driver -> server)
  loc {lat, lng, speed(m/s), heading, accuracy}  -> ack {ok, error?}
"""
import math
from datetime import datetime

from flask_login import current_user
from flask_socketio import SocketIO, emit, join_room

from models import Duty, LocationPing, Vehicle, db

socketio = SocketIO()

MIN_UPDATE_SECONDS = 2     # ignore updates faster than this (spam guard)
PING_EVERY_SECONDS = 15    # store history at most this often...
PING_EVERY_METRES = 50     # ...unless the car moved at least this far


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def metres(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def duty_payload(d):
    v = d.vehicle
    return {
        "id": d.id, "vehicle_id": v.id, "reg_no": v.reg_no, "model": v.model, "seats": v.seats,
        "vendor_id": v.vendor_id, "vendor": v.vendor.name,
        "driver": d.driver.name, "driver_phone": d.driver.phone,
        "site_id": d.site_id, "site": d.site.name if d.site else None,
        "lat": d.lat, "lng": d.lng, "speed": d.speed, "heading": d.heading, "accuracy": d.accuracy,
        "last_seen": iso(d.last_seen), "started_at": iso(d.started_at),
    }


def visible_duties(user):
    """Active duties the user may see on the live map."""
    q = Duty.active()
    if user.role == "vendor":
        q = q.join(Vehicle).filter(Vehicle.vendor_id == user.vendor_id)
    elif user.role != "admin":
        return []
    return q.all()


def can_see(user, duty):
    return user.role == "admin" or (user.role == "vendor" and duty.vehicle.vendor_id == user.vendor_id)


def _rooms(duty):
    return ["admin", f"vendor:{duty.vehicle.vendor_id}"]


def broadcast(duty):
    socketio.emit("fleet:update", duty_payload(duty), to=_rooms(duty))


def broadcast_end(duty):
    socketio.emit("fleet:remove", {"id": duty.id}, to=_rooms(duty))


@socketio.on("connect")
def on_connect(auth=None):
    if not current_user.is_authenticated or not current_user.active:
        return False   # reject anonymous sockets
    if current_user.role == "admin":
        join_room("admin")
    elif current_user.role == "vendor":
        join_room(f"vendor:{current_user.vendor_id}")
    if current_user.role in ("admin", "vendor"):
        emit("fleet:snapshot", [duty_payload(d) for d in visible_duties(current_user)])


@socketio.on("loc")
def on_loc(data):
    if not current_user.is_authenticated or current_user.role != "driver":
        return {"ok": False, "error": "not_driver"}
    duty = Duty.active().filter_by(driver_id=current_user.id).first()
    if not duty:
        return {"ok": False, "error": "no_duty"}
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "error": "bad_position"}

    now = datetime.utcnow()
    if duty.last_seen and (now - duty.last_seen).total_seconds() < MIN_UPDATE_SECONDS:
        return {"ok": True, "throttled": True}

    def num(key, scale=1.0):
        try:
            return round(float(data[key]) * scale, 1) if data.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    moved = metres(duty.lat, duty.lng, lat, lng) if duty.lat is not None else 1e9
    duty.lat, duty.lng = lat, lng
    duty.speed = num("speed", 3.6)          # browser gives m/s
    duty.heading = num("heading")
    duty.accuracy = num("accuracy")
    duty.last_seen = now

    if (duty.last_ping_at is None or moved >= PING_EVERY_METRES
            or (now - duty.last_ping_at).total_seconds() >= PING_EVERY_SECONDS):
        db.session.add(LocationPing(duty_id=duty.id, lat=lat, lng=lng, speed=duty.speed, at=now))
        duty.last_ping_at = now

    db.session.commit()
    broadcast(duty)
    return {"ok": True}
