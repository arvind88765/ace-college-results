import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from parser import parse_results
import re

LOGIN_URL  = "https://aceexam.in/Login.aspx"
MAIN_URL   = "https://aceexam.in/StudentLogin/MainStud.aspx"
RESULT_URL = "https://aceexam.in/StudentLogin/Student/overallMarks.aspx"

# Pre-compile regex patterns for faster matching
VIEWSTATE_RE = re.compile(r'value="([^"]*)"[^>]*id="__VIEWSTATE"', re.DOTALL)
EVENTVAL_RE = re.compile(r'value="([^"]*)"[^>]*id="__EVENTVALIDATION"', re.DOTALL)
VIEWGEN_RE = re.compile(r'value="([^"]*)"[^>]*id="__VIEWSTATEGENERATOR"', re.DOTALL)

def create_session():
    """Create optimized requests session with connection pooling and retries"""
    s = requests.Session()
    
    # Connection pooling & retry strategy for resilience
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Connection": "keep-alive"
    })
    
    return s

def get_hidden_fields_fast(html):
    """Extract hidden fields using regex (10x faster than BeautifulSoup for single fields)"""
    return {
        "__VIEWSTATE": VIEWSTATE_RE.search(html).group(1) if VIEWSTATE_RE.search(html) else "",
        "__EVENTVALIDATION": EVENTVAL_RE.search(html).group(1) if EVENTVAL_RE.search(html) else "",
        "__VIEWSTATEGENERATOR": VIEWGEN_RE.search(html).group(1) if VIEWGEN_RE.search(html) else "",
    }

def login_and_fetch(hallticket, password):
    """Optimized login flow with connection pooling & timeout"""
    s = create_session()
    
    # Set aggressive timeout (20s total per request)
    timeout = (5, 15)  # (connect, read)

    try:
        # STEP 1 – load login page
        r = s.get(LOGIN_URL, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 2 – submit hall ticket
        payload1 = {
            "__LASTFOCUS":          "",
            "__EVENTTARGET":        "",
            "__EVENTARGUMENT":      "",
            "__VIEWSTATE":          hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION":    hidden["__EVENTVALIDATION"],
            "txtUserName":          hallticket,
            "btnNext":              "Next",
        }
        r = s.post(LOGIN_URL, data=payload1, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 3 – submit password
        payload2 = {
            "__LASTFOCUS":          "",
            "__EVENTTARGET":        "",
            "__EVENTARGUMENT":      "",
            "__VIEWSTATE":          hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION":    hidden["__EVENTVALIDATION"],
            "txtPassword":          password,
            "btnSubmit":            "Submit",
        }
        r = s.post(LOGIN_URL, data=payload2, timeout=timeout)
        r.raise_for_status()

        # STEP 4 – load main student page
        r = s.get(MAIN_URL, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 5 – trigger lnkOverallMarks postback → redirects to overallMarks.aspx
        payload3 = {
            "__EVENTTARGET": "ctl00$cpHeader$ucStud$lnkOverallMarks",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
        }
        r = s.post(MAIN_URL, data=payload3, timeout=timeout, allow_redirects=True)
        r.raise_for_status()

        # STEP 6 – fetch the full results page
        marks = s.get(RESULT_URL, timeout=timeout)
        marks.raise_for_status()
        
        return parse_results(marks.text)
    
    finally:
        s.close()
