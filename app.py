# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
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
# SYLLABUS FUNCTIONS
# -------------------------------
def clean_line(line):
    bad = ["annexure","notice","commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line)<120

def read_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
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
            with open(os.path.join(r,f),"rb") as file:
                lines = read_pdf(file)
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

def parse_uploaded_syllabus(files):
    data = defaultdict(list)
    for f in files:
        lines = read_pdf(f)
        subject = None
        for l in lines:
            if l.isupper() and l.replace(" ","").isalpha():
                subject = l.title()
            elif subject:
                parts = [p.strip() for p in l.split(",") if len(p.strip())>3]
                data[subject].extend(parts)
    return data

def estimate_time_min(topic, exam):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words*3 + complexity*10
    weight = {"NEET":1.1,"IIT JEE":1.3,"GATE":1.5}.get(exam,1)
    return int(base*weight)

# -------------------------------
# USER INPUT: EXAM & SYLLABUS
# -------------------------------
st.title("📚 AI-Powered Study Planner")

exam = st.selectbox("Select Exam", ["NEET","IIT JEE","GATE"])

syllabus_option = st.radio(
    "Choose Syllabus",
    ["Use available exam syllabus", "Upload my own syllabus"]
)

syllabus_json = {}

if syllabus_option == "Use available exam syllabus":
    if not os.path.exists(EXTRACT_DIR):
        if not os.path.exists(ZIP_PATH):
            gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(EXTRACT_DIR)
    syllabus = parse_syllabus(EXTRACT_DIR)
    if exam not in syllabus:
        st.error("Syllabus not found.")
        st.stop()
    syllabus_json = syllabus[exam]

else:
    uploaded_files = st.file_uploader(
        "Upload syllabus PDF(s)",
        type=["pdf"],
        accept_multiple_files=True
    )
    if not uploaded_files:
        st.warning("Upload at least one PDF.")
        st.stop()
    syllabus_json = parse_uploaded_syllabus(uploaded_files)
    if not syllabus_json:
        st.error("No valid syllabus found.")
        st.stop()

subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
questions_per_topic = st.number_input("Questions per topic per day",10,200,30)
revision_every_n_days = st.number_input("Revision Day Frequency (every N days)",5,30,7)
test_every_n_days = st.number_input("Test Day Frequency (every N days)",7,30,14)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q=deque()
    for s in selected_subjects:
        for t in syllabus_json[s]:
            q.append({"subject":s,"topic":t,"time_min":estimate_time_min(t, exam)})
    return q

# -------------------------------
# ASSIGN DAILY PLAN
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    subject_queues={s:deque([i for i in queue if i["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time_min"],daily_min)
            plan.append({"subject":item["subject"],"topic":item["topic"],"time_min":alloc})
            daily_min-=alloc
            item["time_min"]-=alloc
            if item["time_min"]<=0:
                for i,q in enumerate(queue):
                    if q["subject"]==item["subject"] and q["topic"]==item["topic"]:
                        del queue[i]
                        break
            if daily_min<=0: break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date,datetime.min.time())
    while queue:
        daily_min=int(daily_hours*60)
        day_type="STUDY"
        plan=assign_daily_plan(queue,daily_min)
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","time_min":0}]
            streak=0
        elif day_count and day_count%revision_every_n_days==0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revision","time_min":daily_min}]
        elif day_count and day_count%test_every_n_days==0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test","time_min":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"questions":questions_per_topic,"type":day_type})
        streak+=1 if day_type=="STUDY" else 0
        day_count+=1
        cur_date+=timedelta(days=1)
    return calendar

if selected_subjects and not st.session_state.calendar:
    st.session_state.calendar=generate_calendar(build_queue())

# -------------------------------
# DISPLAY STUDY PLAN
# -------------------------------
st.header("📆 Study Plan")

for day in st.session_state.calendar:
    st.subheader(day["date"].strftime("%A, %d %b %Y"))
    for p in day["plan"]:
        st.write(f"- {p['subject']} → {p['topic']} ({p['time_min']} min)")

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
