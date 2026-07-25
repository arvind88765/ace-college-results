import json
import asyncio
from flask import Flask, render_template, request
from ace_client import fetch_all_semesters_single_session

app = Flask(__name__)

def transform_hallticket(raw: str) -> str:
    ht = raw.strip().upper()
    if not ht.endswith("P"):
        ht = ht + "P"
    return ht

# Plain sync view — deliberately NOT `async def`. Async Flask views need
# the 'asgiref' package (via the Flask[async] extra), which failed to
# install correctly in the Vercel build (confirmed via the runtime
# traceback: "RuntimeError: Install Flask with the 'async' extra").
# asyncio.run() here gets the same httpx-async client working without
# depending on Flask's async-view machinery at all.
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
            data = asyncio.run(fetch_all_semesters_single_session(hallticket, password))
            return render_template("dashboard.html", data_json=json.dumps(data))

        except Exception as e:
            return render_template("index.html", error=f"Login failed — {e}")

    return render_template("index.html", error=None)

if __name__ == "__main__":
    app.run(debug=True)
