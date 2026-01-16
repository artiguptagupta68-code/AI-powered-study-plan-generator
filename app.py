# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re
from collections import deque, defaultdict
from datetime import datetime, timedelta

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
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

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# UTILITY FUNCTIONS
# -------------------------------
def clean_line(line):
    bad = ["annexure","notice","commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line)<200

def read_pdf(file):
    doc = fitz.open(file)
    lines=[]
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

# -------------------------------
# SYLLABUS PARSER
# -------------------------------
def parse_pdf_hierarchy(files):
    """Parse uploaded PDFs into Subject -> Topic -> Subtopics"""
    syllabus = defaultdict(lambda: defaultdict(list))
    
    for f in files:
        lines = read_pdf(f)
        current_subject = None
        current_topic = None
        
        for l in lines:
            l_strip = l.strip()
            # Subject detection: all caps and short line
            if l_strip.isupper() and len(l_strip.split()) <= 5:
                current_subject = l_strip.title()
                current_topic = None
                continue
            
            # Topic detection: line ends with ":" or numbered
            if current_subject and (l_strip.endswith(":") or re.match(r"^\(?[ivxlcdm]+\)|^\d+\.", l_strip.lower())):
                current_topic = l_strip.replace(":", "").strip().title()
                continue
            
            # Subtopics: comma / semicolon separated
            if current_subject and current_topic:
                parts = [p.strip() for p in re.split(r",|;", l_strip) if len(p.strip())>3]
                if parts:
                    syllabus[current_subject][current_topic].extend(parts)
    return dict(syllabus)

def estimate_time_min(subtopic, exam=None):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof|design)", subtopic.lower()))
    base = 10 + words*3 + complexity*8
    weight = {"NEET":1.1,"IIT JEE":1.3,"GATE":1.5}.get(exam,1)
    return int(base*weight)

# -------------------------------
# USER INPUT
# -------------------------------
st.title("📚 AI-Powered Study Planner")

custom_plan = st.checkbox("Create a study plan from uploaded syllabus", key="custom_plan")

syllabus_json = {}
exam_name = ""
subjects = []

if custom_plan:
    exam_name = st.text_input("Enter your Exam Name", key="custom_exam")
    uploaded_files = st.file_uploader(
        f"Upload syllabus PDF(s) for {exam_name}",
        type=["pdf"],
        accept_multiple_files=True
    )
    if uploaded_files:
        syllabus_json = parse_pdf_hierarchy(uploaded_files)
        if not syllabus_json:
            st.error("No topics found in uploaded PDFs.")
            st.stop()
        subjects = list(syllabus_json.keys())
    else:
        st.warning("Please upload at least one PDF.")
        st.stop()
else:
    # Default syllabus from Drive
    exam_name = st.selectbox("Select Exam", ["NEET","IIT JEE","GATE"], key="exam_select")
    syllabus_root = EXTRACT_DIR
    if not os.path.exists(syllabus_root):
        if not os.path.exists(ZIP_PATH):
            gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(EXTRACT_DIR)
    # Parse default syllabus
    def parse_default_syllabus(root, exam):
        data = defaultdict(lambda: defaultdict(list))
        for r,_,files in os.walk(root):
            for f in files:
                if not f.endswith(".pdf"): continue
                lines = read_pdf(os.path.join(r,f))
                if detect_exam(lines)!=exam: continue
                current_subject = None
                current_topic = None
                for l in lines:
                    l_strip = l.strip()
                    if l_strip.isupper() and len(l_strip.split())<=5:
                        current_subject = l_strip.title()
                        current_topic = None
                        continue
                    if current_subject and (l_strip.endswith(":") or re.match(r"^\(?[ivxlcdm]+\)|^\d+\.", l_strip.lower())):
                        current_topic = l_strip.replace(":", "").strip().title()
                        continue
                    if current_subject and current_topic:
                        parts = [p.strip() for p in re.split(r",|;", l_strip) if len(p.strip())>3]
                        if parts:
                            data[current_subject][current_topic].extend(parts)
        return dict(data)
    
    syllabus_json = parse_default_syllabus(syllabus_root, exam_name)
    if not syllabus_json:
        st.error(f"No syllabus found for {exam_name}.")
        st.stop()
    subjects = list(syllabus_json.keys())

selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
questions_per_subtopic = st.number_input("Questions per subtopic per day",5,50,15)
revision_every_n_days = st.number_input("Revision Day Frequency (every N days)",5,30,7)
test_every_n_days = st.number_input("Test Day Frequency (every N days)",7,30,14)

# -------------------------------
# BUILD SUBTOPIC QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t, subtopics in syllabus_json[s].items():
            for stp in subtopics:
                q.append({"subject":s, "topic":t, "subtopic":stp,
                          "time_min":estimate_time_min(stp, exam_name)})
    return q

# -------------------------------
# ROUND-ROBIN ASSIGNMENT
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today = list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues = {s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item = subject_queues[s].popleft()
            alloc = min(item["time_min"], daily_min)
            plan.append({"subject":item["subject"],"topic":item["topic"],"subtopic":item["subtopic"],"time_min":alloc})
            daily_min -= alloc
            item["time_min"] -= alloc
            if item["time_min"] <= 0:
                for idx,q_item in enumerate(queue):
                    if q_item["subject"]==item["subject"] and q_item["topic"]==item["topic"] and q_item["subtopic"]==item["subtopic"]:
                        del queue[idx]
                        break
            if daily_min<=0: break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue, start_date, daily_hours):
    calendar=[]
    streak=0
    day_count=0
    cur_date = datetime.combine(start_date, datetime.min.time())
    while queue:
        daily_min = int(daily_hours*60)
        plan = assign_daily_plan(queue, daily_min)
        day_type="STUDY"
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Rest / light revision","time_min":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"Revise Completed Subtopics","time_min=int(daily_hours*60)}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"Test Completed Subtopics","time_min=int(daily_hours*60)}]
        calendar.append({"date":cur_date, "plan":plan, "questions":questions_per_subtopic, "type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count +=1
        cur_date += timedelta(days=1)
    return calendar

if selected_subjects and not st.session_state.calendar:
    queue = build_queue()
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours)

# -------------------------------
# TABS
# -------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan","📝 Question Practice"])
COLORS = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color={s:COLORS[i%len(COLORS)] for i,s in enumerate(selected_subjects)}

# -------------------------------
# STUDY PLAN TAB
# -------------------------------
with tab1:
    st.header("📆 Weekly Study Plan")
    weeks=defaultdict(list)
    for idx,day in enumerate(st.session_state.calendar):
        week_num = idx//7 + 1
        weeks[week_num].append(day)

    for w_num in sorted(weeks.keys()):
        st.subheader(f"Week {w_num}")
        for day_idx, day in enumerate(weeks[w_num]):
            day_type=str(day.get("type","STUDY")).upper()
            st.markdown(f"**{day['date'].strftime('%A, %d %b %Y')} ({day_type} DAY)**")
            unfinished_today=[]
            for i,p in enumerate(day["plan"]):
                if p["subject"] in ["FREE","REVISION","TEST"]:
                    st.markdown(f"- **{p['subject']} → {p['subtopic']}**")
                    continue
                key = f"{day['date']}_{i}_{p['subtopic']}"
                checked = key in st.session_state.completed
                label = f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['time_min']} min)"
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
                    next_idx=day_idx+1
                    if next_idx>=len(weeks[w_num]):
                        next_date = day["date"] + timedelta(days=1)
                        st.session_state.calendar.append({"date":next_date,"plan":[],"questions":questions_per_subtopic,"type":"STUDY"})
                    st.session_state.calendar[next_idx]["plan"] = unfinished_today + st.session_state.calendar[next_idx]["plan"]

# -------------------------------
# QUESTION PRACTICE TAB
# -------------------------------
with tab2:
    st.header("📝 Daily Question Practice")
    day_labels = [d["date"].strftime("%A, %d %b %Y") for d in st.session_state.calendar]
    if day_labels:
        sel = st.selectbox("Select Day", day_labels, key="practice_day_select")
        idx = day_labels.index(sel)
        day = st.session_state.calendar[idx]

        num_questions = st.number_input("Number of questions to practice",1,200,15,key=f"num_questions_{idx}")
        q_type = st.selectbox("Type of questions", ["MCQs","Subjective","Long Questions"], key=f"qtype_{idx}")

        for i,p in enumerate(day["plan"]):
            if p["subject"] in ["FREE","REVISION","TEST"]: continue
            key = f"{sel}_{p['subject']}_{p['topic']}_{p['subtopic']}"
            questions = [f"{q_type} Q{q_idx+1} on {p['subtopic']}" for q_idx in range(num_questions)]
            st.markdown(f"**{p['subject']} → {p['topic']} → {p['subtopic']}**")
            for q_idx,q in enumerate(questions):
                st.checkbox(q,key=f"{key}_q{q_idx}", value=st.session_state.practice_done.get(f"{key}_q{q_idx}",False))
                st.session_state.practice_done[f"{key}_q{q_idx}"] = st.session_state.practice_done.get(f"{key}_q{q_idx}",False)

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
