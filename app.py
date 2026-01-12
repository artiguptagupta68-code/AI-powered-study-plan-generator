import streamlit as st
import zipfile, os
import fitz
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
EXTRACT_PATH = "syllabus_data"
os.makedirs(EXTRACT_PATH, exist_ok=True)

# ---------------- PDF READING ----------------
def read_pdf_text(path):
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for line in page.get_text("text").split("\n"):
            if line.strip():
                lines.append(line.strip())
    return lines

# ---------------- BUILD SYLLABUS (TOPICS ONLY) ----------------
def build_syllabus():
    syllabus = {}
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".pdf"):
                exam = os.path.basename(root)
                if exam not in syllabus:
                    syllabus[exam] = {}
                subject = os.path.splitext(file)[0]
                lines = read_pdf_text(os.path.join(root, file))
                
                # Only capture topics (line with colon or short lines)
                topics = []
                for line in lines:
                    if ':' in line or len(line.split()) <= 6:
                        topics.append(line)
                syllabus[exam][subject] = topics
    return syllabus

# ---------------- STATUS TRACKER ----------------
topic_data = {}  # key: (exam, subject, topic)

def init_status(syllabus):
    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic in topics:
                topic_data[(exam, subject, topic)] = {
                    "status": "pending",
                    "actual_time": 2,       # placeholder, adaptive later
                    "practice_time": 1,
                    "revision_time": 1,
                    "last_studied": None,
                    "next_revision": None
                }

# ---------------- DAILY PLANNER LOGIC ----------------
def get_pending_topics(selected_subjects):
    return [k for k,v in topic_data.items() if k[1] in selected_subjects and v["status"]=="pending"]

def assign_daily_topics(capacity, selected_subjects):
    assigned = []
    used = 0
    for k in get_pending_topics(selected_subjects):
        time_needed = topic_data[k]["actual_time"] + topic_data[k]["practice_time"]
        if used + time_needed <= capacity:
            assigned.append(k)
            used += time_needed
        else:
            break
    return assigned

def mark_completed(k):
    topic_data[k]["status"] = "completed"
    topic_data[k]["last_studied"] = datetime.now()
    topic_data[k]["next_revision"] = [
        datetime.now() + timedelta(days=1),
        datetime.now() + timedelta(days=3),
        datetime.now() + timedelta(days=7)
    ]

def add_delay(k):
    topic_data[k]["status"] = "delayed"

def get_due_revisions():
    now = datetime.now()
    due = []
    for k, v in topic_data.items():
        if v["status"]=="completed" and v["next_revision"]:
            for rev in v["next_revision"]:
                if now >= rev:
                    due.append(k)
                    break
    return due

def progress_stats():
    total = len(topic_data)
    completed = len([v for v in topic_data.values() if v["status"]=="completed"])
    return total, completed

# ---------------- STREAMLIT UI ----------------
st.set_page_config("Adaptive Study Planner", layout="wide")
st.title("📘 Adaptive Study Planner (Topics Only)")

menu = st.sidebar.selectbox("Navigation", ["Upload Syllabus ZIP", "Daily Planner", "Progress Dashboard"])

# ---------------- UPLOAD ZIP ----------------
if menu == "Upload Syllabus ZIP":
    st.header("📂 Upload your syllabus ZIP")
    uploaded_file = st.file_uploader("Upload ZIP file containing PDFs", type=["zip"])
    if uploaded_file is not None:
        zip_path = os.path.join(EXTRACT_PATH, "plan.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(EXTRACT_PATH)
        st.success("ZIP extracted successfully! Go to Daily Planner to generate study plan.")

# ---------------- DAILY PLANNER ----------------
elif menu == "Daily Planner":
    syllabus = build_syllabus()
    if not topic_data:
        init_status(syllabus)
    
    st.header("📅 Today's Study Plan")
    
    # Parallel subjects selection
    all_subjects = []
    for exam, subjects in syllabus.items():
        all_subjects.extend(subjects.keys())
    selected_subjects = st.multiselect("Select subjects to study today", all_subjects, default=all_subjects)
    
    capacity = st.number_input("Your study capacity today (hours)", min_value=1, max_value=16, value=6)
    
    # Assign topics + revisions
    assigned = assign_daily_topics(capacity, selected_subjects)
    due_revisions = get_due_revisions()
    
    st.subheader("📌 Topics Assigned Today")
    for k in assigned:
        exam, subject, topic = k
        col1, col2, col3 = st.columns([4,1,1])
        col1.write(f"{exam} > {subject} > {topic}")
        if col2.button("✅ Done", key=f"done{k}"):
            mark_completed(k)
            st.experimental_rerun()
        if col3.button("⏱ Delay", key=f"delay{k}"):
            add_delay(k)
            st.warning("Delay added")
    
    if due_revisions:
        st.subheader("🕑 Due Revisions")
        for k in due_revisions:
            exam, subject, topic = k
            st.info(f"{exam} > {subject} > {topic} (Revision Due)")

# ---------------- PROGRESS DASHBOARD ----------------
else:
    st.header("📊 Progress Dashboard")
    total, completed = progress_stats()
    st.metric("Total Topics", total)
    st.metric("Completed", completed)
    st.progress(completed / total if total else 0)
    
    st.subheader("Pending Topics")
    for k, v in topic_data.items():
        if v["status"]=="pending":
            st.write(" > ".join(k))
    
    st.subheader("Delayed Topics")
    for k, v in topic_data.items():
        if v["status"]=="delayed":
            st.warning(" > ".join(k))
