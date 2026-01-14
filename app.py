# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz
import re
from collections import defaultdict
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

st.set_page_config(page_title="Smart Study Planner", layout="wide")

# -------------------------
# DOWNLOAD AND EXTRACT
# -------------------------
if not os.path.exists(ZIP_PATH):
    with st.spinner("⬇️ Downloading syllabus ZIP..."):
        gdown.download(f"https://drive.google.com/uc?id={DRIVE_FILE_ID}", ZIP_PATH, quiet=False)

if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

# -------------------------
# REMOVE GARBAGE
# -------------------------
def is_garbage_line(line):
    l = line.lower()
    keywords = ["annexure","government of india","national medical commission",
                "medical education","ugmeb","neet (ug exam)","date:","sector",
                "dwarka","new delhi","pocket-","phase-","board)","exam)"]
    if any(k in l for k in keywords):
        return True
    if re.match(r"[a-z]-\d+/\d+", l):
        return True
    if re.search(r"\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4}", l):
        return True
    if len(line)>120:
        return True
    return False

# -------------------------
# READ PDF LINES
# -------------------------
def read_pdf_lines(pdf_path):
    doc = fitz.open(pdf_path)
    lines=[]
    for page in doc:
        text=page.get_text()
        for line in text.split("\n"):
            line=line.strip()
            if not line or is_garbage_line(line):
                continue
            lines.append(line)
    return lines

# -------------------------
# DETECT EXAM & BRANCH
# -------------------------
def detect_exam(pdf_path, lines):
    text=" ".join(lines).upper()
    filename=os.path.basename(pdf_path).upper()
    folder=os.path.basename(os.path.dirname(pdf_path)).upper()

    # NEET
    if "NEET" in text or "NEET" in filename or "NEET" in folder:
        return "NEET","UG"

    # IIT JEE
    if "JEE" in text or "IIT" in text:
        if "ADVANCED" in text:
            return "IIT JEE","JEE Advanced"
        return "IIT JEE","JEE Main"

    # GATE
    if "GATE" in text or "GRADUATE APTITUDE TEST" in text:
        branch="General"
        for l in lines:
            l_clean=l.upper().strip()
            if l_clean in ["ME","IN","CE"]:
                branch=l_clean
                break
        return "GATE",branch

    return None,None

# -------------------------
# PARSE SYLLABUS
# -------------------------
def parse_syllabus(root_dir):
    syllabus=defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    remove_subjects=["SECRETARY","PUBLIC NOTICE"]
    for root,_,files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            pdf_path=os.path.join(root,file)
            lines=read_pdf_lines(pdf_path)
            exam,stage=detect_exam(pdf_path,lines)
            if not exam:
                continue
            current_subject=None
            current_topic=None
            for line in lines:
                # SUBJECT
                if line.isupper() and line.replace(" ","").isalpha() and len(line.split())<=5:
                    if line.upper() in remove_subjects:
                        current_subject=None
                        current_topic=None
                        continue
                    current_subject=line.title()
                    current_topic=None
                    continue
                # TOPIC
                if (":" in line or line[:2].isdigit() or line.startswith("-")) and len(line.split())<=12:
                    current_topic=line.replace(":","").strip()
                    if current_subject:
                        syllabus[exam][stage][current_subject][current_topic]=[]
                    continue
                # SUBTOPIC
                if current_subject and current_topic:
                    parts=[p.strip() for p in line.split(",") if len(p.strip())>3]
                    syllabus[exam][stage][current_subject][current_topic].extend(parts)
    return syllabus

# -------------------------
# BUILD SYLLABUS
# -------------------------
syllabus_json=parse_syllabus(EXTRACT_DIR)

if not syllabus_json:
    st.error("No syllabus found.")
    st.stop()

# -------------------------
# SESSION STATE
# -------------------------
if "study_queue" not in st.session_state:
    st.session_state.study_queue=[]  # list of dicts with subtopics and assigned hours
if "remaining_hours" not in st.session_state:
    st.session_state.remaining_hours=0
if "current_day" not in st.session_state:
    st.session_state.current_day=datetime.today()

# -------------------------
# UI
# -------------------------
st.title("📚 Smart Competitive Exam Study Planner")

exam_list=list(syllabus_json.keys())
selected_exam=st.selectbox("Select Exam",exam_list)
stage_list=list(syllabus_json[selected_exam].keys())
selected_stage=st.selectbox("Select Stage/Branch",stage_list)

subjects=list(syllabus_json[selected_exam][selected_stage].keys())
selected_subject=st.selectbox("Select Subject",subjects)

capacity=st.number_input("Available study hours today",min_value=1.0,value=6.0,step=0.5)
time_per_subtopic=st.number_input("Time per subtopic (hours)",min_value=0.1,value=0.5,step=0.1)

# -------------------------
# BUILD STUDY QUEUE
# -------------------------
if st.button("Load Subtopics"):
    st.session_state.study_queue=[]
    st.session_state.remaining_hours=capacity
    st.session_state.current_day=datetime.today()

    for topic, subtopics in syllabus_json[selected_exam][selected_stage][selected_subject].items():
        for sub in subtopics:
            st.session_state.study_queue.append({
                "topic":topic,
                "subtopic":sub,
                "done":False
            })

# -------------------------
# DISPLAY STUDY PLAN
# -------------------------
if st.session_state.study_queue:
    st.subheader(f"📌 Study Plan for {selected_subject} ({selected_exam})")
    remaining_hours=st.session_state.remaining_hours
    today=st.session_state.current_day

    st.write(f"📅 Date: {today.strftime('%Y-%m-%d')}")
    for item in st.session_state.study_queue:
        if remaining_hours<=0:
            break
        if not item["done"]:
            if time_per_subtopic<=remaining_hours:
                st.checkbox(f"{item['topic']} → {item['subtopic']} ({time_per_subtopic}h)",key=item['subtopic'])
                remaining_hours-=time_per_subtopic
            else:
                st.checkbox(f"{item['topic']} → {item['subtopic']} (Not enough time today)",key=item['subtopic'])

    st.session_state.remaining_hours=remaining_hours

    # MARK COMPLETED SUBTOPICS
    for i,item in enumerate(st.session_state.study_queue):
        if st.session_state.get(item['subtopic'],False):
            st.session_state.study_queue[i]['done']=True

    # MOVE TO NEXT DAY IF ALL HOURS USED
    if remaining_hours<=0 or all([s["done"] for s in st.session_state.study_queue]):
        st.session_state.current_day+=timedelta(days=1)
        st.session_state.remaining_hours=capacity
        st.write("⏩ Moving to next day!")

