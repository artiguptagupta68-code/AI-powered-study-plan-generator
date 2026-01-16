# app.py
import streamlit as st
import os, zipfile, gdown, fitz, pytesseract, io, json, re
from PIL import Image
from collections import deque, defaultdict
from datetime import datetime, timedelta

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config("📚 AI Study Planner", layout="wide")
st.title("📚 AI Study Planner (Junior Engineer Edition)")

# -------------------------------
# SESSION STATE
# -------------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF FUNCTIONS
# -------------------------------
def read_pdf(file):
    """Read PDF: use text if available, OCR if scanned"""
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
    except:
        st.error(f"Cannot open PDF: {file.name}")
        return []
    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip())>2]
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip())>2]
        lines.extend(page_lines)
    return lines

def parse_uploaded_syllabus(files):
    """Parse uploaded PDFs into JSON: subject -> topic -> subtopic"""
    syllabus = defaultdict(lambda: defaultdict(list))
    current_subject = None
    current_topic = None
    for f in files:
        lines = read_pdf(f)
        for line in lines:
            line = line.strip()
            if not line: continue
            # Subject detection (ALL CAPS)
            if line.isupper() and len(line.split()) <= 6 and re.sub(r"[^A-Z]", "", line):
                current_subject = line.title()
                current_topic = None
            # Topic detection (Capitalized)
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)
                elif current_subject:
                    syllabus[current_subject]["General"].append(line)
                else:
                    syllabus["General"]["General"].append(line)
    return dict(syllabus)

# -------------------------------
# DEFAULT SYLLABUS FUNCTIONS
# -------------------------------
def clean_line(line):
    bad = ["annexure","notice","commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line)<120

def read_pdf_default(path):
    doc = fitz.open(path)
    lines=[]
    for p in doc:
        for l in p.get_text().split("\n"):
            if clean_line(l):
                lines.append(l.strip())
    return lines

def detect_exam(lines):
    text = " ".join(lines).upper()
    if "NEET" in text: return "NEET"
    if "JEE" in text: return "IIT JEE"
    if "GATE" in text: return "GATE"
    return None

def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(list))
    for r,_,files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"): continue
            lines = read_pdf_default(os.path.join(r,f))
            exam = detect_exam(lines)
            if not exam: continue
            subject = None
            for l in lines:
                if l.isupper() and l.replace(" ","").isalpha():
                    subject = l.title()
                elif subject:
                    parts = [p.strip() for p in l.split(",") if len(p.strip())>3]
                    data[exam][subject].extend(parts)
    return data

# -------------------------------
# TIME ESTIMATION
# -------------------------------
def estimate_time(text):
    words = len(text.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", text.lower()))
    base = max(15, words*3 + complexity*10)
    return base

def estimate_time_min(topic, exam=None):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words*3 + complexity*10
    weight = {"NEET":1.1,"IIT JEE":1.3,"GATE":1.5}.get(exam,1)
    return int(base*weight)

# -------------------------------
# USER INPUT
# -------------------------------
custom_plan = st.checkbox("Create a study plan of my choice / custom syllabus", key="custom_plan")

if custom_plan:
    exam_name = st.text_input("Enter your Exam Name", key="custom_exam")
    uploaded_files = st.file_uploader(f"Upload syllabus PDF(s) for {exam_name}", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.warning("Please upload at least one PDF to create custom syllabus.")
        st.stop()
    syllabus_json = parse_uploaded_syllabus(uploaded_files)
    if not syllabus_json:
        st.error("No valid topics found in uploaded PDFs.")
        st.stop()
    subjects = list(syllabus_json.keys())
else:
    exam = st.selectbox("Select Exam", ["NEET","IIT JEE","GATE"], key="exam_select")
    syllabus_source = st.radio("Syllabus Source", ["Use default syllabus", "Upload PDF(s)"], key="syllabus_source")
    syllabus_root = EXTRACT_DIR
    if syllabus_source=="Upload PDF(s)":
        uploaded_files = st.file_uploader(f"Upload syllabus PDFs for {exam}", type=["pdf"], accept_multiple_files=True)
        if uploaded_files:
            os.makedirs(syllabus_root, exist_ok=True)
            for f in uploaded_files:
                with open(os.path.join(syllabus_root,f.name),"wb") as out:
                    out.write(f.read())
            st.success(f"{len(uploaded_files)} files uploaded successfully")
        syllabus_json = parse_uploaded_syllabus(uploaded_files)
    else:
        if not os.path.exists(syllabus_root):
            if not os.path.exists(ZIP_PATH):
                gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH) as z:
                z.extractall(EXTRACT_DIR)
        syllabus = parse_syllabus(syllabus_root)
        if not syllabus or exam not in syllabus:
            st.error(f"No syllabus found for {exam}.")
            st.stop()
        syllabus_json = syllabus[exam]
    subjects = list(syllabus_json.keys())

selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
revision_every_n_days = st.number_input("Revision Day Frequency (every N days)",5,30,7)
test_every_n_days = st.number_input("Test Day Frequency (every N days)",7,30,14)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for topic, subtopics in syllabus_json[s].items():
            for subtopic in subtopics:
                q.append({"subject":s,"topic":topic,"subtopic":subtopic,"time":estimate_time(subtopic)})
    return q

# -------------------------------
# ROUND-ROBIN ASSIGNMENT
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time"],daily_min)
            plan.append({"subject":item["subject"],"topic":item["topic"],"subtopic":item["subtopic"],"minutes":alloc})
            daily_min -= alloc
            item["time"] -= alloc
            if item["time"] <= 0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0: break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue, start_date, daily_hours, revision_every_n_days=7, test_every_n_days=14):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date, datetime.min.time())
    daily_min=int(daily_hours*60)
    while queue:
        day_type="STUDY"
        plan=assign_daily_plan(queue, daily_min)
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Relax / Light revision","minutes":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics","minutes":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics","minutes":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# -------------------------------
# GENERATE PLAN BUTTON
# -------------------------------
if selected_subjects and not st.session_state.calendar:
    queue = build_queue()
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days)

# -------------------------------
# DISPLAY STUDY PLAN
# -------------------------------
st.subheader("📆 Weekly Study Plan")
for day_idx, day in enumerate(st.session_state.calendar):
    day_label = day['date'].strftime("%A, %d %b %Y")
    st.markdown(f"### {day_label} ({day['type']} DAY)")
    unfinished_today = []
    for idx, p in enumerate(day["plan"]):
        subtopic = p.get("subtopic", p.get("topic", ""))
        key = f"{day_label}_{idx}_{subtopic}"
        checked = key in st.session_state.completed
        label = f"**{p['subject']} → {p.get('topic','')} → {subtopic}** ({p.get('minutes',0)} min)"
        if st.checkbox(label, key=key, value=checked):
            st.session_state.completed.add(key)
        else:
            st.session_state.completed.discard(key)
            if p.get("subject") not in ["REVISION","TEST","FREE"]:
                unfinished_today.append(p)
    if st.button(f"Mark Day Completed ({day_label})", key=f"complete_day_{day_idx}"):
        if not unfinished_today:
            st.success("🎉 All subtopics completed for this day!")
        else:
            st.warning(f"{len(unfinished_today)} subtopics unfinished. Carrying forward to next day.")
            next_idx = day_idx + 1
            if next_idx >= len(st.session_state.calendar):
                next_date = day["date"] + timedelta(days=1)
                st.session_state.calendar.append({"date":next_date,"plan":[],"type":"STUDY"})
            st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# -------------------------------
# QUESTION PRACTICE TAB
# -------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan","📝 Question Practice"])
with tab2:
    st.header("📝 Daily Question Practice")
    day_labels=[d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    if day_labels:
        sel=st.selectbox("Select Day", day_labels, key="practice_day_select")
        idx=day_labels.index(sel)
        day=st.session_state.calendar[idx]

        num_questions=st.number_input("Number of questions to practice",1,200,30,key=f"num_questions_{idx}")
        q_type=st.selectbox("Type of questions",["MCQs","Subjective","Long Questions"], key=f"qtype_{idx}")

        for i,p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]:
                continue
            key=f"{sel}_{p['subject']}_{p['topic']}"
            questions=[f"{q_type} Q{q_idx+1} on {p['topic']}" for q_idx in range(num_questions)]
            st.markdown(f"**{p['subject']} → {p['topic']}**")
            for q_idx,q in enumerate(questions):
                st.checkbox(q,key=f"{key}_q{q_idx}", value=st.session_state.practice_done.get(f"{key}_q{q_idx}",False))
                st.session_state.practice_done[f"{key}_q{q_idx}"]=st.session_state.practice_done.get(f"{key}_q{q_idx}",False)

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
