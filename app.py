# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re, io
from collections import deque, defaultdict
from datetime import datetime, timedelta
from PIL import Image
import pytesseract

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config(page_title="📚 AI Study Planner", layout="wide")
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
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF READER (TEXT + OCR)
# -------------------------------
def read_pdf(file_or_path):
    """
    file_or_path can be:
    - Streamlit uploaded file: file-like object with read()
    - Local path string
    """
    if isinstance(file_or_path, str):
        doc = fitz.open(file_or_path)
    else:  # Uploaded file
        doc = fitz.open(stream=file_or_path.read(), filetype="pdf")

    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 2]
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip()) > 2]
        lines.extend(page_lines)
    return lines

# -------------------------------
# PDF → SYLLABUS JSON
# -------------------------------
def parse_uploaded_syllabus(files):
    """Parse uploaded PDFs into JSON: subjects -> topics -> subtopics"""
    syllabus = defaultdict(lambda: defaultdict(list))
    current_subject = None
    current_topic = None
    for f in files:
        lines = read_pdf(f)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Subject detection (ALL CAPS)
            if line.isupper() and len(line.split()) <= 6 and re.sub(r"[^A-Z]", "", line):
                current_subject = line.title()
                current_topic = None
            # Topic detection (Capitalized)
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            # Otherwise, subtopic
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)
                elif current_subject:
                    syllabus[current_subject]["General"].append(line)
                else:
                    syllabus["General"]["General"].append(line)
    return dict(syllabus)

# -------------------------------
# DEFAULT SYLLABUS PARSER
# -------------------------------
def clean_line(line):
    bad = ["annexure","notice","commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line)<120

def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(list))
    for r,_,files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"): continue
            lines = read_pdf(os.path.join(r,f))
            subject = None
            for l in lines:
                if l.isupper() and l.replace(" ","").isalpha():
                    subject = l.title()
                elif subject:
                    parts = [p.strip() for p in l.split(",") if len(p.strip())>3]
                    data[subject]["General"].extend(parts)
    return dict(data)

# -------------------------------
# NORMALIZE SYLLABUS
# -------------------------------
def normalize_syllabus(syllabus_json):
    normalized = {}
    for subject, topics in syllabus_json.items():
        if isinstance(topics, list):
            normalized[subject] = {t:[t] for t in topics}
        elif isinstance(topics, dict):
            normalized[subject] = {t:(v if isinstance(v,list) else [v]) for t,v in topics.items()}
        else:
            normalized[subject] = {"General":[str(topics)]}
    return normalized

# -------------------------------
# ESTIMATE TIME
# -------------------------------
def estimate_time(text):
    words = len(text.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", text.lower()))
    base = max(15, words*3 + complexity*10)
    return base

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue(syllabus_json, selected_subjects):
    q = deque()
    for subject in selected_subjects:
        for topic, subtopics in syllabus_json[subject].items():
            for subtopic in subtopics:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": subtopic,
                    "time": estimate_time(subtopic)
                })
    return q

# -------------------------------
# ASSIGN DAILY PLAN
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
            alloc=min(item["time"], daily_min)
            plan.append({"subject":item["subject"], "topic":item["topic"], "subtopic":item["subtopic"], "minutes":alloc})
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
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics", "minutes":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics", "minutes":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# -------------------------------
# UPLOAD OR DEFAULT SYLLABUS
# -------------------------------
custom_plan = st.checkbox("Create custom study plan")
if custom_plan:
    exam_name = st.text_input("Enter Exam Name", value="Junior Engineer")
    uploaded_files = st.file_uploader(f"Upload syllabus PDF(s) for {exam_name}", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.warning("Upload at least one PDF")
        st.stop()
    syllabus_json = parse_uploaded_syllabus(uploaded_files)
else:
    syllabus_source = st.radio("Syllabus Source", ["Use default syllabus folder", "Upload PDFs"])
    if syllabus_source=="Upload PDFs":
        uploaded_files = st.file_uploader("Upload syllabus PDFs", type=["pdf"], accept_multiple_files=True)
        if not uploaded_files:
            st.warning("Upload at least one PDF")
            st.stop()
        syllabus_json = parse_uploaded_syllabus(uploaded_files)
    else:
        if not os.path.exists(EXTRACT_DIR):
            if not os.path.exists(ZIP_PATH):
                gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH) as z:
                z.extractall(EXTRACT_DIR)
        syllabus_json = parse_syllabus(EXTRACT_DIR)

# Normalize for queue building
syllabus_json = normalize_syllabus(syllabus_json)

# -------------------------------
# SELECT SUBJECTS
# -------------------------------
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select subjects to study", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
revision_every_n_days = st.number_input("Revision Day Frequency",5,30,7)
test_every_n_days = st.number_input("Test Day Frequency",7,30,14)

# -------------------------------
# GENERATE STUDY PLAN
# -------------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days)
    st.success("✅ Study plan generated!")

# -------------------------------
# DISPLAY PLAN + DAY COMPLETED
# -------------------------------
if st.session_state.calendar:
    st.subheader("📆 Weekly Study Plan")
    for day_idx, day in enumerate(st.session_state.calendar):
        day_label = day['date'].strftime("%A, %d %b %Y")
        st.markdown(f"### {day_label} ({day['type']} DAY)")
        unfinished_today = []
        for idx, p in enumerate(day["plan"]):
            subtopic = p.get("subtopic", p.get("topic",""))
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
# SAVE PROGRESS
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed), f)
