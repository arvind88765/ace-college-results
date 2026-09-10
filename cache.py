"""
Tiny Redis-backed result cache using the Upstash REST API.

Why this approach: Vercel Python functions are stateless/serverless - nothing
in-process survives between invocations, so an in-memory dict cache is useless
in production. Upstash's REST API works over plain HTTPS (no redis-py, no
compiled deps to break the build) and is what Vercel's own "KV" storage
add-on provisions under the hood.

If no store is configured, every function here is a silent no-op - the app
keeps working exactly as before, just without caching. Connect a store via
the Vercel dashboard (Storage tab -> create a KV / Upstash Redis database ->
Connect to Project) and the required env vars are added automatically.
"""
import os
import json
import requests

TTL_SECONDS = 6 * 60 * 60  # 6 hours - long enough to skip re-scraping on repeat
                            # visits same day, short enough to pick up new marks

_URL = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")

ENABLED = bool(_URL and _TOKEN)


def _command(*parts):
    """Send one Redis command via Upstash's REST pipeline endpoint."""
    if not ENABLED:
        return None
    try:
        r = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=list(parts),
            timeout=(2, 3),
        )
        r.raise_for_status()
        return r.json().get("result")
    except Exception as e:
        print(f"⚠️ cache backend error: {e}")
        return None


def _key(hallticket):
    return f"ace_results:{hallticket.upper()}"


def get_cached_result(hallticket):
    """Returns the cached parsed-results dict, or None on miss/disabled/error."""
    raw = _command("GET", _key(hallticket))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def set_cached_result(hallticket, data):
    """Stores the parsed-results dict with a TTL. Best-effort - never raises."""
    try:
        _command("SETEX", _key(hallticket), TTL_SECONDS, json.dumps(data))
    except Exception as e:
        print(f"⚠️ cache write failed: {e}")
