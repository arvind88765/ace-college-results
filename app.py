import json
from flask import Flask, render_template, request, jsonify
from ace_client import login_and_fetch

app = Flask(__name__)

def transform_hallticket(raw: str) -> str:
    ht = raw.strip().upper()
    if not ht.endswith("P"):
        ht = ht + "P"
    return ht

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        raw_hallticket = request.form.get("hallticket", "").strip()
        user_password  = request.form.get("password", "").strip()

        if not raw_hallticket:
            return render_template("index.html", error="Please enter your hall ticket number.")

        hallticket = transform_hallticket(raw_hallticket)
        password = user_password if user_password else hallticket

        try:
            data = login_and_fetch(hallticket, password)
            return render_template("dashboard.html", data_json=json.dumps(data))

        except Exception as e:
            return render_template("index.html", error=f"Login failed — {e}")

    return render_template("index.html", error=None)

@app.route("/api/results", methods=["POST"])
def api_results():
    """Fast JSON API - POST hallticket + password, get results instantly"""
    try:
        raw_hallticket = request.json.get("hallticket", "").strip()
        user_password = request.json.get("password", "").strip()
        
        if not raw_hallticket:
            return jsonify({"error": "hallticket required"}), 400
        
        hallticket = transform_hallticket(raw_hallticket)
        password = user_password if user_password else hallticket
        
        data = login_and_fetch(hallticket, password)
        
        return jsonify({
            "success": True,
            "data": data
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

@app.route("/results/<hallticket>", methods=["GET", "POST"])
def quick_results(hallticket):
    """FASTEST: Direct results - hallticket in URL, password optional (defaults to hallticket)"""
    try:
        password = request.args.get("password") or request.json.get("password") if request.is_json else None
        
        ht = transform_hallticket(hallticket)
        pwd = password if password else ht
        
        data = login_and_fetch(ht, pwd)
        
        # Return as JSON by default
        return jsonify({
            "success": True,
            "student": data.get("student"),
            "cgpa": data.get("cgpa"),
            "credits": data.get("credits"),
            "backlogs": data.get("backlogs"),
            "semesters": data.get("semesters")
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=False, threaded=True)
