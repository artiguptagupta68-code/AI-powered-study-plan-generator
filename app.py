import streamlit as st
import zipfile, os, fitz

# ---------------- CONFIG ----------------
ZIP_PATH = r"C:\Users\ASUS\Downloads\plan.zip"
EXTRACT_PATH = "syllabus_data"

# ----------------- EXTRACT ZIP -----------------
def extract_zip():
    if not os.path.exists(EXTRACT_PATH):
        os.makedirs(EXTRACT_PATH, exist_ok=True)
        with zipfile.ZipFile(ZIP_PATH, 'r') as z:
            z.extractall(EXTRACT_PATH)

# ----------------- READ PDFs -----------------
def read_pdf_text(path):
    doc = fitz.open(path)
    text = ""
    for p in doc:
        text += p.get_text()
    # Split by line and remove empty lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines

# ----------------- BUILD SYLLABUS -----------------
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
                
                # Very basic parsing: first line -> topic, rest -> subtopics
                topics = {}
                current_topic = None
                sub_list = []
                for line in lines:
                    # Heuristic: if line ends with "Syllabus" or similar, treat as topic
                    if len(line.split()) <= 6:
                        if current_topic:
                            topics[current_topic] = sub_list
                        current_topic = line
                        sub_list = []
                    else:
                        sub_list.append(line)
                if current_topic:
                    topics[current_topic] = sub_list
                syllabus[exam][subject] = topics
    return syllabus

# ----------------- STATUS TRACKER -----------------
status = {}  # (exam, subject, topic, subtopic) -> pending/completed/delayed

def init_status(syllabus):
    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                for sub in subtopics:
                    status[(exam, subject, topic, sub)] = "pending"

# ----------------- ASSIGN / COMPLETE LOGIC -----------------
def get_pending_subtopics():
    return [k for k,v in status.items() if v=="pending"]

def assign_subtopics(capacity):
    assigned = []
    used = 0
    for k in get_pending_subtopics():
        if used + 2 <= capacity:  # assume 2 hours per subtopic
            assigned.append(k)
            used += 2
        else:
            break
    return assigned

def mark_completed(subtopic_key):
    status[subtopic_key] = "completed"

def add_delay(subtopic_key):
    status[subtopic_key] = "delayed"

def progress_stats():
    total = len(status)
    completed = len([v for v in status.values() if v=="completed"])
    return total, completed

# ----------------- STREAMLIT UI -----------------
st.set_page_config("Adaptive Study Planner", layout="wide")
st.title("📘 Adaptive Study Planner (ZIP PDFs → In-Memory)")

extract_zip()
syllabus = build_syllabus()
init_status(syllabus)

menu = st.sidebar.selectbox("Navigation", ["Daily Planner", "Progress Dashboard"])

# ----------------- DAILY PLANNER -----------------
if menu == "Daily Planner":
    st.header("📅 Today's Study Plan")
    capacity = st.number_input("Your study capacity today (hours)", min_value=1, max_value=16, value=6)
    
    assigned = assign_subtopics(capacity)
    
    st.subheader("📌 Assigned Subtopics")
    for k in assigned:
        exam, subject, topic, sub = k
        col1, col2, col3 = st.columns([4,1,1])
        col1.write(f"{exam} > {subject} > {topic} > {sub}")
        if col2.button("✅ Done", key=f"done{k}"):
            mark_completed(k)
            st.experimental_rerun()
        if col3.button("⏱ Delay", key=f"delay{k}"):
            add_delay(k)
            st.warning("Delay added")

# ----------------- PROGRESS DASHBOARD -----------------
else:
    st.header("📊 Progress Dashboard")
    total, completed = progress_stats()
    st.metric("Total Subtopics", total)
    st.metric("Completed", completed)
    st.progress(completed / total if total else 0)
    
    st.subheader("Pending Subtopics")
    for k in get_pending_subtopics():
        st.write(" > ".join(k))
