# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import json, re, io, os, zipfile, gdown
from collections import defaultdict, deque
from datetime import datetime, timedelta

# Optional OCR
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="📚 AI Study Planner", layout="wide")
st.title("📚 AI Study Planner")

STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"

# ---------------------------
# SESSION STATE
# ---------------------------
if "completed" not in st.session_state:
    st.session_state.completed = set()
if "calendar" not in st.session_state:
    st.session_state.calendar = []
if "practice_done" not in st.session_state:
    st.session_state.practice_done = {}

if os.path.exists(STATE_FILE):
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# ---------------------------
# PDF READER (TEXT + optional OCR)
# ---------------------------
def read_pdf(file_or_path):
    if isinstance(file_or_path, str):
        doc = fitz.open(file_or_path)
    else:
        doc = fitz.open(stream=file_or_path.read(), filetype="pdf")

    lines = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            page_lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 2]
            lines.extend(page_lines)
        elif OCR_AVAILABLE:
            # OCR fallback only if pytesseract is installed
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            page_lines = [l.strip() for l in ocr_text.split("\n") if len(l.strip()) > 2]
            lines.extend(page_lines)
    return lines

# ---------------------------
# SYLLABUS PARSING
# ---------------------------
def pdf_to_syllabus_json(files):
    syllabus = defaultdict(lambda: defaultdict(list))
    for f in files:
        lines = read_pdf(f)
        current_subject = None
        current_topic = None
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.isupper() and len(line.split()) <= 6 and re.sub(r"[^A-Z]", "", line):
                current_subject = line.title()
                current_topic = None
            elif line[0].isupper() and len(line.split()) <= 10:
                current_topic = line
            else:
                if current_subject and current_topic:
                    syllabus[current_subject][current_topic].append(line)
                elif current_subject:
                    syllabus[current_subject]["General"].append(line)
                else:
                    syllabus["General"]["General"].append(line)
    return dict(syllabus)

def parse_uploaded_syllabus(files):
    """Flat list parser for custom uploaded PDFs"""
    data = defaultdict(list)
    for f in files:
        lines = read_pdf(f)
        subject = None
        for l in lines:
            if l.isupper() and l.replace(" ","").isalpha():
                subject = l.title()
            elif subject:
                parts = [p.strip() for p in l.split(",") if len(p.strip())>3]
                data[subject].extend(parts)
    return data

def normalize_syllabus(syllabus_json):
    normalized = {}
    for subject, topics in syllabus_json.items():
        if isinstance(topics, list):
            normalized[subject] = {t: [t] for t in topics}
        elif isinstance(topics, dict):
            normalized[subject] = {t: (v if isinstance(v,list) else [v]) for t,v in topics.items()}
        else:
            normalized[subject] = {"General": [str(topics)]}
    return normalized

# ---------------------------
# TIME ESTIMATION
# ---------------------------
def estimate_time(text, exam=None):
    words = len(text.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", text.lower()))
    base = 15 + words*3 + complexity*10
    weight = {"NEET":1.1,"IIT JEE":1.3,"GATE":1.5}.get(exam,1)
    return int(base*weight)

# ---------------------------
# QUEUE BUILDING
# ---------------------------
def build_queue(syllabus_json, selected_subjects, exam=None):
    q = deque()
    for subject in selected_subjects:
        for topic, subtopics in syllabus_json[subject].items():
            for subtopic in subtopics:
                q.append({
                    "subject": subject,
                    "topic": topic,
                    "subtopic": subtopic,
                    "time": estimate_time(subtopic, exam)
                })
    return q

# ---------------------------
# ROUND-ROBIN ASSIGNMENT
# ---------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time"], daily_min)
            plan.append({"subject":item["subject"], "topic":item["topic"], "subtopic":item["subtopic"], "minutes":alloc})
            daily_min -= alloc
            item["time"] -= alloc
            if item["time"] <= 0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0:
                break
    return plan

# ---------------------------
# GENERATE CALENDAR
# ---------------------------
def generate_calendar(queue, start_date, daily_hours, revision_every_n_days=7, test_every_n_days=14, questions_per_topic=30):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date, datetime.min.time())
    daily_min=int(daily_hours*60)
    while queue:
        day_type="STUDY"
        plan=assign_daily_plan(queue, daily_min)
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest","subtopic":"Relax / Light revision","minutes":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics", "minutes":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics", "minutes":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"type":day_type,"questions":questions_per_topic})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# ---------------------------
# STEP 1: SYLLABUS INPUT
# ---------------------------
custom_plan = st.checkbox("Create custom syllabus / upload PDF(s)")
syllabus_json = {}
exam_name = None
if custom_plan:
    exam_name = st.text_input("Enter your Exam Name", key="custom_exam")
    uploaded_files = st.file_uploader(f"Upload syllabus PDF(s) for {exam_name}", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        syllabus_json = pdf_to_syllabus_json(uploaded_files)
else:
    # Default syllabus from EXTRACT_DIR
    if not os.path.exists(EXTRACT_DIR):
        os.makedirs(EXTRACT_DIR)
    files = [os.path.join(EXTRACT_DIR,f) for f in os.listdir(EXTRACT_DIR) if f.endswith(".pdf")]
    if files:
        syllabus_json = pdf_to_syllabus_json(files)

if not syllabus_json:
    st.error("❌ No syllabus found. Upload at least one PDF.")
    st.stop()

# Confirm / edit syllabus
st.subheader("📌 Extracted Syllabus (JSON)")
json_text = st.text_area("Edit subjects/topics/subtopics if needed",
                         value=json.dumps(syllabus_json, indent=2, ensure_ascii=False), height=400)
try:
    syllabus_json = json.loads(json_text)
except:
    st.error("Invalid JSON")
    st.stop()

confirm = st.checkbox("✅ Confirm syllabus")
if not confirm:
    st.warning("Confirm the syllabus to continue.")
    st.stop()

syllabus_json = normalize_syllabus(syllabus_json)
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select subjects", subjects, default=subjects)
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
revision_every_n_days = st.number_input("Revision every N days",5,30,7)
test_every_n_days = st.number_input("Test every N days",7,30,14)
questions_per_topic = st.number_input("Questions per topic per day",10,200,30)

# ---------------------------
# GENERATE CALENDAR
# ---------------------------
if st.button("🚀 Generate Study Plan"):
    queue = build_queue(syllabus_json, selected_subjects, exam_name)
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours, revision_every_n_days, test_every_n_days, questions_per_topic)
    st.success("✅ Study plan generated!")

# ---------------------------
# TABS: Study Plan & Question Practice
# ---------------------------
tab1, tab2 = st.tabs(["📖 Study Plan","📝 Question Practice"])
COLORS=["#4CAF50","#2196F3","#FF9800","#9C27B0","#009688","#E91E63"]
subject_color={s:COLORS[i%len(COLORS)] for i,s in enumerate(selected_subjects)}

with tab1:
    st.header("📆 Weekly Study Plan")
    weeks=defaultdict(list)
    for idx,day in enumerate(st.session_state.calendar):
        week_num=idx//7+1
        weeks[week_num].append(day)

    for w_num in sorted(weeks.keys()):
        st.subheader(f"Week {w_num}")
        for day_idx, day in enumerate(weeks[w_num]):
            day_type=str(day.get("type","STUDY")).upper()
            st.markdown(f"**{day['date'].strftime('%A, %d %b %Y')} ({day_type} DAY)**")
            unfinished_today=[]
            for i,p in enumerate(day["plan"]):
                if p["subject"] in ["FREE","REVISION","TEST"]:
                    st.markdown(f"- **{p['subject']} → {p['topic']}**")
                    continue
                key=f"{day['date']}_{i}_{p['subtopic']}"
                checked=key in st.session_state.completed
                label=f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['minutes']} min / {round(p['minutes']/60,2)} h)"
                if st.checkbox(label,checked,key=f"study_{key}"):
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
                        next_date=day["date"]+timedelta(days=1)
                        st.session_state.calendar.append({"date":next_date,"plan":[],"questions":questions_per_topic,"type":"STUDY"})
                    st.session_state.calendar[next_idx]["plan"]=unfinished_today+st.session_state.calendar[next_idx]["plan"]

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

# ---------------------------
# SAVE STATE
# ---------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
