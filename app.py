# app.py
import streamlit as st
import os, zipfile, gdown, fitz, re, json
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
# SESSION STATE
# -------------------------------------------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed_subtopics = set(json.load(f))

# -------------------------------------------------
# DOWNLOAD & EXTRACT
# -------------------------------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# -------------------------------------------------
# PDF CLEANING
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

# -------------------------------------------------
# EXAM DETECTION
# -------------------------------------------------
def detect_exam(path, lines):
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
            if not f.endswith(".pdf"): continue
            path = os.path.join(r, f)
            lines = read_pdf(path)
            exam, stage = detect_exam(path, lines)
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

# -------------------------------------------------
# UI INPUTS
# -------------------------------------------------
st.title("📅 Competitive Exam Study Planner")

exam = st.selectbox("Select Exam", syllabus.keys())
stage = st.selectbox("Select Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())
selected_subjects = st.multiselect("Subjects (priority order)", subjects)

start_date = st.date_input("📆 Start Date", datetime.today())
total_days = st.number_input("🗓️ Total days to finish syllabus", min_value=7, value=90)

daily_hours = st.number_input("⏱️ Daily study hours", min_value=1.0, value=6.0)

st.markdown("### Optional: Custom days per subject")
subject_days = {}
for s in selected_subjects:
    subject_days[s] = st.number_input(f"{s} days", min_value=0, value=0)

# -------------------------------------------------
# COLORS
# -------------------------------------------------
COLORS = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color = {s: COLORS[i % len(COLORS)] for i, s in enumerate(selected_subjects)}

# -------------------------------------------------
# BUILD QUEUE
# -------------------------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t, subs in syllabus[exam][stage][s].items():
            for sub in subs:
                est_h = max(0.3 + 0.05 * len(sub.split()), MIN_SUBTOPIC_TIME_H)
                q.append({
                    "subject": s,
                    "subtopic": sub,
                    "time_h": est_h,
                    "time_min": round(est_h * 60)
                })
    return q

# -------------------------------------------------
# PLAN GENERATION
# -------------------------------------------------
if selected_subjects:
    queue = build_queue()
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())

    subject_day_used = defaultdict(set)

    for day_idx in range(total_days):
        rem_h = daily_hours
        plan = []

        while queue and rem_h > 0:
            item = queue.popleft()
            alloc = min(item["time_h"], rem_h)
            plan.append({
                **item,
                "time_h": alloc,
                "time_min": round(alloc * 60)
            })
            rem_h -= alloc
            item["time_h"] -= alloc
            if item["time_h"] > 0:
                queue.appendleft(item)

        calendar.append({"date": cur_date, "plan": plan})
        cur_date += timedelta(days=1)

    # -------------------------------------------------
    # WEEKLY VIEW
    # -------------------------------------------------
    st.header("📆 Study Calendar")

    weeks = defaultdict(list)
    for d in calendar:
        weeks[d["date"].isocalendar().week].append(d)

    tabs = st.tabs([f"Week {i+1}" for i in range(len(weeks))])

    for tab, (_, days) in zip(tabs, weeks.items()):
        with tab:
            for d_idx, day in enumerate(days):
                st.subheader(day["date"].strftime("%A, %d %b %Y"))

                for i, s in enumerate(day["plan"]):
                    key = f"{day['date']}_{i}_{s['subtopic']}"
                    checked = key in st.session_state.completed_subtopics

                    if st.checkbox(
                        f"{s['subject']} → {s['subtopic']} ({s['time_min']} min)",
                        value=checked,
                        key=key
                    ):
                        st.session_state.completed_subtopics.add(key)
                        subject_day_used[s["subject"]].add(day["date"])
                    else:
                        st.session_state.completed_subtopics.discard(key)

    # -------------------------------------------------
    # PROGRESS
    # -------------------------------------------------
    st.header("📊 Subject Progress")

    cols = st.columns(len(selected_subjects))
    for col, s in zip(cols, selected_subjects):
        total = subject_days[s] if subject_days[s] > 0 else total_days // len(selected_subjects)
        done = len(subject_day_used[s])
        remain = max(0, total - done)

        col.markdown(f"### {s}")
        col.progress(done / total if total else 0)
        col.caption(f"⏳ {remain} days remaining")

# -------------------------------------------------
# SAVE STATE
# -------------------------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed_subtopics), f)
