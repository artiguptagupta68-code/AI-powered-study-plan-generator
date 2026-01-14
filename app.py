# app.py
import streamlit as st
import os, zipfile, gdown, fitz, re, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# =================================================
# CONFIG
# =================================================
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"

MIN_SUBTOPIC_H = 0.33  # 20 minutes

st.set_page_config("📚 Smart Study Planner", layout="wide")

# =================================================
# SESSION STATE INIT
# =================================================
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()

if "base_queue" not in st.session_state:
    st.session_state.base_queue = None

if "remaining_queue" not in st.session_state:
    st.session_state.remaining_queue = None

if "calendar" not in st.session_state:
    st.session_state.calendar = None

if "recompute_needed" not in st.session_state:
    st.session_state.recompute_needed = False

# =================================================
# LOAD STATE (BACKWARD SAFE)
# =================================================
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            st.session_state.completed_subtopics = set(data)
        elif isinstance(data, dict):
            st.session_state.completed_subtopics = set(data.get("subs", []))
    except Exception:
        st.session_state.completed_subtopics = set()

# =================================================
# DOWNLOAD & EXTRACT
# =================================================
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# =================================================
# PDF PARSING
# =================================================
def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for p in doc:
        for l in p.get_text().split("\n"):
            l = l.strip()
            if l and len(l) < 120:
                lines.append(l)
    return lines

def detect_exam(lines):
    t = " ".join(lines).upper()
    if "NEET" in t: return "NEET", "UG"
    if "JEE" in t: return "IIT JEE", "JEE Main"
    if "GATE" in t: return "GATE", "General"
    return None, None

def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"): continue
            lines = read_pdf(os.path.join(r, f))
            exam, stage = detect_exam(lines)
            if not exam: continue

            subject, topic = None, None
            for l in lines:
                if l.isupper():
                    subject = l.title()
                elif ":" in l and subject:
                    topic = l.replace(":", "").strip()
                elif subject and topic:
                    for p in l.split(","):
                        if len(p.strip()) > 3:
                            data[exam][stage][subject].append(p.strip())
    return data

syllabus = parse_syllabus(EXTRACT_DIR)

# =================================================
# UI INPUTS
# =================================================
st.title("📅 Smart Study Planner")

exam = st.selectbox("Select Exam", syllabus.keys())
stage = st.selectbox("Select Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Select Subjects (priority order)", subjects)

start_date = st.date_input("Start Date", datetime.today())
total_days = st.number_input("Total Preparation Days", min_value=7, value=60)
daily_hours = st.number_input("Daily Study Hours", min_value=1.0, value=6.0)

# =================================================
# BUILD BASE QUEUE (ONCE)
# =================================================
def build_queue():
    q = deque()
    for s in selected_subjects:
        for sub in syllabus[exam][stage][s]:
            h = max(0.3 + 0.05 * len(sub.split()), MIN_SUBTOPIC_H)
            q.append({
                "subject": s,
                "subtopic": sub,
                "time_h": h,
                "time_min": round(h * 60)
            })
    return q

if selected_subjects and st.session_state.base_queue is None:
    st.session_state.base_queue = build_queue()
    st.session_state.remaining_queue = deque(st.session_state.base_queue)
    st.session_state.recompute_needed = True

# =================================================
# RECOMPUTE CALENDAR (ONLY WHEN NEEDED)
# =================================================
if st.session_state.recompute_needed and st.session_state.remaining_queue:
    calendar = []
    cur = datetime.combine(start_date, datetime.min.time())
    queue = deque(st.session_state.remaining_queue)

    for _ in range(total_days):
        remaining = daily_hours
        plan = []

        while queue and remaining > 0:
            item = queue.popleft()
            alloc = min(item["time_h"], remaining)

            plan.append({
                "subject": item["subject"],
                "subtopic": item["subtopic"],
                "time_h": alloc,
                "time_min": round(alloc * 60)
            })

            remaining -= alloc
            item["time_h"] -= alloc

            if item["time_h"] > 0:
                queue.appendleft(item)

        calendar.append({"date": cur, "plan": plan})
        cur += timedelta(days=1)

    st.session_state.calendar = calendar
    st.session_state.remaining_queue = queue
    st.session_state.recompute_needed = False

# =================================================
# DISPLAY CALENDAR
# =================================================
if st.session_state.calendar:
    st.header("📆 Study Calendar")

    for day_idx, day in enumerate(st.session_state.calendar):
        st.subheader(day["date"].strftime("%A, %d %b %Y"))

        for item_idx, s in enumerate(day["plan"]):
            key = f"{day_idx}_{item_idx}_{s['subtopic']}"
            checked = key in st.session_state.completed_subtopics

            if st.checkbox(
                f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)",
                value=checked,
                key=key
            ):
                if key not in st.session_state.completed_subtopics:
                    st.session_state.completed_subtopics.add(key)

                    # remove completed subtopic from remaining queue
                    st.session_state.remaining_queue = deque(
                        i for i in st.session_state.remaining_queue
                        if i["subtopic"] != s["subtopic"]
                    )

                    st.session_state.recompute_needed = True

# =================================================
# SAVE STATE
# =================================================
with open(STATE_FILE, "w") as f:
    json.dump(
        {"subs": list(st.session_state.completed_subtopics)},
        f,
        indent=2
    )
