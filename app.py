# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
from collections import defaultdict, deque
from datetime import datetime, timedelta

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"

MAX_CONTINUOUS_DAYS = 6
FREE_DAY_BUFFER_MIN = 300  # 5 hours

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
# DOWNLOAD & EXTRACT
# -------------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)

if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(EXTRACT_DIR)

# -------------------------------
# PDF PARSING
# -------------------------------
def clean_line(line):
    bad = ["annexure", "notice", "commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line) < 120

def read_pdf(path):
    doc = fitz.open(path)
    lines = []
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
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"):
                continue
            lines = read_pdf(os.path.join(r, f))
            exam = detect_exam(lines)
            if not exam:
                continue
            subject = None
            for l in lines:
                if l.isupper() and l.replace(" ", "").isalpha():
                    subject = l.title()
                elif subject:
                    parts = [p.strip() for p in l.split(",") if len(p.strip()) > 3]
                    data[exam][subject].extend(parts)
    return data

syllabus = parse_syllabus(EXTRACT_DIR)
if not syllabus:
    st.error("❌ No syllabus data found.")
    st.stop()

# -------------------------------
# TIME ESTIMATION
# -------------------------------
def estimate_time_min(topic, exam):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words * 3 + complexity * 10
    weight = {"NEET":1.1, "IIT JEE":1.3, "GATE":1.5}.get(exam,1)
    return int(base * weight)

# -------------------------------
# UI INPUTS
# -------------------------------
st.title("📅 AI Study Planner (Week View)")

exam = st.selectbox("Select Exam", list(syllabus.keys()))
subjects = list(syllabus[exam].keys())
selected_subjects = st.multiselect("Select Subjects", subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
questions_per_day = st.number_input("Questions per topic per day", 10, 200, 30)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t in syllabus[exam][s]:
            q.append({
                "subject": s,
                "topic": t,
                "time_min": estimate_time_min(t, exam)
            })
    return q

# -------------------------------
# GENERATE CALENDAR WEEK-BY-WEEK
# -------------------------------
if selected_subjects:
    queue = build_queue()
    calendar = []
    cur_date = datetime.combine(start_date, datetime.min.time())
    streak = 0

    while queue:
        daily_min = int(daily_hours * 60)
        plan = []

        while queue and daily_min > 0:
            item = queue.popleft()
            if item["time_min"] <= daily_min:
                plan.append(item)
                daily_min -= item["time_min"]
            else:
                plan.append({**item, "time_min": daily_min})
                item["time_min"] -= daily_min
                queue.appendleft(item)
                daily_min = 0

        # Add free day if streak limit reached
        if streak >= MAX_CONTINUOUS_DAYS:
            calendar.append({
                "date": cur_date,
                "plan": [{"subject":"FREE","topic":"Rest / light revision","time_min":0}],
                "questions":0
            })
            streak = 0
        else:
            calendar.append({
                "date": cur_date,
                "plan": plan,
                "questions": questions_per_day
            })
            streak += 1

        cur_date += timedelta(days=1)

    st.session_state.calendar = calendar

# -------------------------------
# TABS
# -------------------------------
tab1, tab2, tab3 = st.tabs([
    "📖 Study Plan",
    "📝 Question Practice",
    "✅ Day Completed"
])

# -------------------------------
# STUDY PLAN TAB (WEEKLY)
# -------------------------------
with tab1:
    st.header("📆 Weekly Study Plan")

    # group days by week
    weeks = defaultdict(list)
    for day in st.session_state.calendar:
        week_num = day["date"].isocalendar()[1]
        weeks[week_num].append(day)

    for w_num, days in weeks.items():
        st.subheader(f"Week {w_num}")
        for day in days:
            st.markdown(f"**{day['date'].strftime('%A, %d %b %Y')}**")
            for i, p in enumerate(day["plan"]):
                key = f"{day['date']}_{i}_{p['topic']}"
                checked = key in st.session_state.completed
                label = f"{p['subject']} → {p['topic']} ({p['time_min']} min / {round(p['time_min']/60,2)} h)"
                if st.checkbox(label, checked, key=key):
                    st.session_state.completed.add(key)
                else:
                    st.session_state.completed.discard(key)

# -------------------------------
# PRACTICE TAB
# -------------------------------
with tab2:
    st.header("📝 Daily Question Practice")
    day_labels = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", day_labels)
    idx = day_labels.index(sel)
    day = st.session_state.calendar[idx]

    for i, p in enumerate(day["plan"]):
        if p["subject"] == "FREE":
            continue
        key = f"Q_{sel}_{i}"
        st.session_state.practice_done[key] = st.number_input(
            f"{p['subject']} → {p['topic']} ({day['questions']} questions)",
            0, day["questions"],
            st.session_state.practice_done.get(key, 0),
            key=key
        )

# -------------------------------
# DAY COMPLETED TAB
# -------------------------------
with tab3:
    st.header("✅ Mark Day Completed")
    day_labels = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    sel = st.selectbox("Select Day", day_labels)
    idx = day_labels.index(sel)
    day = st.session_state.calendar[idx]

    unfinished = []
    for i, p in enumerate(day["plan"]):
        if p["subject"] == "FREE":
            continue
        key = f"{day['date']}_{i}_{p['topic']}"
        if key not in st.session_state.completed:
            unfinished.append(p)

    if st.button("Confirm Day Completion"):
        if not unfinished:
            st.success("🎉 All subtopics completed!")
        else:
            # Ensure next day exists
            if idx + 1 >= len(st.session_state.calendar):
                st.session_state.calendar.append({
                    "date": day["date"] + timedelta(days=1),
                    "plan": [],
                    "questions": day["questions"]
                })
            # Move unfinished subtopics to next day
            st.session_state.calendar[idx + 1]["plan"] = unfinished + st.session_state.calendar[idx + 1]["plan"]
            st.warning(f"{len(unfinished)} unfinished subtopics moved to next day")
            for u in unfinished:
                st.write(f"• {u['subject']} → {u['topic']}")

# -------------------------------
# ADAPTIVE WARNING
# -------------------------------
unfinished_min = 0
for d in st.session_state.calendar:
    for i, p in enumerate(d["plan"]):
        key = f"{d['date']}_{i}_{p['topic']}"
        if key not in st.session_state.completed and p["subject"] != "FREE":
            unfinished_min += p["time_min"]

if unfinished_min > FREE_DAY_BUFFER_MIN:
    st.warning(
        f"⚠️ {unfinished_min} min ({round(unfinished_min/60,2)} h) pending. Consider adding a free/revision day."
    )

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE, "w") as f:
    json.dump(list(st.session_state.completed), f)
