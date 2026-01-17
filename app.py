# app.py
import streamlit as st
import os, zipfile, gdown, fitz, json, re, io
from collections import deque, defaultdict
from datetime import datetime, timedelta
from PIL import Image
import pytesseract

# -------------------------------
# CONFIG
# -------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"
STATE_FILE = "progress.json"
MAX_CONTINUOUS_DAYS = 6

st.set_page_config("📚 AI Study Planner", layout="wide")
st.title("📚 AI Study Planner")

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
    with open(STATE_FILE,"r") as f:
        st.session_state.completed = set(json.load(f))

# -------------------------------
# PDF READER
# -------------------------------
def clean_line(line):
    bad = ["annexure","notice","commission"]
    return line.strip() and not any(b in line.lower() for b in bad) and len(line)<120

def read_pdf(file):
    """Read PDF using PyMuPDF. If empty, fallback to OCR."""
    if isinstance(file,str):
        doc = fitz.open(file)
    else:
        doc = fitz.open(stream=file.read(), filetype="pdf")
    lines=[]
    for page in doc:
        text = page.get_text()
        if text.strip():
            lines.extend([l.strip() for l in text.split("\n") if clean_line(l)])
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            lines.extend([l.strip() for l in ocr_text.split("\n") if clean_line(l)])
    return lines

# -------------------------------
# SYLLABUS PARSER
# -------------------------------
def parse_pdf_hierarchy(files, forced_exam=None):
    """
    Parse PDFs into hierarchy: exam -> subject -> topic -> subtopic
    If forced_exam is provided, all PDFs are assigned to that exam
    """
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for f in files:
        lines = read_pdf(f)
        exam_name = forced_exam if forced_exam else "Custom Exam"
        current_subject = None
        current_topic = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Subject: all caps, <=6 words
            if line.isupper() and len(line.split())<=6:
                current_subject = line.title()
                current_topic = None
            # Topic: capitalized, <=10 words
            elif line[0].isupper() and len(line.split())<=10:
                current_topic = line
            # Subtopic
            else:
                if current_subject and current_topic:
                    data[exam_name][current_subject][current_topic].append(line)
                elif current_subject:
                    data[exam_name][current_subject]["General"].append(line)
                else:
                    data[exam_name]["General"]["General"].append(line)
    return dict(data)

def estimate_time(subtopic):
    words = len(subtopic.split())
    complexity = len(re.findall(r"(theorem|numerical|derivation|proof)", subtopic.lower()))
    return max(15, words*3 + complexity*10)

# -------------------------------
# USER INPUT: EXAM & SYLLABUS
# -------------------------------
custom_plan = st.checkbox("Create a study plan of my choice / upload syllabus")

if custom_plan:
    exam_name = st.text_input("Enter your Exam Name", key="custom_exam")
    uploaded_files = st.file_uploader(f"Upload syllabus PDF(s) for {exam_name}", type=["pdf"], accept_multiple_files=True)
    if not uploaded_files:
        st.warning("Please upload at least one PDF.")
        st.stop()
    syllabus_dict = parse_pdf_hierarchy(uploaded_files, forced_exam=exam_name)
    if not syllabus_dict or not syllabus_dict.get(exam_name):
        st.error("No valid syllabus found in uploaded PDFs.")
        st.stop()
else:
    exam_name = st.selectbox("Select Exam", ["NEET","GATE","IIT JEE"])
    syllabus_source = st.radio("Syllabus Source", ["Use default syllabus","Upload PDF(s)"])
    syllabus_root = EXTRACT_DIR
    # Upload PDFs
    if syllabus_source=="Upload PDF(s)":
        uploaded_files = st.file_uploader(f"Upload syllabus PDFs for {exam_name}", type=["pdf"], accept_multiple_files=True)
        if uploaded_files:
            os.makedirs(syllabus_root, exist_ok=True)
            for f in uploaded_files:
                with open(os.path.join(syllabus_root,f.name),"wb") as out:
                    out.write(f.read())
            st.success(f"{len(uploaded_files)} files uploaded successfully")
    # Use default
    if syllabus_source=="Use default syllabus":
        if not os.path.exists(syllabus_root):
            if not os.path.exists(ZIP_PATH):
                gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH) as z:
                z.extractall(EXTRACT_DIR)
    # Parse all PDFs in syllabus_root
    all_files = [os.path.join(syllabus_root,f) for f in os.listdir(syllabus_root) if f.lower().endswith(".pdf")]
    syllabus_dict = parse_pdf_hierarchy(all_files, forced_exam=exam_name)
    if not syllabus_dict or not syllabus_dict.get(exam_name):
        st.error(f"No syllabus found for {exam_name}. Check default PDFs or upload manually.")
        st.stop()

syllabus_json = syllabus_dict[exam_name]
subjects = list(syllabus_json.keys())
selected_subjects = st.multiselect("Select Subjects", subjects, default=subjects)
start_date = st.date_input("Start Date", datetime.today())
daily_hours = st.number_input("Daily study hours",1.0,12.0,6.0)
questions_per_topic = st.number_input("Questions per topic per day",10,200,30)
revision_every_n_days = st.number_input("Revision every N days",5,30,7)
test_every_n_days = st.number_input("Test every N days",7,30,14)

# -------------------------------
# BUILD QUEUE
# -------------------------------
def build_queue():
    q = deque()
    for s in selected_subjects:
        for t, subtopics in syllabus_json[s].items():
            for stp in subtopics:
                q.append({"subject":s,"topic":t,"subtopic":stp,"time_min":estimate_time(stp)})
    return q

# -------------------------------
# ASSIGN DAILY PLAN
# -------------------------------
def assign_daily_plan(queue, daily_min):
    plan=[]
    subjects_today=list({item["subject"] for item in queue})
    if not subjects_today: return plan
    subject_queues={s:deque([item for item in queue if item["subject"]==s]) for s in subjects_today}
    while daily_min>0 and any(subject_queues.values()):
        for s in subjects_today:
            if not subject_queues[s]: continue
            item=subject_queues[s].popleft()
            alloc=min(item["time_min"],daily_min)
            plan.append({"subject":item["subject"],"topic":item["topic"],"subtopic":item["subtopic"],"time_min":alloc})
            daily_min -= alloc
            item["time_min"] -= alloc
            if item["time_min"]<=0:
                for idx,q_item in enumerate(queue):
                    if q_item==item:
                        del queue[idx]
                        break
            if daily_min<=0:
                break
    return plan

# -------------------------------
# GENERATE CALENDAR
# -------------------------------
def generate_calendar(queue,start_date,daily_hours):
    calendar=[]
    streak=0
    day_count=0
    cur_date=datetime.combine(start_date,datetime.min.time())
    daily_min=int(daily_hours*60)
    while queue:
        plan=assign_daily_plan(queue,daily_min)
        day_type="STUDY"
        if streak>=MAX_CONTINUOUS_DAYS:
            day_type="FREE"
            plan=[{"subject":"FREE","topic":"Rest / light revision","subtopic":"Relax","time_min":0}]
            streak=0
        elif day_count%revision_every_n_days==0 and day_count!=0:
            day_type="REVISION"
            plan=[{"subject":"REVISION","topic":"Revise Completed","subtopic":"All completed topics","time_min":daily_min}]
        elif day_count%test_every_n_days==0 and day_count!=0:
            day_type="TEST"
            plan=[{"subject":"TEST","topic":"Test Completed","subtopic":"All completed topics","time_min":daily_min}]
        calendar.append({"date":cur_date,"plan":plan,"questions":questions_per_topic,"type":day_type})
        streak += 1 if day_type=="STUDY" else 0
        day_count += 1
        cur_date += timedelta(days=1)
    return calendar

# -------------------------------
# GENERATE CALENDAR IF NOT EXISTS
# -------------------------------
if selected_subjects and not st.session_state.calendar:
    queue = build_queue()
    st.session_state.calendar = generate_calendar(queue, start_date, daily_hours)

# -------------------------------
# TABS: Study Plan & Question Practice
# -------------------------------
tab1, tab2 = st.tabs(["📖 Study Plan","📝 Question Practice"])

# -------------------------------
# STUDY PLAN TAB
# -------------------------------
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
                label=f"{p['subject']} → {p['topic']} → {p['subtopic']} ({p['time_min']} min)"
                if st.checkbox(label,checked,key=f"study_{key}"):
                    st.session_state.completed.add(key)
                else:
                    st.session_state.completed.discard(key)
                    unfinished_today.append(p)
            if st.button(f"Mark Day Completed ({day['date'].strftime('%d %b %Y')})", key=f"complete_{day['date']}"):
                if not unfinished_today:
                    st.success("🎉 All subtopics completed for this day!")
                else:
                    st.warning(f"{len(unfinished_today)} subtopics unfinished. Carrying forward to next day.")
                    next_idx=day_idx+1
                    if next_idx>=len(st.session_state.calendar):
                        next_date=day["date"]+timedelta(days=1)
                        st.session_state.calendar.append({"date":next_date,"plan":[],"questions":questions_per_topic,"type":"STUDY"})
                    st.session_state.calendar[next_idx]["plan"]=unfinished_today+st.session_state.calendar[next_idx]["plan"]

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
            key=f"{sel}_{p['subject']}_{p['topic']}_{p['subtopic']}"
            questions=[f"{q_type} Q{q_idx+1} on {p['subtopic']}" for q_idx in range(num_questions)]
            st.markdown(f"**{p['subject']} → {p['topic']} → {p['subtopic']}**")
            for q_idx,q in enumerate(questions):
                st.checkbox(q,key=f"{key}_q{q_idx}", value=st.session_state.practice_done.get(f"{key}_q{q_idx}",False))
                st.session_state.practice_done[f"{key}_q{q_idx}"]=st.session_state.practice_done.get(f"{key}_q{q_idx}",False)

# -------------------------------
# SAVE STATE
# -------------------------------
with open(STATE_FILE,"w") as f:
    json.dump(list(st.session_state.completed),f)
