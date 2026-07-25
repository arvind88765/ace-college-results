import re
from bs4 import BeautifulSoup


def parse_overall_result(html):
    """Parses OverallResultStudent.aspx - the SGPA/CGPA-per-semester
    summary table. Written directly against real page source the user
    provided (table id="ctl00_cpStud_grdOverall"), not guessed.

    Note: the table's SNo column is NOT chronological (e.g. row order
    seen was SNo 1,4,2,3,5,6,8,7) - but the row DISPLAY order already
    is chronological (I BTECH I SEM, I BTECH II SEM, II BTECH I SEM...),
    so we preserve display order and ignore SNo for ordering.
    """
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        soup = BeautifulSoup(html, 'html.parser')

    data = {
        "student": {"name": "N/A", "hallticket": "N/A", "branch": "N/A"},
        "cgpa": "N/A",
        "credits": "N/A",
        "backlogs": "N/A",
        "semesters": [],
    }

    full_text = soup.get_text(' ', strip=True)
    name_match = re.search(r'WELCOME\s+([A-Z\s]+)\s*\(\s*([0-9A-Z]+)\s*\)', full_text, re.I)
    if name_match:
        data['student']['name'] = name_match.group(1).strip()
        data['student']['hallticket'] = name_match.group(2).strip()
    branch_match = re.search(r'(CSE|CSM|AIML|AIDS|IT|ECE|EEE|MECH|CIVIL)(?:\s*\([A-Z&]+\))?', full_text, re.I)
    if branch_match:
        data['student']['branch'] = branch_match.group(0).upper().replace('&', '')

    table = soup.find(id="ctl00_cpStud_grdOverall")
    if not table:
        # Table id can vary slightly by ASP.NET naming container; fall
        # back to searching for any table whose header row mentions CGPA.
        for t in soup.find_all('table'):
            header_text = t.find('tr')
            if header_text and 'CGPA' in header_text.get_text().upper():
                table = t
                break

    if table:
        rows = table.find_all('tr')[1:]  # skip header row
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all('td')]
            if len(cells) < 4:
                continue
            _sno, sem_name, sgpa, cgpa = cells[0], cells[1], cells[2], cells[3]
            data['semesters'].append({
                "name": sem_name,
                "sgpa": sgpa,
                "subjects": [],  # subject-level detail not fetched here
            })
            data['cgpa'] = cgpa  # last row = most recent overall CGPA

    return data


def parse_results(html):
    # lxml is roughly 5-10x faster than the stdlib html.parser for
    # table-heavy pages like this results transcript. Falls back to
    # html.parser only if lxml isn't installed.
    try:
        soup = BeautifulSoup(html, 'lxml')
    except Exception:
        soup = BeautifulSoup(html, 'html.parser')
    full_text = soup.get_text(' ', strip=True)

    data = {
        "student": {
            "name": "N/A",
            "hallticket": "N/A",
            "branch": "N/A"
        },
        "cgpa": "N/A",
        "credits": "N/A",
        "backlogs": "N/A",
        "semesters": []
    }

    # --- 1. Top-Level Stats ---
    cgpa_elem = soup.find(id=re.compile(r'lblMarks$'))
    if cgpa_elem: 
        data['cgpa'] = cgpa_elem.get_text(strip=True)
    if not data['cgpa']: 
        data['cgpa'] = 'N/A' # Juniors might have a blank CGPA span

    cred_elem = soup.find(id=re.compile(r'lblCredits$'))
    if cred_elem: 
        data['credits'] = cred_elem.get_text(strip=True).replace(' ', '')

    due_elem = soup.find(id=re.compile(r'lblDue$'))
    if due_elem: 
        data['backlogs'] = due_elem.get_text(strip=True).replace(' ', '')

    # --- 2. Student Info ---
    name_match = re.search(r'WELCOME\s+([A-Z\s]+)\s+\(\s*([0-9A-Z]+)\s*\)', full_text, re.I)
    if name_match:
        data['student']['name'] = name_match.group(1).strip()
        data['student']['hallticket'] = name_match.group(2).strip()

    branch_match = re.search(r'(CSE|CSM|AIML|AIDS|IT|ECE|EEE|MECH|CIVIL)(?:\s*\([A-Z&]+\))?', full_text, re.I)
    if branch_match: 
        data['student']['branch'] = branch_match.group(0).upper().replace('&', '')

    # --- 3. Indestructible Table Parsing ---
    SEM_RE = re.compile(r'([IVX]+\s+B\.?\s*(?:TECH|E|SC)[^\n]{0,30}SEM)', re.I)
    valid_grades = {'O', 'A+', 'A', 'B+', 'B', 'C', 'D', 'P', 'F', 'AB'}

    unique_sems = {} # Used to overwrite duplicate ghost tables
    current_sem = None

    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            raw_cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            
            # Remove all empty/whitespace columns to perfectly collapse the array
            cols = [x for x in raw_cells if x]
            if not cols: continue
            
            row_text = " ".join(cols).upper()
            
            # Detect Semester Header
            sem_match = SEM_RE.search(row_text)
            if sem_match:
                sem_name = sem_match.group(1).strip()
                current_sem = {
                    "name": sem_name,
                    "sgpa": "N/A",
                    "subjects": []
                }
                unique_sems[sem_name] = current_sem
                continue
                
            # Detect SGPA
            if current_sem and 'SGPA:' in row_text:
                sgpa_m = re.search(r'SGPA:\s*([0-9.]+)', row_text)
                if sgpa_m: 
                    current_sem['sgpa'] = sgpa_m.group(1)
                continue

            # Detect Subject Row dynamically
            # Needs to have a few columns, and index 1 must look like a subject code
            if len(cols) >= 5 and current_sem:
                if len(cols[1]) >= 5 and any(c.isdigit() for c in cols[1]):
                    code = cols[1]
                    name = cols[2]
                    
                    status = 'N/A'
                    credits = 'N/A'
                    latest_grade = 'N/A'
                    
                    # MAGIC TRICK: Search backwards for the Pass/Fail Status. 
                    # This completely ignores how many "Attempt" columns the college adds.
                    status_idx = -1
                    for i in range(len(cols)-1, 1, -1):
                        if cols[i].upper() in ['P', 'F', 'AB']:
                            status_idx = i
                            break
                    
                    if status_idx != -1:
                        status = cols[status_idx].capitalize() if cols[status_idx].upper() == 'AB' else cols[status_idx].upper()
                        credits = cols[status_idx - 1]
                        
                        # Extract the grades array sitting between the subject name and credits
                        grades_list = [x for x in cols[3:status_idx] if x.upper() in valid_grades]
                        if grades_list:
                            # Capture the most recent attempt
                            raw_grade = grades_list[-1]
                            latest_grade = raw_grade.capitalize() if raw_grade.upper() == 'AB' else raw_grade.upper()
                    
                    current_sem['subjects'].append({
                        "code": code,
                        "name": name,
                        "grade": latest_grade,
                        "credits": credits,
                        "status": status
                    })

    # Only keep semesters that actually successfully parsed subjects
    data['semesters'] = [s for s in unique_sems.values() if len(s['subjects']) > 0]
    return data
