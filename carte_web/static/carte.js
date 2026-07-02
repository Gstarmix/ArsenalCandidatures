"use strict";
const CAT_COLORS = {
  restauration: "#e74c3c",
  cafe: "#8e44ad",
  commerce: "#f39c12",
  hotel_nuit: "#16a085",
  services: "#2980b9",
  inventaire: "#d35400",
  industrie_interim: "#7f8c8d",
  autre: "#7f8c8d"
};
const STATUT_LABELS = {
  a_envoyer: "À envoyer",
  envoye: "Envoyé",
  relance: "Relancé",
  sans_reponse: "Sans réponse",
  entretien: "Entretien",
  refus: "Refus",
  accepte: "Accepté"
};
const state = {
  data: null,
  filters: {
    dates: new Set(),
    cats: new Set(),
    statuts: new Set(),
    text: ""
  },
  markers: {},
  me: null,
  meMarker: null,
  meSimulated: false,
  placeMode: false,
  listText: "",
  metro: [],
  layer: null
};
let map;
function el(id) {
  return document.getElementById(id);
}
function frDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || "");
  return m ? `${m[3]}/${m[2]}` : s || "?";
}
function statutLabel(s) {
  return STATUT_LABELS[s] || s || "—";
}
function esc(s) {
  return (s || "").replace(/[&<>"]/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;"
  })[c]);
}
function haversine(a, b) {
  const R = 6371000,
    rad = x => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat),
    dLon = rad(b.lon - a.lon);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
function distLabel(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
async function load() {
  setStatus("Chargement…");
  const r = await fetch("/api/lieux");
  state.data = await r.json();
  try {
    const rm = await fetch("/static/metro_rennes.json");
    state.metro = await rm.json();
    buildSimChips();
  } catch (e) {
    state.metro = [];
  }
  state.data.lieux.forEach(l => {
    state.filters.dates.add(l.date);
    state.filters.cats.add(l.categorie);
    state.filters.statuts.add(l.statut);
  });
  buildChips();
  render();
  const c = state.data.centre || {
    lat: 48.1093,
    lon: -1.68
  };
  map.setView([c.lat, c.lon], 14);
}
function setStatus(t) {
  el("status-text").textContent = t;
}
function uniqueSorted(arr, desc) {
  const u = [...new Set(arr)];
  u.sort();
  if (desc) u.reverse();
  return u;
}
function buildChips() {
  const L = state.data.lieux;
  const labels = state.data.cat_labels || {};
  el("f-dates").innerHTML = "";
  uniqueSorted(L.map(l => l.date), true).forEach(d => {
    el("f-dates").appendChild(makeChip(d, frDate(d), "dates"));
  });
  el("f-cats").innerHTML = "";
  uniqueSorted(L.map(l => l.categorie)).forEach(c => {
    const chip = makeChip(c, labels[c] || c, "cats");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = CAT_COLORS[c] || "#999";
    chip.prepend(dot);
    el("f-cats").appendChild(chip);
  });
  el("f-statuts").innerHTML = "";
  uniqueSorted(L.map(l => l.statut)).forEach(s => {
    el("f-statuts").appendChild(makeChip(s, statutLabel(s), "statuts"));
  });
}
function makeChip(value, label, kind) {
  const c = document.createElement("div");
  c.className = "chip on";
  c.dataset.kind = kind;
  c.dataset.value = value;
  c.append(document.createTextNode(label));
  c.addEventListener("click", () => {
    const set = state.filters[kind];
    if (set.has(value)) {
      set.delete(value);
      c.classList.remove("on");
    } else {
      set.add(value);
      c.classList.add("on");
    }
    render();
  });
  return c;
}
function passes(l) {
  const f = state.filters;
  if (!f.dates.has(l.date)) return false;
  if (!f.cats.has(l.categorie)) return false;
  if (!f.statuts.has(l.statut)) return false;
  if (f.text) {
    const blob = (l.entreprise + " " + l.poste + " " + l.adresse).toLowerCase();
    if (!blob.includes(f.text.toLowerCase())) return false;
  }
  return true;
}
function filtered() {
  return state.data.lieux.filter(passes);
}
function render() {
  if (!state.layer) state.layer = L.layerGroup().addTo(map);
  state.layer.clearLayers();
  state.markers = {};
  const list = filtered();
  list.forEach(l => {
    const m = L.circleMarker([l.lat, l.lon], {
      radius: 9,
      weight: 2,
      color: "#fff",
      fillColor: CAT_COLORS[l.categorie] || "#999",
      fillOpacity: 0.95
    });
    m.bindPopup(popupHtml(l), {
      maxWidth: 280
    });
    m.addTo(state.layer);
    state.markers[l.id] = m;
  });
  el("f-count").textContent = list.length;
  setStatus(`${list.length} lieu(x) affiché(s) · données du ${state.data.generated_at}`);
}
function popupHtml(l) {
  const labels = state.data.cat_labels || {};
  let docs = "";
  if (l.has_cv) docs += `<a class="doc" href="/doc/${l.id}/cv" target="_blank">CV</a>`;
  if (l.has_lm) docs += `<a class="doc" href="/doc/${l.id}/lm" target="_blank">Lettre</a>`;
  const gmap = `https://www.google.com/maps/dir/?api=1&destination=${l.lat},${l.lon}&travelmode=walking`;
  const tel = l.tel ? `<div class="pop-row">📞 <a href="tel:${l.tel.replace(/\s/g, "")}">${esc(l.tel)}</a></div>` : "";
  const horaires = l.horaires ? `<div class="pop-row">🕒 ${esc(l.horaires)}</div>` : "";
  const site = l.site ? `<div class="pop-row">🌐 <a href="${esc(l.site)}" target="_blank">${esc(l.site)}</a></div>` : "";
  return `<div class="pop">
    <div class="badge">${esc(labels[l.categorie] || l.categorie)} · ${statutLabel(l.statut)}</div>
    <div class="pop-name">${esc(l.entreprise)}</div>
    <div class="pop-poste">${esc(l.poste)}</div>
    <div class="pop-row">📍 ${esc(l.adresse)}</div>
    ${tel}${horaires}${site}
    <div class="pop-actions">
      <a class="go" href="${gmap}" target="_blank">🚶 Y aller</a>
      ${docs}
      <button class="enrich crm-enrich">🔎 Rechercher infos</button>
      <button class="websearch crm-websearch">🌐 Web</button>
    </div>
    <div class="pop-crm" data-id="${esc(l.id)}">
      <div class="crm-statuts">
        <button class="crm-depose">Déposé 🚀</button>
        <button class="crm-skip">Pas intéressé ❌</button>
      </div>
      <textarea class="crm-note" rows="2" placeholder="Note (visite, contact, horaires...)">${esc(l.note)}</textarea>
      <button class="crm-note-save">📝 Enregistrer la note</button>
      <input class="crm-adresse" type="text" placeholder="Corriger l'adresse (rue, n°, Rennes)">
      <button class="crm-adresse-save">📍 Valider l'adresse</button>
      <div class="crm-msg"></div>
    </div>
  </div>`;
}
async function crmPost(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body || {})
  });
  return r.json();
}
function removeMarker(id) {
  const m = state.markers[id];
  if (m) {
    state.layer.removeLayer(m);
    delete state.markers[id];
  }
  state.data.lieux = state.data.lieux.filter(l => l.id !== id);
  el("f-count").textContent = filtered().length;
}
async function crmStatus(id, action) {
  try {
    const res = await crmPost(`/api/update_status/${encodeURIComponent(id)}`, {
      action
    });
    if (res.ok) {
      map.closePopup();
      removeMarker(id);
      setStatus(action === "depose" ? "Candidature marquée déposée." : "Marquée pas intéressée.");
    } else {
      alert("Échec : " + (res.erreur || "?"));
    }
  } catch (e) {
    alert("Erreur réseau : " + e);
  }
}
async function crmNote(id, note, msg) {
  msg.textContent = "Enregistrement…";
  const res = await crmPost(`/api/update_note/${encodeURIComponent(id)}`, {
    note
  });
  msg.textContent = res.ok ? "Note enregistrée ✓" : "Échec : " + (res.erreur || "?");
  const l = state.data.lieux.find(x => x.id === id);
  if (l) l.note = note;
}
async function crmAdresse(id, adresse, msg) {
  if (!adresse.trim()) {
    msg.textContent = "Saisis une adresse d'abord.";
    return;
  }
  msg.textContent = "Recherche de l'adresse sur OpenStreetMap…";
  const res = await crmPost(`/api/update_location/${encodeURIComponent(id)}`, {
    adresse
  });
  if (!res.ok) {
    msg.textContent = "Échec : " + (res.erreur || "?");
    return;
  }
  const l = state.data.lieux.find(x => x.id === id);
  if (l) {
    l.lat = res.lat;
    l.lon = res.lon;
    l.adresse = adresse;
  }
  const m = state.markers[id];
  if (m) m.setLatLng([res.lat, res.lon]);
  map.setView([res.lat, res.lon], 16);
  msg.textContent = "Adresse mise à jour ✓";
}
async function crmEnrich(id, msg) {
  msg.textContent = "Recherche d'infos sur OpenStreetMap…";
  const res = await crmPost(`/api/enrich/${encodeURIComponent(id)}`, {});
  if (!res.ok) {
    msg.textContent = "Échec : " + (res.erreur || "?");
    return;
  }
  if (res.trouve) {
    const l = state.data.lieux.find(x => x.id === id);
    if (l) {
      l.site = res.site;
      l.horaires = res.horaires;
    }
    msg.textContent = "Infos trouvées ✓";
    const m = state.markers[id];
    if (m && l) {
      m.setPopupContent(popupHtml(l));
      const root = m.getPopup().getElement();
      if (root) wireCrm(root);
    }
  } else {
    msg.textContent = "Rien sur OpenStreetMap. Essaie le bouton 🌐 Web (marqué « à enrichir »).";
  }
}
function webSearch(id) {
  const l = state.data.lieux.find(x => x.id === id);
  if (!l) return;
  const mots = [l.entreprise, l.adresse || "Rennes", "horaires recrutement"].filter(Boolean).join(" ");
  window.open("https://www.google.com/search?q=" + encodeURIComponent(mots), "_blank");
}
function wireCrm(root) {
  const crm = root.querySelector(".pop-crm");
  if (!crm) return;
  const id = crm.dataset.id;
  const msg = crm.querySelector(".crm-msg");
  const enrich = root.querySelector(".crm-enrich");
  if (enrich) enrich.onclick = () => crmEnrich(id, msg);
  const web = root.querySelector(".crm-websearch");
  if (web) web.onclick = () => webSearch(id);
  crm.querySelector(".crm-depose").onclick = () => crmStatus(id, "depose");
  crm.querySelector(".crm-skip").onclick = () => crmStatus(id, "pas_interesse");
  crm.querySelector(".crm-note-save").onclick = () => crmNote(id, crm.querySelector(".crm-note").value, msg);
  crm.querySelector(".crm-adresse-save").onclick = () => crmAdresse(id, crm.querySelector(".crm-adresse").value, msg);
}
function setMeMarker(simulated) {
  if (state.meMarker) map.removeLayer(state.meMarker);
  const cls = simulated ? "me-dot sim" : "me-dot";
  state.meMarker = L.marker([state.me.lat, state.me.lon], {
    draggable: simulated,
    icon: L.divIcon({
      className: "",
      html: `<div class="${cls}"></div>`,
      iconSize: [16, 16]
    })
  }).addTo(map);
  if (simulated) {
    state.meMarker.on("dragend", e => {
      const ll = e.target.getLatLng();
      state.me = {
        lat: ll.lat,
        lon: ll.lng
      };
      setStatus("Position simulée déplacée. Utilise « Près de moi ».");
    });
  }
}
function nearestFrom() {
  const list = filtered().map(l => ({
    l,
    d: haversine(state.me, l)
  })).sort((a, b) => a.d - b.d);
  if (!list.length) {
    alert("Aucun lieu avec les filtres actuels.");
    return;
  }
  const best = list[0];
  map.setView([best.l.lat, best.l.lon], 16);
  if (state.markers[best.l.id]) state.markers[best.l.id].openPopup();
  const src = state.meSimulated ? " (depuis ta position simulée)" : "";
  setStatus(`Plus proche : ${best.l.entreprise} · ${distLabel(best.d)}${src}. Ouvre le popup, puis « Y aller » pour l'itinéraire.`);
}
function nearMe() {
  if (state.meSimulated && state.me) {
    nearestFrom();
    return;
  }
  if (!navigator.geolocation) {
    alert("Géolocalisation indisponible.");
    return;
  }
  setStatus("Localisation en cours…");
  navigator.geolocation.getCurrentPosition(pos => {
    state.me = {
      lat: pos.coords.latitude,
      lon: pos.coords.longitude
    };
    setMeMarker(false);
    nearestFrom();
  }, err => {
    setStatus("Localisation refusée.");
    alert("Impossible de te localiser : " + err.message);
  }, {
    enableHighAccuracy: true,
    timeout: 10000
  });
}
function buildSimChips() {
  ["A", "B"].forEach(ligne => {
    const box = el("sim-ligne" + ligne);
    box.innerHTML = "";
    state.metro.filter(s => s.lignes.includes(ligne)).sort((a, b) => a.nom.localeCompare(b.nom)).forEach(s => {
      const c = document.createElement("div");
      c.className = "chip";
      c.textContent = s.nom;
      c.addEventListener("click", () => choisirStation(s));
      box.appendChild(c);
    });
  });
}
function updateSimUI() {
  el("btn-sim").classList.toggle("on", state.meSimulated);
  el("sim-clear").classList.toggle("hidden", !state.meSimulated);
}
function poserSimulee(lat, lon, libelle) {
  state.me = {
    lat,
    lon
  };
  state.meSimulated = true;
  state.placeMode = false;
  setMeMarker(true);
  map.setView([lat, lon], 15);
  updateSimUI();
  setStatus(`Position simulée : ${libelle}. Utilise « Près de moi ».`);
}
function choisirStation(s) {
  closeSheet("simpanel");
  poserSimulee(s.lat, s.lon, "métro " + s.nom);
}
function armerClicCarte() {
  closeSheet("simpanel");
  state.placeMode = true;
  setStatus("Touche la carte pour poser ta position simulée.");
}
function clearSim() {
  if (state.meMarker) {
    map.removeLayer(state.meMarker);
    state.meMarker = null;
  }
  state.me = null;
  state.meSimulated = false;
  state.placeMode = false;
  closeSheet("simpanel");
  updateSimUI();
  setStatus("Position simulée retirée (retour au GPS réel).");
}
function onMapClick(e) {
  if (!state.placeMode) return;
  poserSimulee(e.latlng.lat, e.latlng.lng, "point sur la carte");
}
function renderList() {
  const box = el("list-items");
  let list = filtered();
  const q = state.listText.trim().toLowerCase();
  if (q) {
    list = list.filter(l => (l.entreprise + " " + l.poste + " " + l.adresse + " " + (l.note || "")).toLowerCase().includes(q));
  }
  if (state.me) {
    list = list.map(l => ({
      l,
      d: haversine(state.me, l)
    })).sort((a, b) => a.d - b.d);
  } else {
    list = list.map(l => ({
      l,
      d: null
    })).sort((a, b) => a.l.entreprise.localeCompare(b.l.entreprise));
  }
  el("list-count").textContent = `(${list.length})`;
  box.innerHTML = "";
  list.forEach(({
    l,
    d
  }) => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `<div class="it-top"><span class="it-name">${esc(l.entreprise)}</span>
      ${d != null ? `<span class="it-dist">${distLabel(d)}</span>` : ""}</div>
      <div class="it-sub">${esc(l.poste)}</div>
      <div class="it-sub">📍 ${esc(l.adresse)}</div>`;
    div.addEventListener("click", () => {
      closeSheet("listpanel");
      map.setView([l.lat, l.lon], 16);
      state.markers[l.id] && state.markers[l.id].openPopup();
    });
    box.appendChild(div);
  });
  const sg = el("sansgeo-items");
  sg.innerHTML = "";
  let sansgeo = state.data.sans_geo || [];
  if (q) {
    sansgeo = sansgeo.filter(l => ((l.entreprise || "") + " " + (l.poste || "") + " " + (l.adresse || "")).toLowerCase().includes(q));
  }
  el("sansgeo-block").style.display = sansgeo.length ? "" : "none";
  sansgeo.forEach(l => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `<div class="it-name">${esc(l.entreprise || "(sans nom)")}</div>
      <div class="it-sub">${esc(l.poste)}</div>
      <div class="it-sub">${esc(l.adresse || "adresse imprécise")}</div>`;
    sg.appendChild(div);
  });
  renderTraites(q);
}
function renderTraites(q) {
  const box = el("traites-items");
  box.innerHTML = "";
  let traites = state.data.traites || [];
  if (q) {
    traites = traites.filter(t => ((t.entreprise || "") + " " + (t.poste || "") + " " + (t.adresse || "") + " " + (t.note || "")).toLowerCase().includes(q));
  }
  el("traites-count").textContent = `(${traites.length})`;
  el("traites-block").style.display = traites.length ? "" : "none";
  const groupes = [{
    key: "envoye",
    label: "Déposées 🚀"
  }, {
    key: "pas_interesse",
    label: "Pas intéressées ❌"
  }];
  groupes.forEach(g => {
    const items = traites.filter(t => t.statut === g.key);
    if (!items.length) return;
    const h = document.createElement("div");
    h.className = "group-title sub";
    h.textContent = `${g.label} (${items.length})`;
    box.appendChild(h);
    items.forEach(t => {
      const div = document.createElement("div");
      div.className = "item";
      let docs = "";
      if (t.has_cv) docs += `<a class="doc" href="/doc/${t.id}/cv" target="_blank">CV</a>`;
      if (t.has_lm) docs += `<a class="doc" href="/doc/${t.id}/lm" target="_blank">Lettre</a>`;
      const quand = t.date_envoi ? ` · déposé le ${frDate(t.date_envoi)}` : "";
      div.innerHTML = `<div class="it-name">${esc(t.entreprise || "(sans nom)")}</div>
        <div class="it-sub">${esc(t.poste)}</div>
        <div class="it-sub">📍 ${esc(t.adresse || "adresse imprécise")}${quand}</div>
        ${t.note ? `<div class="it-sub">📝 ${esc(t.note)}</div>` : ""}
        <div class="it-actions">${docs}<button class="restore">↩︎ Remettre sur la carte</button></div>`;
      div.querySelector(".restore").addEventListener("click", () => restoreCand(t.id));
      box.appendChild(div);
    });
  });
}
async function restoreCand(id) {
  setStatus("Remise sur la carte…");
  const res = await crmPost(`/api/restore/${encodeURIComponent(id)}`, {});
  if (!res.ok) {
    alert("Échec : " + (res.erreur || "?"));
    return;
  }
  const r = await fetch("/api/lieux");
  state.data = await r.json();
  state.data.lieux.forEach(l => {
    state.filters.dates.add(l.date);
    state.filters.cats.add(l.categorie);
    state.filters.statuts.add(l.statut);
  });
  buildChips();
  render();
  renderList();
  setStatus("Remis sur la carte.");
}
function openSheet(id) {
  ["filters", "listpanel", "simpanel"].forEach(s => el(s).classList.add("hidden"));
  el(id).classList.remove("hidden");
  if (id === "listpanel") renderList();
  if (id === "simpanel") {
    buildSimChips();
    updateSimUI();
  }
}
function closeSheet(id) {
  el(id).classList.add("hidden");
}
async function refresh() {
  setStatus("Mise à jour (géocodage)…");
  el("btn-refresh").disabled = true;
  try {
    await fetch("/api/refresh", {
      method: "POST"
    });
    const r = await fetch("/api/lieux");
    state.data = await r.json();
    state.data.lieux.forEach(l => {
      state.filters.dates.add(l.date);
      state.filters.cats.add(l.categorie);
      state.filters.statuts.add(l.statut);
    });
    buildChips();
    render();
  } catch (e) {
    alert("Échec de la mise à jour : " + e);
  } finally {
    el("btn-refresh").disabled = false;
  }
}
function init() {
  map = L.map("map", {
    zoomControl: true
  }).setView([48.1093, -1.68], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap"
  }).addTo(map);
  map.on("popupopen", e => wireCrm(e.popup.getElement()));
  map.on("click", onMapClick);
  el("btn-near").addEventListener("click", nearMe);
  el("btn-sim").addEventListener("click", () => openSheet("simpanel"));
  el("sim-map").addEventListener("click", armerClicCarte);
  el("sim-clear").addEventListener("click", clearSim);
  el("btn-filters").addEventListener("click", () => openSheet("filters"));
  el("btn-list").addEventListener("click", () => openSheet("listpanel"));
  el("l-text").addEventListener("input", e => {
    state.listText = e.target.value;
    renderList();
  });
  el("btn-refresh").addEventListener("click", refresh);
  document.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => closeSheet(b.dataset.close)));
  el("f-apply").addEventListener("click", () => closeSheet("filters"));
  el("f-text").addEventListener("input", e => {
    state.filters.text = e.target.value;
    render();
  });
  el("f-reset").addEventListener("click", () => {
    state.filters.text = "";
    el("f-text").value = "";
    state.data.lieux.forEach(l => {
      state.filters.dates.add(l.date);
      state.filters.cats.add(l.categorie);
      state.filters.statuts.add(l.statut);
    });
    document.querySelectorAll(".chip").forEach(c => c.classList.add("on"));
    render();
  });
  load().catch(e => setStatus("Erreur de chargement : " + e));
}
document.addEventListener("DOMContentLoaded", init);