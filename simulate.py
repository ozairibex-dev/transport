"""
Drive demo vehicles around so the live map can be tested without real drivers.

It logs in as real driver accounts and uses exactly the same path as the phone
(start duty -> send GPS over Socket.IO), so it also exercises the real system.

Usage (server must be running):
    python simulate.py                                  # driver, driver2, driver3 / driver123
    python simulate.py --drivers ali:pass1 sara:pass2   # your own driver accounts
    python simulate.py --url http://localhost:5000 --center 24.86,67.00

Stop with Ctrl+C (duties are ended on exit).
"""
import argparse
import math
import random
import threading
import time

import requests
import socketio


def drive(url, username, password, center, index, stop):
    http = requests.Session()
    r = http.post(f"{url}/login", data={"username": username, "password": password}, allow_redirects=False)
    if r.status_code != 302 or "login" in r.headers.get("Location", ""):
        print(f"[{username}] login failed")
        return
    state = http.get(f"{url}/driver/api/state").json()
    if not state["duty"]:
        if not state["vehicles"]:
            print(f"[{username}] no free vehicle")
            return
        sites = [s for s in state["sites"] if s["lat"] is not None]
        for attempt in range(3):   # other simulated drivers may grab the same vehicle at once
            free = state["vehicles"]
            if not free:
                break
            http.post(f"{url}/driver/start", data={"vehicle_id": free[(index + attempt) % len(free)]["id"],
                                                   "site_id": sites[0]["id"] if sites else ""})
            state = http.get(f"{url}/driver/api/state").json()
            if state["duty"]:
                break
    if not state["duty"]:
        print(f"[{username}] couldn't get a vehicle")
        return
    if not center:
        sites = [s for s in state["sites"] if s["lat"] is not None]
        center = (sites[0]["lat"], sites[0]["lng"]) if sites else (51.5072, -0.1276)
    print(f"[{username}] on duty in {state['duty']['vehicle']}")

    sio = socketio.Client(reconnection=True)
    sio.connect(url, headers={"Cookie": "; ".join(f"{k}={v}" for k, v in http.cookies.items())},
                transports=["websocket", "polling"])

    # Drive a loop around the site: radius 1-4 km, ~30-45 km/h
    radius_km = 1 + index * 1.2
    speed_kmh = random.uniform(30, 45)
    angle = random.uniform(0, 2 * math.pi)
    step = 3  # seconds between updates
    while not stop.is_set():
        angle += (speed_kmh * step / 3600) / radius_km
        lat = center[0] + (radius_km / 111.0) * math.cos(angle)
        lng = center[1] + (radius_km / (111.0 * math.cos(math.radians(center[0])))) * math.sin(angle)
        heading = (math.degrees(angle) + 90) % 360
        sio.emit("loc", {"lat": lat, "lng": lng, "speed": speed_kmh / 3.6, "heading": heading, "accuracy": 8})
        stop.wait(step)

    sio.disconnect()
    http.post(f"{url}/driver/end")
    print(f"[{username}] duty ended")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:5000")
    ap.add_argument("--drivers", nargs="+", default=["driver:driver123", "driver2:driver123", "driver3:driver123"],
                    help="username:password pairs")
    ap.add_argument("--center", help="lat,lng to drive around (default: first site)")
    args = ap.parse_args()
    center = tuple(float(x) for x in args.center.split(",")) if args.center else None

    stop = threading.Event()
    threads = []
    for i, pair in enumerate(args.drivers):
        user, _, pwd = pair.partition(":")
        t = threading.Thread(target=drive, args=(args.url.rstrip("/"), user, pwd, center, i, stop), daemon=True)
        t.start()
        threads.append(t)
    print("Simulating... press Ctrl+C to stop.")
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop.set()
        for t in threads:
            t.join(timeout=5)


if __name__ == "__main__":
    main()
