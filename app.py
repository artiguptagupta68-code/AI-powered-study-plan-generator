import streamlit as st
import zipfile, os
import fitz  # PyMuPDF

# ---------------- CONFIG ----------------
EXTRACT_PATH = "syllabus_data"
os.makedirs(EXTRACT_PATH, exist_ok=True)

# ---------------- PDF READING ----------------
def read_pdf_text(path):
    """Read PDF and return lines as list"""
    doc = fitz.open(path)
    lines = []
    for page in doc:
        for line in page.get_text("text").split("\n"):
            if line.strip():
                lines.append(line.strip())
    return lines

# ---------------- BUILD SYLLABUS ----------------
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
                
                # Simple parsing: lines of length <=6 -> topic, rest -> subtopics
                topics = {}
                current_topic = None
                sub_list = []
                for line in lines:
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

# ---------------- STATUS TRACKER ----------------
status = {}

def init_status(syllabus):
    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                for sub in subtopics:
                    status[(exam, subject, topic, sub)] = "pending"

# ---------------- LOGIC ----------------
def get_pending_subtopics():
    return [k for k,v in status.items() if v=="pending"]

def assign_subtopics(capacity):
    assigned = []
    used = 0
    for k in get_pending_subtopics():
        if used + 2 <= capacity:  # each subtopic ~2 hours
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

# ---------------- STREAMLIT UI ----------------
st.set_page_config("Adaptive Study Planner", layout="wide")
st.title("📘 Adaptive Study Planner (ZIP PDF Upload)")

menu = st.sidebar.selectbox("Navigation", ["Upload Syllabus ZIP", "Daily Planner", "Progress Dashboard"])

# ---------------- UPLOAD ZIP ----------------
if menu == "Upload Syllabus ZIP":
    st.header("📂 Upload your syllabus ZIP")
    uploaded_file = st.file_uploader("Upload ZIP file containing PDFs", type=["zip"])
    if uploaded_file is not None:
        zip_path = os.path.join(EXTRACT_PATH, "plan.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(EXTRACT_PATH)
        st.success("ZIP extracted successfully!")
        st.info("Go to Daily Planner to generate study plan")
        
# ---------------- DAILY PLANNER ----------------
elif menu == "Daily Planner":
    st.header("📅 Today's Study Plan")
    syllabus = build_syllabus()
    init_status(syllabus)
    
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

# ---------------- PROGRESS DASHBOARD ----------------
else:
    st.header("📊 Progress Dashboard")
    total, completed = progress_stats()
    st.metric("Total Subtopics", total)
    st.metric("Completed", completed)
    st.progress(completed / total if total else 0)
    
    st.subheader("Pending Subtopics")
    for k in get_pending_subtopics():
        st.write(" > ".join(k))
