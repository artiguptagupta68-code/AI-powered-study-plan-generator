# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# ----------------------------
# CONFIG
# ----------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MIN_SUBTOPIC_TIME_H = 0.33
DEFAULT_FREE_DAY_EVERY = 5
MAX_SCHEDULE_DAYS = 365  # prevent OverflowError

st.set_page_config("📚 Study Planner", layout="wide")

# ----------------------------
# SESSION STATE
# ----------------------------
if "completed_subtopics" not in st.session_state:
    st.session_state.completed_subtopics = set()
if "calendar_cache" not in st.session_state:
    st.session_state.calendar_cache = []

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed_subtopics = set(json.load(f))

# ----------------------------
# DOWNLOAD & EXTRACT
# ----------------------------
if not os.path.exists(ZIP_PATH):
    gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH)
if not os.path.exists(EXTRACT_DIR):
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(EXTRACT_DIR)

# ----------------------------
# PDF CLEANING
# ----------------------------
def is_garbage(line):
    bad = ["government","commission","notice","annexure"]
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

# ----------------------------
# EXAM DETECTION
# ----------------------------
def detect_exam(path, lines):
    t = " ".join(lines).upper()
    if "NEET" in t: return "NEET","UG"
    if "JEE" in t: return "IIT JEE","JEE Main"
    if "GATE" in t: return "GATE","General"
    return None,None

# ----------------------------
# PARSE SYLLABUS
# ----------------------------
def parse_syllabus(root):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for r, _, files in os.walk(root):
        for f in files:
            if not f.endswith(".pdf"): continue
            path = os.path.join(r,f)
            lines = read_pdf(path)
            exam, stage = detect_exam(path, lines)
            if not exam: continue
            subj, topic = None,None
            for l in lines:
                if l.isupper() and l.replace(" ","").isalpha():
                    subj, topic = l.title(), None
                elif ":" in l and subj:
                    topic = l.replace(":","").strip()
                elif subj and topic:
                    parts = [p.strip() for p in l.split(",") if len(p) > 3]
                    data[exam][stage][subj][topic].extend(parts)
    return data

syllabus = parse_syllabus(EXTRACT_DIR)

# ----------------------------
# UI TABS
# ----------------------------
tab1, tab2 = st.tabs(["📚 Study Planner","📝 Question Practice"])

# ----------------------------
# COMMON INPUTS
# ----------------------------
st.sidebar.header("Settings")
exam = st.sidebar.selectbox("Select Exam", syllabus.keys())
stage = st.sidebar.selectbox("Select Stage", syllabus[exam].keys())
subjects = list(syllabus[exam][stage].keys())

# ----------------------------
# STUDY PLANNER TAB
# ----------------------------
with tab1:
    st.header("📚 Study Planner")
    selected_subjects = st.multiselect("Subjects to study", subjects)
    start_date = st.date_input("📆 Start Date", datetime.today())
    daily_hours = st.number_input("Daily study hours", min_value=1.0, value=6.0)
    free_day_every = st.number_input("Free day after every N study days", min_value=0, value=DEFAULT_FREE_DAY_EVERY)
    questions_per_topic = st.number_input("Questions per topic", min_value=0, value=20)

    COLORS = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
    subject_color = {s: COLORS[i % len(COLORS)] for i,s in enumerate(selected_subjects)}

    # ----------------------------
    # BUILD QUEUE
    # ----------------------------
    def build_queue():
        q = deque()
        for s in selected_subjects:
            for t, subs in syllabus[exam][stage][s].items():
                for sub in subs:
                    est_h = max(0.3 + 0.05*len(sub.split()), MIN_SUBTOPIC_TIME_H)
                    q.append({"subject":s,"subtopic":sub,"time_h":est_h,"time_min":round(est_h*60)})
        return q

    if selected_subjects:
        queue = build_queue()
        calendar = []
        cur_date = datetime.combine(start_date, datetime.min.time())
        study_day_count = 0
        carry_forward = deque()
        days_generated = 0

        # ----------------------------
        # DYNAMIC CALENDAR LOOP WITH LIMIT
        # ----------------------------
        while (queue or carry_forward) and days_generated < MAX_SCHEDULE_DAYS:
            rem_h = daily_hours
            plan = []

            # Free day logic
            if free_day_every>0 and study_day_count>0 and study_day_count%free_day_every==0:
                plan.append({"subject":"FREE DAY","subtopic":"Rest / light reading","time_min":0})
                calendar.append({"date":cur_date,"day_type":"Free","plan":plan,"questions":0})
                cur_date += timedelta(days=1)
                continue

            # Carry-forward topics first
            temp_carry = deque()
            while carry_forward and rem_h>0:
                item = carry_forward.popleft()
                alloc = min(item["time_h"], rem_h)
                plan.append({"subject":item["subject"],"subtopic":item["subtopic"],"time_h":alloc,"time_min":round(alloc*60)})
                rem_h -= alloc
                item["time_h"] -= alloc
                if item["time_h"]>0:
                    temp_carry.append(item)
            carry_forward = temp_carry

            # Queue topics
            while queue and rem_h>0:
                item = queue.popleft()
                alloc = min(item["time_h"], rem_h)
                plan.append({"subject":item["subject"],"subtopic":item["subtopic"],"time_h":alloc,"time_min":round(alloc*60)})
                rem_h -= alloc
                item["time_h"] -= alloc
                if item["time_h"]>0:
                    carry_forward.append(item)

            calendar.append({"date":cur_date,"day_type":"Study","plan":plan,"questions":questions_per_topic})
            cur_date += timedelta(days=1)
            study_day_count += 1
            days_generated += 1

        if days_generated >= MAX_SCHEDULE_DAYS:
            st.warning("⚠️ Maximum schedule limit reached. Some topics may remain unscheduled.")

        st.session_state.calendar_cache = calendar

        # ----------------------------
        # WEEKLY VIEW
        # ----------------------------
        st.header("📆 Study Calendar")
        weeks = defaultdict(list)
        for day in calendar:
            weeks[day["date"].isocalendar().week].append(day)

        for w in sorted(weeks.keys()):
            st.subheader(f"Week {w}")
            for day_idx, day in enumerate(weeks[w]):
                st.markdown(f"### {day['date'].strftime('%A, %d %b %Y')} ({day['day_type']}) | Questions: {day['questions']}")
                day_keys = []
                for i, s in enumerate(day["plan"]):
                    key = f"{day['date']}_{i}_{s['subtopic']}"
                    checked = key in st.session_state.completed_subtopics
                    day_keys.append((key,s))
                    col1,col2 = st.columns([1,8])
                    with col1:
                        ticked = st.checkbox("",value=checked,key=key)
                    with col2:
                        st.markdown(f"<b style='color:{subject_color.get(s['subject'],'#000')}'>{s['subject']}</b> → {s['subtopic']} ({s['time_min']} min)",unsafe_allow_html=True)
                    if ticked:
                        st.session_state.completed_subtopics.add(key)
                    else:
                        st.session_state.completed_subtopics.discard(key)

# ----------------------------
# QUESTION PRACTICE TAB
# ----------------------------
with tab2:
    st.header("📝 Question Practice")
    if not st.session_state.calendar_cache:
        st.info("No study schedule found. Complete study tab first.")
    else:
        subjects_q = st.multiselect("Select subjects for practice", subjects)
        st.subheader("Today's Topics for Practice")
        today = st.session_state.calendar_cache[0]
        for t in today["plan"]:
            if t["subject"] in subjects_q and t["subject"]!="FREE DAY":
                st.markdown(f"- {t['subject']} → {t['subtopic']} : {t['time_min']} min, {today['questions']} questions")

# ----------------------------
# SAVE STATE
# ----------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed_subtopics),f)
