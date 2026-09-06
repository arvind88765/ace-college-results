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
    
    # NO retries - fail instantly, don't retry slow servers
    retry_strategy = Retry(
        total=0,  # NO RETRIES - fail fast
        backoff_factor=0,
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
    timeout = (2, 5)  # EXTREME timeout
    
    try:
        start_time = time.time()
        
        # TRY 0 – SPEED HACK: If cookie is valid, skip auth entirely (will fail if not logged in)
        direct = try_direct_results(s, timeout)
        if direct:
            elapsed = time.time() - start_time
            print(f"✅ Direct fetch (cached session): {elapsed:.2f}s")
            return parse_results(direct.text)
        
        # STEP 1 – load login page
        r = s.get(LOGIN_URL, timeout=timeout)
        r.raise_for_status()
        hidden = get_hidden_fields_fast(r.text)

        # STEP 2 – submit hall ticket
        payload1 = {
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

        # STEP 5 – trigger results postback
        payload3 = {
            "__EVENTTARGET": "ctl00$cpHeader$ucStud$lnkOverallMarks",
            "__VIEWSTATE": hidden["__VIEWSTATE"],
            "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
            "__EVENTVALIDATION": hidden["__EVENTVALIDATION"],
        }
        r = s.post(MAIN_URL, data=payload3, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        
        marks = r if ("SGPA" in r.text or "lblMarks" in r.text) else s.get(RESULT_URL, timeout=timeout)
        
        elapsed = time.time() - start_time
        print(f"✅ Full auth + scrape: {elapsed:.2f}s")
        
        return parse_results(marks.text)
    
    except requests.exceptions.Timeout:
        raise Exception("Timeout - server too slow")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection failed")
    except Exception as e:
        raise Exception(f"Failed: {str(e)}")
    
    finally:
        s.close()
