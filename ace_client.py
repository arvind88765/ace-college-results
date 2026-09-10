import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from parser import parse_results
import re
import time
from concurrent.futures import ThreadPoolExecutor

LOGIN_URL  = "https://aceexam.in/Login.aspx"
MAIN_URL   = "https://aceexam.in/StudentLogin/MainStud.aspx"
RESULT_URL = "https://aceexam.in/StudentLogin/Student/overallMarks.aspx"

# Pre-compile regex patterns for faster matching
VIEWSTATE_RE = re.compile(r'id="__VIEWSTATE"[^>]*value="([^"]*)"', re.DOTALL)
EVENTVAL_RE = re.compile(r'id="__EVENTVALIDATION"[^>]*value="([^"]*)"', re.DOTALL)
VIEWGEN_RE = re.compile(r'id="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"', re.DOTALL)

def create_session():
    """Create hyper-optimized requests session with extreme pooling"""
    s = requests.Session()
    
    # One quick retry on connection blips — zero retries was causing spurious
    # "Connection failed" errors on cross-region serverless calls to a slow host
    retry_strategy = Retry(
        total=1,
        connect=1,
        read=0,
        backoff_factor=0.3,
        status_forcelist=[],
        allowed_methods=[]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy, 
        pool_connections=50,  # MAX connections
        pool_maxsize=50
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    # Ultra-minimal headers
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate",
    })
    
    return s

def get_hidden_fields_fast(html):
    """Extract hidden fields using ultra-fast regex matching"""
    if not html or len(html) < 100:
        return {"__VIEWSTATE": "", "__EVENTVALIDATION": "", "__VIEWSTATEGENERATOR": ""}
    
    viewstate_match = VIEWSTATE_RE.search(html)
    eventval_match = EVENTVAL_RE.search(html)
    viewgen_match = VIEWGEN_RE.search(html)
    
    return {
        "__VIEWSTATE": viewstate_match.group(1) if viewstate_match else "",
        "__EVENTVALIDATION": eventval_match.group(1) if eventval_match else "",
        "__VIEWSTATEGENERATOR": viewgen_match.group(1) if viewgen_match else "",
    }

def try_direct_results(s, timeout):
    """SPEED HACK: Try fetching results directly - if you're already logged in, skip auth steps"""
    try:
        r = s.get(RESULT_URL, timeout=timeout)
        if r.status_code == 200 and ("SGPA" in r.text or "lblMarks" in r.text):
            return r
    except:
        pass
    return None

def login_and_fetch(hallticket, password):
    """MAXIMUM SPEED - skip unnecessary steps, use caching where possible"""
    s = create_session()
    timeout = (5, 15)  # connect timeout, read timeout — generous enough for cross-region serverless calls

    timings = []  # list of {"step": name, "seconds": float}

    def mark(step_name, step_start):
        timings.append({"step": step_name, "seconds": round(time.time() - step_start, 3)})

    try:
        start_time = time.time()

        # TRY 0 – SPEED HACK: If cookie is valid, skip auth entirely (will fail if not logged in)
        t0 = time.time()
        direct = try_direct_results(s, timeout)
        mark("Direct fetch attempt (cached session)", t0)
        if direct:
            t_parse = time.time()
            result = parse_results(direct.text)
            mark("Parse results", t_parse)
            elapsed = time.time() - start_time
            print(f"✅ Direct fetch (cached session): {elapsed:.2f}s")
            result["timings"] = timings
            result["total_seconds"] = round(elapsed, 3)
            return result

        # STEP 1 – load login page
        t1 = time.time()
        r = s.get(LOGIN_URL, timeout=timeout)
        r.raise_for_status()
        mark("Load login page", t1)
        hidden = get_hidden_fields_fast(r.text)

        # STEP 2 – submit hall ticket
        t2 = time.time()
        payload1 = {
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
            "txtUserName": hallticket,
            "btnNext": "Next",
        }
        r = s.post(LOGIN_URL, data=payload1, timeout=timeout)
        r.raise_for_status()
        mark("Submit hall ticket", t2)
        hidden = get_hidden_fields_fast(r.text)

        # STEP 3 – submit password
        t3 = time.time()
        payload2 = {
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
            "txtPassword": password,
            "btnSubmit": "Submit",
        }
        r = s.post(LOGIN_URL, data=payload2, timeout=timeout)
        r.raise_for_status()
        mark("Submit password", t3)

        # STEP 4 – load main student page
        t4 = time.time()
        r = s.get(MAIN_URL, timeout=timeout)
        r.raise_for_status()
        mark("Load main student page", t4)
        hidden = get_hidden_fields_fast(r.text)

        # STEP 5 – trigger results postback
        t5 = time.time()
        payload3 = {
            "__EVENTTARGET": "ctl00$cpHeader$ucStud$lnkOverallMarks",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
        }
        r = s.post(MAIN_URL, data=payload3, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        mark("Results postback", t5)

        t6 = time.time()
        marks = r if ("SGPA" in r.text or "lblMarks" in r.text) else s.get(RESULT_URL, timeout=timeout)
        if marks is not r:
            mark("Fallback results fetch", t6)

        t_parse = time.time()
        result = parse_results(marks.text)
        mark("Parse results", t_parse)

        elapsed = time.time() - start_time
        print(f"✅ Full auth + scrape: {elapsed:.2f}s")

        result["timings"] = timings
        result["total_seconds"] = round(elapsed, 3)
        return result

    except requests.exceptions.Timeout as e:
        raise Exception(f"Timeout - server too slow ({e.__class__.__name__})")
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Connection failed - {e.__class__.__name__}: {e}")
    except Exception as e:
        raise Exception(f"Failed: {str(e)}")

    finally:
        s.close()
