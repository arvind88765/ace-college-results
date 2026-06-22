import requests
from bs4 import BeautifulSoup
from parser import parse_results


LOGIN_URL  = "https://aceexam.in/Login.aspx"
MAIN_URL   = "https://aceexam.in/StudentLogin/MainStud.aspx"
RESULT_URL = "https://aceexam.in/StudentLogin/Student/overallMarks.aspx"


def get_hidden_fields(html):
    soup = BeautifulSoup(html, "html.parser")
    return {
        "__VIEWSTATE":
            soup.find(id="__VIEWSTATE")["value"],
        "__EVENTVALIDATION":
            soup.find(id="__EVENTVALIDATION")["value"],
        "__VIEWSTATEGENERATOR":
            soup.find(id="__VIEWSTATEGENERATOR")["value"],
    }


def login_and_fetch(hallticket, password):

    s = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    # STEP 1 – load login page
    r = s.get(LOGIN_URL, headers=headers)
    hidden = get_hidden_fields(r.text)

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
    r = s.post(LOGIN_URL, data=payload1, headers=headers)
    hidden = get_hidden_fields(r.text)

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
    r = s.post(LOGIN_URL, data=payload2, headers=headers)

    # STEP 4 – load main student page
    r = s.get(MAIN_URL, headers=headers)
    hidden = get_hidden_fields(r.text)

    # STEP 5 – trigger lnkOverallMarks postback → redirects to overallMarks.aspx
    payload3 = {
        "__EVENTTARGET":
            "ctl00$cpHeader$ucStud$lnkOverallMarks",
        "__EVENTARGUMENT":      "",
        "__VIEWSTATE":          hidden["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION":    hidden["__EVENTVALIDATION"],
    }
    s.post(MAIN_URL, data=payload3, headers=headers, allow_redirects=True)

    # STEP 6 – fetch the full results page
    marks = s.get(RESULT_URL, headers=headers)
    return parse_results(marks.text)
