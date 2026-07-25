import json
from flask import Flask, render_template, request
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
            # login_and_fetch now returns the structured dictionary defined in the brief
            data = login_and_fetch(hallticket, password)
            
            # Pass data as JSON string for Chart.js and dynamic rendering
            return render_template("dashboard.html", data_json=json.dumps(data))

        except Exception as e:
            return render_template("index.html", error=f"Login failed — {e}")

    return render_template("index.html", error=None)

if __name__ == "__main__":
    app.run(debug=True)
