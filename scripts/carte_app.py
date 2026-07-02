import hmac
from pathlib import Path
from flask import (Flask, Response, jsonify, render_template, request,
                   send_file, send_from_directory)
import json
from scripts.config import ROOT, SUIVI_PATH
from scripts.carte_data import CARTE_PATH, construire
from scripts import carte_crm
PORT = 5681
WEB_DIR = ROOT / "carte_web"
SECRETS_PATH = ROOT / "_secrets" / "remote_access.json"
app = Flask(
    __name__,
    template_folder=str(WEB_DIR / "templates"),
    static_folder=str(WEB_DIR / "static"),
)
def _auth_conf():
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        ba = data.get("basic_auth", {})
        if ba.get("enabled"):
            return ba.get("user", ""), ba.get("pass", "")
    except (OSError, ValueError):
        pass
    return None
@app.before_request
def _exiger_auth():
    conf = _auth_conf()
    if not conf:
        return None
    user, pwd = conf
    a = request.authorization
    ok = (a and hmac.compare_digest(a.username or "", user)
          and hmac.compare_digest(a.password or "", pwd))
    if not ok:
        return Response(
            "Authentification requise.", 401,
            {"WWW-Authenticate": 'Basic realm="Carte candidatures"'})
    return None
@app.route("/")
def index():
    return render_template("carte.html")
@app.route("/api/lieux")
def api_lieux():
    if not CARTE_PATH.exists():
        construire(verbose=False)
    return Response(CARTE_PATH.read_text(encoding="utf-8"),
                    mimetype="application/json")
@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    data = construire(verbose=False)
    return jsonify({"ok": True, "count": data["count"],
                    "count_sans_geo": data["count_sans_geo"],
                    "generated_at": data["generated_at"]})
@app.route("/api/update_status/<oid>", methods=["POST"])
def api_update_status(oid):
    action = (request.get_json(silent=True) or {}).get("action", "")
    res = carte_crm.marquer(oid, action)
    return jsonify(res), (200 if res.get("ok") else 400)
@app.route("/api/update_note/<oid>", methods=["POST"])
def api_update_note(oid):
    note = (request.get_json(silent=True) or {}).get("note", "")
    res = carte_crm.maj_note(oid, note)
    return jsonify(res), (200 if res.get("ok") else 400)
@app.route("/api/update_location/<oid>", methods=["POST"])
def api_update_location(oid):
    adresse = (request.get_json(silent=True) or {}).get("adresse", "")
    res = carte_crm.maj_localisation(oid, adresse)
    return jsonify(res), (200 if res.get("ok") else 400)
@app.route("/api/enrich/<oid>", methods=["POST"])
def api_enrich(oid):
    res = carte_crm.enrichir(oid)
    return jsonify(res), (200 if res.get("ok") else 400)
@app.route("/api/restore/<oid>", methods=["POST"])
def api_restore(oid):
    res = carte_crm.restaurer(oid)
    return jsonify(res), (200 if res.get("ok") else 400)
def _chemin_doc(oid: str, kind: str):
    suivi = json.loads(SUIVI_PATH.read_text(encoding="utf-8"))
    cand = next((c for c in suivi.get("candidatures", [])
                 if c.get("id") == oid), None)
    if not cand:
        return None
    champ = {"cv": "cv_pdf", "lm": "lettre_pdf", "lmtxt": "lettre_txt"}.get(kind)
    if not champ or not cand.get(champ):
        return None
    p = Path(cand[champ])
    try:
        p.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None
    return p if p.exists() else None
@app.route("/doc/<oid>/<kind>")
def doc(oid, kind):
    p = _chemin_doc(oid, kind)
    if not p:
        return Response("Document introuvable.", 404)
    return send_file(str(p))
@app.route("/static/<path:nom>")
def static_files(nom):
    return send_from_directory(str(WEB_DIR / "static"), nom)
if __name__ == "__main__":
    if not CARTE_PATH.exists():
        construire(verbose=False)
    print(f"Carte des candidatures sur http://127.0.0.1:{PORT}")
    print("Pour l'acces telephone via Tailscale Funnel :")
    print(f"  tailscale funnel --bg --https=443 http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, threaded=True)