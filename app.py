# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ----------------- CONFIG -----------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MIN_SUBTOPIC_TIME_H = 0.33  # 20 minutes

st.set_page_config("📚 Study Planner", layout="wide")

# ----------------- SESSION STATE -----------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()
if "calendar_cache" not in st.session_state:
    st.session_state.calendar_cache = []

# ----------------- LOAD PROGRESS -----------------
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        st.session_state.completed_subtopics = set(data.get("subs", [])) if isinstance(data, dict) else set()
    except:
        st.session_state.completed_subtopics = set()

# ----------------- DOWNLOAD & EXTRACT -----------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)
if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# ----------------- PDF HELPERS -----------------
def is_garbage(line):
    bad = ["government", "commission", "notice", "annexure"]
    return any(b in line.lower() for b in bad) or len(line) > 120

def read_pdf(path):
    doc = fitz.open(path)
    lines = []
    for p in doc:
        for l in p.get_text().split("\n"):
            l = l.strip()
            if l and not is_garbage(l):
                lines.append(l)
    return lines

def detect_exam(lines):
    t = " ".join(lines).upper()
    if "NEET" in t: return "NEET", "UG"
    if "JEE" in t: return "IIT JEE", "JEE Main"
    if "GATE" in t: return "GATE", "General"
    return None, None

# ----------------- PARSE SYLLABUS -----------------
def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"): continue
            lines = read_pdf(os.path.join(r, f))
            exam, stage = detect_exam(lines)
            if not exam: continue

            subj, topic = None, None
            for l in lines:
                if l.isupper() and l.replace(" ", "").isalpha():
                    subj, topic = l.title(), None
                elif ":" in l and subj:
                    topic = l.replace(":", "").strip()
                elif subj and topic:
                    parts = [p.strip() for p in l.split(",") if len(p) > 3]
                    data[exam][stage][subj][topic].extend(parts)
    return data

syllabus = parse_syllabus(EXTRACT_DIR)

# ----------------- UI -----------------
st.title("📅 Competitive Exam Study Planner")

exam = st.selectbox("Select Exam", syllabus.keys())
stage = st.selectbox("Select Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Subjects (priority order)", subjects)

start_date = st.date_input("📆 Start Date", datetime.today())
total_days = st.number_input("🗓️ Total preparation days", min_value=7, value=90)
daily_hours = st.number_input("⏱️ Daily study hours", min_value=1.0, value=6.0)

st.markdown("### Optional: Custom days per subject")
subject_days = {}
for s in selected_subjects:
    subject_days[s] = st.number_input(f"{s} days", min_value=0, value=0)

# ----------------- BUILD QUEUE -----------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for _, subs in syllabus[exam][stage][s].items():
            for sub in subs:
                est = max(0.3 + 0.05 * len(sub.split()), MIN_SUBTOPIC_TIME_H)
                q.append({
                    "subject": s,
                    "subtopic": sub,
                    "time_h": est,
                    "time_min": round(est*60)
                })
    return q

queue = build_queue()

# ----------------- GENERATE CALENDAR -----------------
calendar = []
cur_date = datetime.combine(start_date, datetime.min.time())

for _ in range(total_days):
    rem = daily_hours
    plan = []

    idx = 0
    while queue and rem > 0:
        item = queue.popleft()
        alloc = min(item["time_h"], rem)
        plan.append({
            **item,
            "time_h": alloc,
            "time_min": round(alloc*60)
        })
        rem -= alloc
        item["time_h"] -= alloc
        if item["time_h"] > 0:
            queue.appendleft(item)  # put back the remaining part

    calendar.append({"date": cur_date, "plan": plan})
    cur_date += timedelta(days=1)

st.session_state.calendar_cache = calendar

# ----------------- DISPLAY CALENDAR -----------------
st.header("📆 Study Calendar")
for day in st.session_state.calendar_cache:
    st.subheader(day["date"].strftime("%A, %d %b %Y"))

    day_time_used = 0
    for i, s in enumerate(day.get("plan", []) or []):
        raw_key = f"{day['date']}_{s['subject']}_{s['subtopic']}_{i}"
        key = hashlib.md5(raw_key.encode()).hexdigest()
        checked = key in st.session_state.completed_subtopics

        label = f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)"
        if st.checkbox(label, value=checked, key=key):
            st.session_state.completed_subtopics.add(key)
        else:
            st.session_state.completed_subtopics.discard(key)

        day_time_used += s["time_h"]

    # Warning if daily assignment not completed
    if day_time_used < daily_hours:
        extra_days = round((daily_hours - day_time_used)/daily_hours, 1)
        st.warning(f"⚠️ Your target to complete the subject may be increased by {extra_days} day(s).")

# ----------------- SAVE STATE -----------------
with open(STATE_FILE, "w") as f:
    json.dump({"subs": list(st.session_state.completed_subtopics)}, f, indent=2)
