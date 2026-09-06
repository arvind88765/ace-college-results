import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from parser import parse_results
import re
import time

LOGIN_URL  = "https://aceexam.in/Login.aspx"
MAIN_URL   = "https://aceexam.in/StudentLogin/MainStud.aspx"
RESULT_URL = "https://aceexam.in/StudentLogin/Student/overallMarks.aspx"

# Pre-compile regex patterns for faster matching
VIEWSTATE_RE = re.compile(r'id="__VIEWSTATE"[^>]*value="([^"]*)"', re.DOTALL)
EVENTVAL_RE = re.compile(r'id="__EVENTVALIDATION"[^>]*value="([^"]*)"', re.DOTALL)
VIEWGEN_RE = re.compile(r'id="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"', re.DOTALL)

def create_session():
    """Create hyper-optimized requests session"""
    s = requests.Session()
    
    # Aggressive retry strategy - fail fast
    retry_strategy = Retry(
        total=1,  # Reduced from 2
        backoff_factor=0.1,  # Faster backoff
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy, 
        pool_connections=20,  # Increased for parallel-ready
        pool_maxsize=20
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    # Optimized headers - minimal bloat
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1"
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

def login_and_fetch(hallticket, password):
    """Ultra-fast login flow - minimal requests, aggressive timeouts"""
    s = create_session()
    
    # Aggressive timeouts - fail fast if slow
    timeout = (3, 8)  # (connect: 3s, read: 8s) - reduced from (5, 15)
    
    try:
        start_time = time.time()
        
        # STEP 1 – load login page
        r = s.get(LOGIN_URL, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 2 – submit hall ticket
        payload1 = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
            "txtUserName": hallticket,
            "btnNext": "Next",
        }
        r = s.post(LOGIN_URL, data=payload1, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 3 – submit password
        payload2 = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
            "txtPassword": password,
            "btnSubmit": "Submit",
        }
        r = s.post(LOGIN_URL, data=payload2, timeout=timeout)
        r.raise_for_status()

        # STEP 4 – load main student page
        r = s.get(MAIN_URL, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 5 – trigger lnkOverallMarks postback (THIS IS THE KEY ENDPOINT)
        payload3 = {
            "__EVENTTARGET": "ctl00$cpHeader$ucStud$lnkOverallMarks",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
        }
        r = s.post(MAIN_URL, data=payload3, timeout=timeout, allow_redirects=True)
        r.raise_for_status()

        # STEP 6 – fetch the full results page (finally!)
        marks = s.get(RESULT_URL, timeout=timeout)
        marks.raise_for_status()
        
        elapsed = time.time() - start_time
        print(f"✅ Full scrape completed in {elapsed:.2f}s")
        
        return parse_results(marks.text)
    
    except requests.exceptions.Timeout:
        raise Exception("Request timeout - aceexam.in server is slow. Try again.")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection failed - check your internet or aceexam.in is down.")
    except Exception as e:
        raise Exception(f"Scrape failed: {str(e)}")
    
    finally:
        s.close()
