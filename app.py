# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MIN_SUBTOPIC_TIME_H = 0.33  # 20 minutes

st.set_page_config("📚 Study Planner", layout="wide")

# -------------------------------------------------
# SESSION STATE INIT
# -------------------------------------------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()

if "remaining_queue" not in st.session_state or st.session_state.remaining_queue is None:
    st.session_state.remaining_queue = deque()

if "calendar_cache" not in st.session_state or st.session_state.calendar_cache is None:
    st.session_state.calendar_cache = []

if "recompute_needed" not in st.session_state:
    st.session_state.recompute_needed = True

# -------------------------------------------------
# LOAD PROGRESS
# -------------------------------------------------
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            st.session_state.completed_subtopics = set(data)
        elif isinstance(data, dict):
            st.session_state.completed_subtopics = set(data.get("subs", []))
    except:
        st.session_state.completed_subtopics = set()

# -------------------------------------------------
# DOWNLOAD & EXTRACT
# -------------------------------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# -------------------------------------------------
# PDF HELPERS
# -------------------------------------------------
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
    if "NEET" in t:
        return "NEET", "UG"
    if "JEE" in t:
        return "IIT JEE", "JEE Main"
    if "GATE" in t:
        return "GATE", "General"
    return None, None

# -------------------------------------------------
# PARSE SYLLABUS
# -------------------------------------------------
def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"):
                continue
            lines = read_pdf(os.path.join(r, f))
            exam, stage = detect_exam(lines)
            if not exam:
                continue

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

# -------------------------------------------------
# UI
# -------------------------------------------------
st.title("📅 Competitive Exam Study Planner")

exam = st.selectbox("Select Exam", syllabus.keys())
stage = st.selectbox("Select Stage", syllabus[exam].keys())

subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Subjects (priority order)", subjects)

start_date = st.date_input("📆 Start Date", datetime.today())
total_days = st.number_input("🗓️ Total preparation days", min_value=7, value=90)
daily_hours = st.number_input("⏱️ Daily study hours", min_value=1.0, value=6.0)

# Optional: custom days per subject
st.markdown("### Optional: Custom days per subject")
subject_days = {}
for s in selected_subjects:
    subject_days[s] = st.number_input(f"{s} days", min_value=0, value=0)

# -------------------------------------------------
# BUILD QUEUE
# -------------------------------------------------
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

if selected_subjects and not st.session_state.remaining_queue:
    st.session_state.remaining_queue = build_queue()
    st.session_state.recompute_needed = True

# -------------------------------------------------
# RECOMPUTE CALENDAR (CARRY FORWARD LOGIC)
# -------------------------------------------------
def recompute_calendar():
    queue = deque(st.session_state.remaining_queue or [])
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())

    for _ in range(total_days):
        rem = daily_hours
        plan = []

        while queue and rem > 0:
            item = queue.popleft()
            alloc = min(item["time_h"], rem)
            plan.append({
                "subject": item["subject"],
                "subtopic": item["subtopic"],
                "time_h": alloc,
                "time_min": round(alloc*60)
            })
            rem -= alloc
            item["time_h"] -= alloc
            if item["time_h"] > 0:
                queue.appendleft(item)  # carry forward

        calendar.append({"date": cur_date, "plan": plan})
        cur_date += timedelta(days=1)

    st.session_state.calendar_cache = calendar
    st.session_state.remaining_queue = queue
    st.session_state.recompute_needed = False

if st.session_state.recompute_needed:
    recompute_calendar()

# -------------------------------------------------
# DISPLAY CALENDAR WITH DAY COMPLETED
# -------------------------------------------------
st.header("📆 Study Calendar")

weeks = defaultdict(list)
for d in st.session_state.calendar_cache or []:
    weeks[d["date"].isocalendar().week].append(d)

tabs = st.tabs([f"Week {i+1}" for i in range(len(weeks))])

for tab, (_, days) in zip(tabs, weeks.items()):
    with tab:
        for day in days:
            st.subheader(day["date"].strftime("%A, %d %b %Y"))

            # Day completed checkbox
            day_key = f"day_completed_{day['date']}"
            if day_key not in st.session_state:
                st.session_state[day_key] = False

            st.checkbox("✅ Mark this day as completed", value=st.session_state[day_key], key=day_key)

            # Show subtopics ONLY if day completed
            if st.session_state[day_key]:
                day_time_used = 0
                with st.container():
                    for i, s in enumerate(day.get("plan", []) or []):
                        key = f"{day['date']}_{s['subject']}_{s['subtopic']}"
                        checked = key in st.session_state.completed_subtopics

                        if st.checkbox(
                            f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)",
                            value=checked,
                            key=key
                        ):
                            if key not in st.session_state.completed_subtopics:
                                st.session_state.completed_subtopics.add(key)
                        else:
                            # Carry forward uncompleted
                            st.session_state.remaining_queue.append({
                                "subject": s["subject"],
                                "subtopic": s["subtopic"],
                                "time_h": s["time_h"],
                                "time_min": s["time_min"]
                            })

                        day_time_used += s["time_h"]

                # Warning if daily assignment not completed
                if day_time_used < daily_hours:
                    extra_days = round((daily_hours - day_time_used)/daily_hours,1)
                    st.warning(f"⚠️ Your target to complete the subject is being increased by {extra_days} day(s).")
                    st.session_state.recompute_needed = True

# -------------------------------------------------
# SAVE STATE
# -------------------------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(
        {"subs": list(st.session_state.completed_subtopics)},
        f,
        indent=2
    )
