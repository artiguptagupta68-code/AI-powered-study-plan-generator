# app.py
import streamlit as st
import os, zipfile, gdown, fitz, re, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"

MIN_SUBTOPIC_H = 0.33  # 20 minutes

st.set_page_config("📚 Study Planner", layout="wide")

# ---------------- STATE ----------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()

if "completed_days" not in st.session_state:
    st.session_state.completed_days = set()

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
        st.session_state.completed_subtopics = set(data.get("subs", []))
        st.session_state.completed_days = set(data.get("days", []))

# ---------------- DOWNLOAD ----------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# ---------------- PDF PARSE ----------------
def read_pdf(p):
    doc = fitz.open(p)
    lines = []
    for page in doc:
        for l in page.get_text().split("\n"):
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

            subj, topic = None, None
            for l in lines:
                if l.isupper():
                    subj = l.title()
                elif ":" in l and subj:
                    topic = l.replace(":", "").strip()
                elif subj and topic:
                    for p in l.split(","):
                        data[exam][stage][subj].append(p.strip())
    return data

syllabus = parse_syllabus(EXTRACT_DIR)

# ---------------- UI ----------------
st.title("📅 Smart Study Planner")

exam = st.selectbox("Exam", syllabus.keys())
stage = st.selectbox("Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Subjects (priority order)", subjects)

start_date = st.date_input("Start Date", datetime.today())
total_days = st.number_input("Total Days", min_value=7, value=60)
daily_hours = st.number_input("Daily Study Hours", min_value=1.0, value=6.0)

# ---------------- BUILD QUEUE ----------------
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

queue = build_queue()

# ---------------- CALENDAR ----------------
calendar = []
cur = datetime.combine(start_date, datetime.min.time())

for d in range(total_days):
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

# ---------------- DISPLAY ----------------
st.header("📆 Study Calendar")

for day_idx, day in enumerate(calendar):
    st.subheader(day["date"].strftime("%A, %d %b %Y"))

    day_key = f"DAY_{day['date']}"

    incomplete_today = []

    for i, s in enumerate(day["plan"]):
        key = f"{day_idx}_{i}_{s['subtopic']}"
        checked = key in st.session_state.completed_subtopics

        if st.checkbox(
            f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)",
            value=checked,
            key=key
        ):
            st.session_state.completed_subtopics.add(key)
        else:
            incomplete_today.append(s)

    # -------- DAY COMPLETED ----------
    if st.checkbox("✅ Mark Day as Completed", key=day_key):
        st.session_state.completed_days.add(day_key)

        # Carry forward unfinished
        for item in reversed(incomplete_today):
            queue.appendleft({
                "subject": item["subject"],
                "subtopic": item["subtopic"],
                "time_h": item["time_h"],
                "time_min": item["time_min"]
            })

        st.success("Day locked. Unfinished topics shifted forward.")

# ---------------- SAVE STATE ----------------
with open(STATE_FILE, "w") as f:
    json.dump({
        "subs": list(st.session_state.completed_subtopics),
        "days": list(st.session_state.completed_days)
    }, f)
