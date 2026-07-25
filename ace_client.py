"""
Rewritten against the ACTUAL navigation chain captured in a real HAR
(aceexam_in.har), not guesses. Key corrections vs. the original
ace_client.py:

  - There is an extra required hop through StudLoginDashboard.aspx
    (postback target ctl00$cpStud$lnkStudentMain) before MainStud.aspx
    will accept the "Overall Marks" postback.
  - The final results page is NOT a single "overallMarks.aspx" page.
    It's OverallMarksSemwiseMarks.aspx, which lists one button per
    semester (ctl00$cpStud$btn1, btn2, ... btnN) and EACH semester's
    detail requires its own separate POST back to that same page.
  - Each of those per-semester POSTs costs ~1.8-2.5s server-side in
    the captured HAR, regardless of response size (30-70KB) - this is
    backend DB/render time on their IIS server, not something a faster
    HTTP client can fix.
  - VIEWSTATE changes on every response and each semester click needs
    the immediately preceding response's VIEWSTATE - confirmed by
    comparing VIEWSTATE hashes across consecutive semester clicks in
    the HAR. So semester fetches are NOT parallelizable within one
    login session.

The one real lever left: run multiple independent login sessions
concurrently (one per semester needed) with asyncio.gather, trading
extra login overhead for wall-clock parallelism. This is UNTESTED
against the live site - I have no network access to aceexam.in to
confirm it tolerates concurrent logins on the same account. Test
carefully before relying on it.
"""

import re
import asyncio
import httpx
from parser import parse_results

BASE = "https://aceexam.in"
LOGIN_URL = f"{BASE}/Login.aspx"
DASHBOARD_URL = f"{BASE}/StudentLogin/StudLoginDashboard.aspx"
MAIN_URL = f"{BASE}/StudentLogin/MainStud.aspx"
SEMWISE_URL = f"{BASE}/StudentLogin/Student/OverallMarksSemwiseMarks.aspx"

HEADERS = {"User-Agent": "Mozilla/5.0"}

_VIEWSTATE_RE = re.compile(r'id="__VIEWSTATE"[^>]*value="([^"]*)"')
_EVENTVAL_RE = re.compile(r'id="__EVENTVALIDATION"[^>]*value="([^"]*)"')
_VIEWSTATEGEN_RE = re.compile(r'id="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"')
# Semester buttons look like: name="ctl00$cpStud$btn6" ... value="III B.TECH II SEM"
_SEM_BTN_RE = re.compile(
    r'name="(ctl00\$cpStud\$btn\w+)"[^>]*value="([^"]*)"'
)


def _hidden_fields(html: str) -> dict:
    vs = _VIEWSTATE_RE.search(html)
    ev = _EVENTVAL_RE.search(html)
    vg = _VIEWSTATEGEN_RE.search(html)
    return {
        "__VIEWSTATE": vs.group(1) if vs else "",
        "__EVENTVALIDATION": ev.group(1) if ev else "",
        "__VIEWSTATEGENERATOR": vg.group(1) if vg else "",
    }


def _find_semester_buttons(html: str):
    """Returns [(field_name, semester_label), ...] e.g.
    [("ctl00$cpStud$btn6", "III B.TECH II SEM"), ...]
    NOTE: derived from the field-name pattern seen in the HAR's
    REQUEST bodies, not from an actual saved response body (the HAR
    didn't retain full response text for these pages). Verify this
    matches the real button markup before relying on it - if it
    doesn't match, list_semesters() returns an empty list instead of
    silently guessing wrong.
    """
    return _SEM_BTN_RE.findall(html)


async def _login(client: httpx.AsyncClient, hallticket: str, password: str) -> str:
    """Runs the full login + navigation chain, returns the HTML of the
    OverallMarksSemwiseMarks.aspx landing page (the one listing
    semester buttons)."""

    # STEP 1 - login page
    r = await client.get(LOGIN_URL)
    hidden = _hidden_fields(r.text)

    # STEP 2 - username
    r = await client.post(LOGIN_URL, data={
        "__LASTFOCUS": "", "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        **hidden, "txtUserName": hallticket, "btnNext": "Next",
    })
    hidden = _hidden_fields(r.text)

    # STEP 3 - password
    r = await client.post(LOGIN_URL, data={
        "__LASTFOCUS": "", "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        **hidden, "txtPassword": password, "btnSubmit": "Submit",
    })
    hidden = _hidden_fields(r.text)

    # STEP 4 - the dashboard hop the old code was missing entirely.
    # This one costs ~2.5s server-side in the HAR - real, unavoidable.
    r = await client.post(DASHBOARD_URL, data={
        "__EVENTTARGET": "ctl00$cpStud$lnkStudentMain",
        "__EVENTARGUMENT": "",
        **hidden,
    })
    hidden = _hidden_fields(r.text)

    # STEP 5 - trigger the Overall Marks link from MainStud (302 redirect)
    r = await client.post(MAIN_URL, data={
        "__EVENTTARGET": "ctl00$cpHeader$ucStud$lnkOverallMa",
        "__EVENTARGUMENT": "",
        **hidden,
    }, follow_redirects=True)

    return r.text


async def list_semesters(hallticket: str, password: str):
    """Logs in and returns available (field_name, label) semester
    buttons without fetching any semester's detail yet - useful for
    deciding which semesters are actually needed before paying the
    ~2s-per-semester cost."""
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(
        headers=HEADERS, http2=True, limits=limits,
        timeout=httpx.Timeout(15.0, connect=5.0),
    ) as client:
        html = await _login(client, hallticket, password)
        return _find_semester_buttons(html)


async def fetch_all_semesters_single_session(hallticket: str, password: str) -> dict:
    """Baseline CORRECT approach: one session, one semester click at a
    time, sequentially - because VIEWSTATE genuinely chains between
    these requests (confirmed against the HAR) and can't be skipped
    within a single session. Expect ~2s PER semester on top of ~6s of
    login/navigation overhead."""
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(
        headers=HEADERS, http2=True, limits=limits,
        timeout=httpx.Timeout(15.0, connect=5.0),
    ) as client:
        html = await _login(client, hallticket, password)
        hidden = _hidden_fields(html)
        buttons = _find_semester_buttons(html)

        all_html = [html]
        for field_name, label in buttons:
            r = await client.post(SEMWISE_URL, data={
                "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                **hidden, field_name: label,
            })
            hidden = _hidden_fields(r.text)  # chain forward
            all_html.append(r.text)

    combined = "\n".join(all_html)
    return await asyncio.to_thread(parse_results, combined)


async def fetch_all_semesters_parallel_sessions(hallticket: str, password: str) -> dict:
    """UNTESTED against the live site - I have no network path to
    aceexam.in to confirm it tolerates concurrent logins on one
    account. Opens one independent login session PER semester and
    fetches them all with asyncio.gather. Trades N extra logins
    (~6s each) for wall-clock parallelism: if the server allows it,
    wall time collapses toward the single slowest session instead of
    the sum of all of them. Try this against a real test account
    first and watch for rate-limiting or session-collision errors
    before using it for real."""

    buttons = await list_semesters(hallticket, password)
    if not buttons:
        return await fetch_all_semesters_single_session(hallticket, password)

    async def fetch_one(field_name: str, label: str) -> str:
        limits = httpx.Limits(max_keepalive_connections=2, max_connections=4)
        async with httpx.AsyncClient(
            headers=HEADERS, http2=True, limits=limits,
            timeout=httpx.Timeout(15.0, connect=5.0),
        ) as client:
            html = await _login(client, hallticket, password)
            hidden = _hidden_fields(html)
            r = await client.post(SEMWISE_URL, data={
                "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                **hidden, field_name: label,
            })
            return r.text

    results = await asyncio.gather(
        *(fetch_one(f, l) for f, l in buttons),
        return_exceptions=True,
    )
    good_html = [r for r in results if isinstance(r, str)]
    failed = [r for r in results if isinstance(r, Exception)]
    if failed:
        print(f"[warn] {len(failed)}/{len(buttons)} parallel semester fetches failed: {failed}")

    combined = "\n".join(good_html)
    return await asyncio.to_thread(parse_results, combined)


def login_and_fetch(hallticket: str, password: str) -> dict:
    return asyncio.run(fetch_all_semesters_single_session(hallticket, password))
