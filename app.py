import json
import asyncio
from flask import Flask, render_template, request, Response
from ace_client import fetch_all_semesters_single_session, list_semesters, _login, _make_client

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


# TEMPORARY DEBUG ROUTE — remove once the semester-button regex is fixed.
# Dumps the raw HTML of the post-login landing page instead of trying to
# parse it, so we can see the real markup and fix _SEM_BTN_RE correctly.
# Usage: POST hallticket/password to /debug-raw the same way you would to /.
@app.route("/debug-raw", methods=["GET", "POST"])
def debug_raw():
    if request.method == "GET":
        return '''
        <form method="POST">
          Hall ticket: <input name="hallticket"><br>
          Password (leave blank to reuse hallticket): <input name="password" type="password"><br>
          <button type="submit">Fetch raw HTML</button>
        </form>
        '''

    raw_hallticket = request.form.get("hallticket", "").strip()
    user_password = request.form.get("password", "").strip()
    if not raw_hallticket:
        return "Missing hallticket", 400

    hallticket = transform_hallticket(raw_hallticket)
    password = user_password if user_password else hallticket

    async def _fetch():
        async with _make_client() as client:
            return await _login(client, hallticket, password)

    try:
        html = asyncio.run(_fetch())
    except Exception as e:
        return f"Login/fetch failed: {e}", 500

    # Return as plain text so the browser shows raw HTML instead of
    # rendering it — makes Ctrl+F for "btn" or "cpStud" easy.
    return Response(html, mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True)
