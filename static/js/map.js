/* Shared map helpers (Leaflet + OpenStreetMap + Nominatim). No API keys needed.
 *
 * Nominatim usage policy: max 1 request/second, no autocomplete-as-you-type.
 * We only call it on an explicit Search click/Enter or a map click.
 */
const NOMINATIM = "https://nominatim.openstreetmap.org";

function baseMap(id, center, zoom) {
  const map = L.map(id).setView(center || window.MAP_CENTER, zoom || window.MAP_ZOOM);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  return map;
}

function dot(color) {
  return L.divIcon({
    className: "",
    html: `<div style="width:16px;height:16px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
    iconSize: [16, 16], iconAnchor: [8, 8],
  });
}

const COLORS = { site: "#4f46e5", home: "#f59e0b", vehicle: "#059669" };

/* Read-only map with labelled points: [{lat, lng, label, kind}] */
function showPoints(id, points) {
  const map = baseMap(id);
  const layer = points.map(p =>
    L.marker([p.lat, p.lng], { icon: dot(COLORS[p.kind] || "#334155") }).bindTooltip(p.label).addTo(map));
  if (layer.length) map.fitBounds(L.featureGroup(layer).getBounds().pad(0.2), { maxZoom: 15 });
  return map;
}

/* Location picker bound to form inputs {lat, lng, addr} */
function MapPicker(id, inputs) {
  const has = inputs.lat.value && inputs.lng.value;
  const start = has ? [+inputs.lat.value, +inputs.lng.value] : null;
  const map = baseMap(id, start, start ? 16 : null);
  let marker = null;

  async function reverse(lat, lng) {
    if (!inputs.addr) return;
    try {
      const r = await fetch(`${NOMINATIM}/reverse?format=jsonv2&lat=${lat}&lon=${lng}`);
      const j = await r.json();
      if (j.display_name) inputs.addr.value = j.display_name;
    } catch (e) { /* offline or rate-limited - user can type the address */ }
  }

  function setPoint(lat, lng, opts = {}) {
    lat = +(+lat).toFixed(6); lng = +(+lng).toFixed(6);
    inputs.lat.value = lat; inputs.lng.value = lng;
    if (!marker) {
      marker = L.marker([lat, lng], { draggable: true }).addTo(map);
      marker.on("dragend", e => { const p = e.target.getLatLng(); setPoint(p.lat, p.lng); });
    } else marker.setLatLng([lat, lng]);
    if (opts.pan) map.setView([lat, lng], Math.max(map.getZoom(), 16));
    if (opts.addr !== undefined) { if (inputs.addr) inputs.addr.value = opts.addr; }
    else reverse(lat, lng);
  }

  if (start) setPoint(start[0], start[1], { addr: inputs.addr ? inputs.addr.value : "" });
  map.on("click", e => setPoint(e.latlng.lat, e.latlng.lng));

  // Typing coordinates by hand moves the pin
  [inputs.lat, inputs.lng].forEach(el => el.addEventListener("change", () => {
    if (inputs.lat.value && inputs.lng.value) setPoint(inputs.lat.value, inputs.lng.value, { pan: true });
  }));

  // Search
  const q = document.getElementById("map-q"), list = document.getElementById("map-results");
  async function search() {
    if (!q.value.trim()) return;
    list.innerHTML = '<li class="px-3 py-2 text-slate-400">Searching…</li>';
    list.classList.remove("hidden");
    try {
      const r = await fetch(`${NOMINATIM}/search?format=jsonv2&limit=6&q=${encodeURIComponent(q.value)}`);
      const res = await r.json();
      list.innerHTML = res.length ? "" : '<li class="px-3 py-2 text-slate-400">No results</li>';
      res.forEach(x => {
        const li = document.createElement("li");
        li.className = "px-3 py-2 cursor-pointer hover:bg-indigo-50";
        li.textContent = x.display_name;
        li.onclick = () => { setPoint(x.lat, x.lon, { pan: true, addr: x.display_name }); list.classList.add("hidden"); };
        list.appendChild(li);
      });
    } catch (e) {
      list.innerHTML = '<li class="px-3 py-2 text-red-500">Search failed - check internet connection</li>';
    }
  }
  document.getElementById("map-search").onclick = search;
  q.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); search(); } });

  // Current location
  document.getElementById("map-me").onclick = () => {
    if (!navigator.geolocation) return alert("Location not supported on this device");
    navigator.geolocation.getCurrentPosition(
      p => setPoint(p.coords.latitude, p.coords.longitude, { pan: true }),
      () => alert("Couldn't get your location (permission denied or unavailable)"),
      { enableHighAccuracy: true, timeout: 10000 });
  };
  return map;
}
