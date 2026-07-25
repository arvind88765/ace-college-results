import json
from flask import Flask, render_template, request
from ace_client import fetch_all_semesters_single_session as login_and_fetch_async

app = Flask(__name__)

def transform_hallticket(raw: str) -> str:
    ht = raw.strip().upper()
    if not ht.endswith("P"):
        ht = ht + "P"
    return ht

# Flask 3.x supports async view functions directly (via asgiref) —
# no gevent/eventlet needed. The ~1-3s login scrape no longer ties
# up a whole sync worker; the process can keep handling other
# requests while awaiting network I/O here.
@app.route("/", methods=["GET", "POST"])
async def home():
    if request.method == "POST":
        raw_hallticket = request.form.get("hallticket", "").strip()
        user_password  = request.form.get("password", "").strip()

        if not raw_hallticket:
            return render_template("index.html", error="Please enter your hall ticket number.")

        hallticket = transform_hallticket(raw_hallticket)
        password = user_password if user_password else hallticket

        try:
            data = await login_and_fetch_async(hallticket, password)
            return render_template("dashboard.html", data_json=json.dumps(data))

        except Exception as e:
            return render_template("index.html", error=f"Login failed — {e}")

    return render_template("index.html", error=None)

if __name__ == "__main__":
    app.run(debug=True)
