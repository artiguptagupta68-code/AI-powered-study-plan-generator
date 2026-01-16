# app.py
import streamlit as st
import fitz
import re
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta

# -------------------------------
# CONFIG
# -------------------------------
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

if st.experimental_get_query_params().get("reset") or not st.session_state.completed:
    # clear progress if reset
    st.session_state.completed = set()
    st.session_state.calendar = []

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF → JSON SYLLABUS
# -------------------------------
def clean_line(line):
    return line.strip() and len(line.strip()) < 200

def parse_uploaded_syllabus(files):
    """
    Converts uploaded PDFs into JSON: Subject -> Topic -> Subtopics
    """
    syllabus = defaultdict(lambda: defaultdict(list))

    for f in files:
        subject_name = f.name.replace(".pdf","").title() if hasattr(f,"name") else "General Subject"
        doc = fitz.open(f)
        current_topic = None
        topic_counter = 1

        for page in doc:
            for line in page.get_text().split("\n"):
                line = line.strip()
                if not clean_line(line):
                    continue

                # Detect new topic
                if line.isupper() or line.istitle() or re.match(r"^(\d+[\.\)]|[IVX]+\.)\s+", line):
                    current_topic = line
                    if current_topic not in syllabus[subject_name]:
                        syllabus[subject_name][current_topic] = []
                    continue

                # Otherwise, treat as subtopic
                if current_topic is None:
                    current_topic = f"Topic {topic_counter}"
                    syllabus[subject_name][current_topic] = []
                    topic_counter += 1

                syllabus[subject_name][current_topic].append(line)

    return syllabus

# -------------------------------
# AI TIME ESTIMATION
# -------------------------------
def estimate_time_min(topic):
    words = len(topic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", topic.lower()))
    base = 15 + words*3 + complexity*10
    return int(base)

# -------------------------------
# USER INPUT
# -------------------------------
st.title("📚 AI-Powered Study Planner")

uploaded_files = st.file_uploader("Upload syllabus PDF(s)", type=["pdf"], accept_multiple_files=True)
if not uploaded_files:
    st.warning("Please upload at least one PDF to create the syllabus.")
    st.stop()

syllabus_json = parse_uploaded_syllabus(uploaded_files)
if not syllabus_json:
    st.error("Could not extract syllabus from the uploaded PDFs.")
    st.stop()

subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)

start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours", 1.0, 12.0, 6.0)
questions_per_topic = st.number_input("Questions per topic per day", 10, 200, 30)
revision_every_n_days = st.number_input("Revision Day Frequency (every N days)",5,30,7)
test_every_n_days = st.number_input("Test Day Frequency (every N days)",7,30,14)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t, subtopics in syllabus_json[s].items():
            for sub in subtopics:
                q.append({"subject": s, "topic": f"{t}: {sub}", "time_min": estimate_time_min(sub)})
    return q

# -------------------------------
# ROUND-ROBIN ASSIGNMENT
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan = []
    subjects_today = list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues = {s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min > 0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item = subject_queues[s].popleft()
            alloc = min(item["time_min"], daily_min)
            plan.append({"subject": item["subject"], "topic": item["topic"], "time_min": alloc})
            daily_min -= alloc
            item["time_min"] -= alloc
            if item["time_min"] > 0:
                subject_queues[s].appendleft(item)
            else:
                # remove from main queue
                for q_idx, q_item in enumerate(queue):
                    if q_item["subject"]==item["subject"] and q_item["topic"]==item["topic"]:
                        del queue[q_idx]
                        break
            if daily_min <= 0:
                break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue, start_date, daily_hours):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date, datetime.min.time())
    while queue:
        daily_min=int(daily_hours*60)
        plan = assign_daily_plan(queue, daily_min)
        day_type="STUDY"
        if streak >= MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest / light revision","time_min":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed Topics","time_min":int(daily_hours*60)}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed Topics","time_min":int(daily_hours*60)}]

        calendar.append({"date":cur_date, "plan":plan, "questions":questions_per_topic, "type":day_type})
        streak+=1 if day_type=="STUDY" else 0
        day_count+=1
        cur_date+=timedelta(days=1)
    return calendar

if selected_subjects and not st.session_state.calendar:
    queue = build_queue()
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours)

# -------------------------------
# TABS: Study Plan & Question Practice
# -------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan","📝 Question Practice"])
COLORS=["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color={s:COLORS[i%len(COLORS)] for i,s in enumerate(selected_subjects)}

# -------------------------------
# STUDY PLAN TAB
# -------------------------------
with tab1:
    st.header("📆 Weekly Study Plan")
    weeks=defaultdict(list)
    for idx, day in enumerate(st.session_state.calendar):
        week_num=idx//7+1
        weeks[week_num].append(day)

    for w_num in sorted(weeks.keys()):
        st.subheader(f"Week {w_num}")
        for day_idx, day in enumerate(weeks[w_num]):
            day_type=str(day.get("type","STUDY")).upper()
            st.markdown(f"**{day['date'].strftime('%A, %d %b %Y')} ({day_type} DAY)**")
            unfinished_today=[]
            for i, p in enumerate(day["plan"]):
                if p["subject"] in ["FREE","REVISION","TEST"]:
                    st.markdown(f"- **{p['subject']} → {p['topic']}**")
                    continue
                key = f"{day['date']}_{i}_{p['topic']}"
                checked = key in st.session_state.completed
                label = f"{p['subject']} → {p['topic']} ({p['time_min']} min / {round(p['time_min']/60,2)} h)"
                if st.checkbox(label, checked, key=f"study_{key}"):
                    st.session_state.completed.add(key)
                else:
                    st.session_state.completed.discard(key)
                    unfinished_today.append(p)
            if st.button(f"Mark Day Completed ({day['date'].strftime('%d %b %Y')})", key=f"complete_{day['date']}"):
                if not unfinished_today:
                    st.success("🎉 All subtopics completed for this day!")
                else:
                    st.warning(f"{len(unfinished_today)} subtopics unfinished. Moving to next day.")
                    next_idx = day_idx + 1
                    if next_idx >= len(weeks[w_num]):
                        next_date = day["date"] + timedelta(days=1)
                        st.session_state.calendar.append({"date":next_date,"plan":[],"questions":questions_per_topic,"type":"STUDY"})
                    st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# -------------------------------
# QUESTION PRACTICE TAB
# -------------------------------
with tab2:
    st.header("📝 Daily Question Practice")
    day_labels=[d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    if day_labels:
        sel=st.selectbox("Select Day", day_labels, key="practice_day_select")
        idx=day_labels.index(sel)
        day=st.session_state.calendar[idx]

        num_questions=st.number_input("Number of questions to practice",1,200,30,key=f"num_questions_{idx}")
        q_type=st.selectbox("Type of questions",["MCQs","Subjective","Long Questions"], key=f"qtype_{idx}")

        for i,p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]:
                continue
            key=f"{sel}_{p['subject']}_{p['topic']}"
            questions=[f"{q_type} Q{q_idx+1} on {p['topic']}" for q_idx in range(num_questions)]
            st.markdown(f"**{p['subject']} → {p['topic']}**")
            for q_idx,q in enumerate(questions):
                st.checkbox(q,key=f"{key}_q{q_idx}", value=st.session_state.practice_done.get(f"{key}_q{q_idx}",False))
                st.session_state.practice_done[f"{key}_q{q_idx}"]=st.session_state.practice_done.get(f"{key}_q{q_idx}",False)

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
