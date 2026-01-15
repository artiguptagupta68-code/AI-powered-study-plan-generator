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

DAY_STUDY = "Study"
DAY_FREE = "Free"

st.set_page_config("📚 Study Planner", layout="wide")

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()
if "calendar_cache" not in st.session_state:
    st.session_state.calendar_cache = []

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
            path = os.path.join(r, f)
            lines = read_pdf(path)
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
# UI: Tabs
# -------------------------------------------------
tab1, tab2 = st.tabs(["📚 Study Planner", "📝 Question Practice"])

# -------------------------------------------------
# COMMON INPUTS
# -------------------------------------------------
with tab1:
    st.header("📚 Study Planner")
    exam = st.selectbox("Select Exam", syllabus.keys(), key="exam_study")
    stage = st.selectbox("Select Stage", syllabus[exam].keys(), key="stage_study")
    subjects = list(syllabus[exam][stage].keys())
    selected_subjects = st.multiselect(
        "Select subjects to study", subjects, key="subjects_study"
    )

    start_date = st.date_input("Start Date", datetime.today(), key="start_date_study")
    total_days = st.number_input("Total days to finish syllabus", min_value=7, value=90, key="total_days_study")
    daily_hours = st.number_input("Daily study hours", min_value=1.0, value=6.0, key="daily_hours_study")

    free_day_frequency = st.number_input(
        "Free day after every N study days", min_value=0, value=14, key="free_days_study"
    )

with tab2:
    st.header("📝 Question Practice")
    exam_q = st.selectbox("Select Exam", syllabus.keys(), key="exam_q")
    stage_q = st.selectbox("Select Stage", syllabus[exam_q].keys(), key="stage_q")
    subjects_q = list(syllabus[exam_q][stage_q].keys())
    selected_subjects_q = st.multiselect(
        "Select subjects for question practice", subjects_q, key="subjects_q"
    )
    daily_questions = st.number_input(
        "Questions per day", min_value=0, value=50, key="questions_per_day"
    )

# -------------------------------------------------
# COLORS
# -------------------------------------------------
COLORS = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color = {s: COLORS[i % len(COLORS)] for i, s in enumerate(subjects)}

# -------------------------------------------------
# HELPER: Build queue (Study)
# -------------------------------------------------
def build_queue(selected_subjects, syllabus_data):
    q = deque()
    for s in selected_subjects:
        for t, subs in syllabus_data[s].items():
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
# STUDY PLANNER LOGIC
# -------------------------------------------------
if tab1:
    if selected_subjects:
        syllabus_data = syllabus[exam][stage]
        queue = build_queue(selected_subjects, syllabus_data)
        calendar = []
        cur_date = datetime.combine(start_date, datetime.min.time())
        study_day_count = 0

        for day_idx in range(total_days):
            is_free_day = (
                free_day_frequency > 0 and
                study_day_count > 0 and
                study_day_count % free_day_frequency == 0
            )

            if is_free_day:
                calendar.append({
                    "date": cur_date,
                    "day_type": DAY_FREE,
                    "questions": 0,
                    "plan": [{
                        "subject": "FREE DAY",
                        "subtopic": "Rest / recovery / light reading",
                        "time_min": 0
                    }]
                })
                cur_date += timedelta(days=1)
                continue

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
                    break

            calendar.append({
                "date": cur_date,
                "day_type": DAY_STUDY,
                "questions": 0,
                "plan": plan
            })
            cur_date += timedelta(days=1)
            study_day_count += 1

        st.header("📆 Weekly Study Calendar")
        weeks = defaultdict(list)
        for day in calendar:
            weeks[day["date"].isocalendar().week].append(day)

        for w in sorted(weeks.keys()):
            st.subheader(f"Week {w}")
            for day_idx, day in enumerate(weeks[w]):
                st.markdown(f"### {day['date'].strftime('%A, %d %b %Y')} ({day['day_type']})")
                day_keys = []
                for i, s in enumerate(day["plan"]):
                    key = f"{day['date']}_{i}_{s['subtopic']}"
                    checked = key in st.session_state.completed_subtopics
                    day_keys.append((key, s))
                    col1, col2 = st.columns([1, 8])
                    with col1:
                        ticked = st.checkbox("", value=checked, key=key)
                    with col2:
                        st.markdown(
                            f"<b style='color:{subject_color.get(s['subject'], '#000')}'>{s['subject']}</b>"
                            f" → {s['subtopic']} ({s['time_min']} min)",
                            unsafe_allow_html=True
                        )
                    if ticked:
                        st.session_state.completed_subtopics.add(key)
                    else:
                        st.session_state.completed_subtopics.discard(key)

                if st.button(f"✅ Mark {day['date']} as Completed", key=f"done_{day['date']}"):
                    carry = [s for k, s in day_keys if k not in st.session_state.completed_subtopics]
                    if carry:
                        next_day = {
                            "date": day["date"] + timedelta(days=1),
                            "day_type": DAY_STUDY,
                            "questions": 0,
                            "plan": carry
                        }
                        st.session_state.calendar_cache.append(next_day)
                        st.warning("Unfinished topics carried forward to next day")

        with open(STATE_FILE, "w") as f:
            json.dump(list(st.session_state.completed_subtopics), f)

# -------------------------------------------------
# QUESTION PRACTICE LOGIC
# -------------------------------------------------
if tab2:
    if selected_subjects_q:
        syllabus_data_q = syllabus[exam_q][stage_q]
        st.header("📆 Question Practice Plan")
        for s in selected_subjects_q:
            st.subheader(f"{s}")
            topics = []
            for t, subs in syllabus_data_q[s].items():
                topics.extend(subs)
            for sub in topics:
                st.markdown(f"- {sub} → {daily_questions} questions")
