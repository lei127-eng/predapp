from flask import Flask, jsonify, render_template
import urllib.request
import json
import numpy as np

app = Flask(__name__)


def fetch_api(url):
    """Appel HTTP simple, retourne le JSON ou None."""

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "F1App/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERREUR API] {url}\n  → {e}")
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/next-race")
def next_race():

    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/next.json")
    if not data:
        return jsonify({"error": "Impossible de récupérer les données"}), 500

    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        return jsonify({"error": "Aucune course à venir cette saison"}), 404

    r = races[0]
    return jsonify({
        "nom":     r.get("raceName", "Inconnu"),
        "circuit": r["Circuit"].get("circuitName", "Inconnu"),
        "pays":    r["Circuit"]["Location"].get("country", ""),
        "ville":   r["Circuit"]["Location"].get("locality", ""),
        "date":    r.get("date", ""),
        "heure":   r.get("time", ""),
        "round":   r.get("round", ""),
        "saison":  r.get("season", "2025"),
    })



@app.route("/api/circuit-info")
def circuit_info():
    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/next.json")
    if not data:
        return jsonify({"error": "Erreur API"}), 500

    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        return jsonify({"error": "Pas de course à venir"}), 404

    c = races[0]["Circuit"]
    return jsonify({
        "nom":   c.get("circuitName", ""),
        "pays":  c["Location"].get("country", ""),
        "ville": c["Location"].get("locality", ""),
        "lat":   c["Location"].get("lat", ""),
        "lng":   c["Location"].get("long", ""),
        "url":   c.get("url", ""),
    })



@app.route("/api/last-race")
def last_race():
    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/last/results.json")
    if not data:
        return jsonify({"error": "Erreur API"}), 500

    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        return jsonify({"error": "Pas encore de résultats cette saison"}), 404

    r = races[0]
    podium = []
    for res in r.get("Results", [])[:3]:
        podium.append({
            "position": res.get("position", ""),
            "pilote":   res["Driver"].get("familyName", ""),
            "prenom":   res["Driver"].get("givenName", ""),
            "equipe":   res["Constructor"].get("name", ""),
        })
    return jsonify({
        "nom":     r.get("raceName", ""),
        "date":    r.get("date", ""),
        "circuit": r["Circuit"].get("circuitName", ""),
        "pays":    r["Circuit"]["Location"].get("country", ""),
        "podium":  podium,
    })



@app.route("/api/results")
def results():
    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/last/results.json")
    if not data:
        return jsonify({"error": "Erreur API"}), 500

    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        return jsonify({"error": "Pas de résultats"}), 404

    r = races[0]
    resultats = []
    for res in r.get("Results", []):
        resultats.append({
            "position": res.get("position", ""),
            "pilote":   res["Driver"].get("givenName", "") + " " + res["Driver"].get("familyName", ""),
            "equipe":   res["Constructor"].get("name", ""),
            "points":   res.get("points", "0"),
            "statut":   res.get("status", ""),
            "laps":     res.get("laps", ""),
            "grille":   res.get("grid", ""),
        })
    return jsonify({
        "course":    r.get("raceName", ""),
        "date":      r.get("date", ""),
        "resultats": resultats,
    })



@app.route("/api/standings")
def standings():
    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/driverstandings.json")
    if not data:
        return jsonify({"error": "Erreur API"}), 500

    listes = data["MRData"]["StandingsTable"]["StandingsLists"]
    if not listes:
        return jsonify({"error": "Pas de classement disponible"}), 404

    classement = []
    for s in listes[0]["DriverStandings"]:
        classement.append({
            "position":  s.get("position", ""),
            "pilote":    s["Driver"].get("givenName", "") + " " + s["Driver"].get("familyName", ""),
            "equipe":    s["Constructors"][0].get("name", "") if s.get("Constructors") else "",
            "points":    s.get("points", "0"),
            "victoires": s.get("wins", "0"),
            "code":      s["Driver"].get("code", ""),
        })
    return jsonify(classement)



@app.route("/api/constructors")
def constructors():
    data = fetch_api("https://api.jolpi.ca/ergast/f1/current/constructorstandings.json")
    if not data:
        return jsonify({"error": "Erreur API"}), 500

    listes = data["MRData"]["StandingsTable"]["StandingsLists"]
    if not listes:
        return jsonify({"error": "Pas de données"}), 404

    classement = []
    for s in listes[0]["ConstructorStandings"]:
        classement.append({
            "position":    s.get("position", ""),
            "equipe":      s["Constructor"].get("name", ""),
            "nationalite": s["Constructor"].get("nationality", ""),
            "points":      s.get("points", "0"),
            "victoires":   s.get("wins", "0"),
        })
    return jsonify(classement)



@app.route("/api/prediction")
def prediction():
    data_standings = fetch_api("https://api.jolpi.ca/ergast/f1/current/driverstandings.json")
    data_results   = fetch_api("https://api.jolpi.ca/ergast/f1/current/results.json?limit=200")

    if not data_standings:
        return jsonify({"error": "Impossible de charger le classement"}), 500

    listes = data_standings["MRData"]["StandingsTable"]["StandingsLists"]
    if not listes:
        return jsonify({"error": "Classement vide"}), 404

    # Positions récentes (5 dernières courses) par pilote
    recent_positions = {}
    if data_results:
        races_data = data_results["MRData"]["RaceTable"]["Races"]
        for race in races_data[-5:]:
            for res in race.get("Results", []):
                nom = res["Driver"].get("familyName", "")
                try:
                    pos = int(res.get("position", 20))
                except ValueError:
                    pos = 20
                recent_positions.setdefault(nom, []).append(pos)

    predictions = []
    for s in listes[0]["DriverStandings"][:10]:
        nom          = s["Driver"].get("familyName", "")
        prenom       = s["Driver"].get("givenName", "")
        equipe       = s["Constructors"][0].get("name", "") if s.get("Constructors") else ""
        points_total = float(s.get("points", 0))
        victoires    = int(s.get("wins", 0))

        positions    = recent_positions.get(nom, [10, 10, 10])
        positions_np = np.array(positions)

        score_points    = points_total / 600
        score_victoires = victoires * 0.04
        score_forme     = (20 - float(np.mean(positions_np))) / 20

        score_final = (score_points * 0.50) + (score_forme * 0.35) + (score_victoires * 0.15)
        score_final = max(0.0, round(score_final * 100, 2))

        predictions.append({
            "pilote":        prenom + " " + nom,
            "equipe":        equipe,
            "points_saison": points_total,
            "victoires":     victoires,
            "score":         score_final,
            "forme":         round(float(np.mean(positions_np)), 1),
            "code":          s["Driver"].get("code", nom[:3].upper()),
        })

    predictions.sort(key=lambda x: x["score"], reverse=True)

    scores = np.array([p["score"] for p in predictions])
    total  = scores.sum()
    probas = (scores / total * 100) if total > 0 else np.ones(len(scores)) * 10
    probas = np.round(probas, 1)

    for i, p in enumerate(predictions):
        p["probabilite"] = float(probas[i])

    return jsonify(predictions)

if __name__ == "__main__":
    import os
    
    # Vérifie si on est sur Render (la variable PORT existe)
    if os.environ.get("PORT"):
        # Mode production (Render)
        port = int(os.environ.get("PORT", 10000))
        print(f"🏎️  F1 App — démarrée sur le port {port} (production)")
        app.run(host="0.0.0.0", port=port)
    else:
        # Mode développement local
        print("🏎️  F1 App — http://localhost:5000")
        app.run(debug=True, host="127.0.0.1", port=5000)
