import streamlit as st
import zipfile, os, requests, fitz
from collections import defaultdict
from datetime import datetime, timedelta

# -------------------------------
# 1) Streamlit: Google Drive ZIP input
# -------------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")

drive_link = st.text_input("Enter Google Drive file link for syllabus ZIP:")
local_zip = "syllabus.zip"
extract_dir = "syllabus_data"

syllabus = {}
topic_status = {}

# -------------------------------
# 2) Functions
# -------------------------------
def read_pdf_text(pdf_path):
    """Read text from a PDF using fitz"""
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        for line in page.get_text("text").split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines

def extract_syllabus_from_pdfs(root_dir):
    """Parse PDFs into Exam -> Subject -> Topic -> Subtopic hierarchy"""
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    # Known subjects for filtering
    known_subjects_keywords = [
        "Mathematics", "Engineering", "Geology", "Physics", "Chemistry",
        "General Studies", "Economics", "Polity", "CS", "Computer", "Science"
    ]
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(root, file)
            lines = read_pdf_text(pdf_path)

            # Detect Exam Name
            exam = None
            for line in lines[:10]:
                l = line.upper()
                if "GATE" in l:
                    exam = "GATE 2026"
                    break
                elif "SSC" in l:
                    exam = "SSC"
                    break
                elif "UPSC" in l:
                    exam = "UPSC"
                    break
            if not exam:
                exam = "Unknown Exam"

            current_subject = None
            current_topic = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Subject heuristic
                if (
                    line.isupper() and
                    len(line.split()) <= 5 and
                    line.replace(" ", "").isalpha() and
                    any(kw.upper() in line.upper() for kw in known_subjects_keywords)
                ):
                    current_subject = line.title()
                    continue

                # Topic heuristic
                if (len(line.split()) <= 6 and ":" in line) or any(c.isdigit() for c in line[:3]):
                    current_topic = line
                    if not current_subject:
                        current_subject = "General"
                    syllabus[exam][current_subject][current_topic] = []
                    continue

                # Subtopic
                if current_topic:
                    if not current_subject:
                        current_subject = "General"
                    syllabus[exam][current_subject][current_topic].append(line)
    return syllabus

def calc_estimated_time(syllabus):
    """Calculate estimated & practice time for each topic"""
    keyword_multiplier = {"advanced":1.5, "complex":1.3, "important":1.2}
    topic_status = {}
    for exam, subjects in syllabus.items():
        for subject, topics in subjects.items():
            for topic, subtopics in topics.items():
                num_words = sum(len(s.split()) for s in subtopics) + len(topic.split())
                base_time = num_words * 0.05  # 0.05h per word
                mult = 1.0
                for kw, m in keyword_multiplier.items():
                    if kw in topic.lower():
                        mult *= m
                est = round(base_time * mult, 2)
                practice = round(est * 0.3, 2)
                topic_status[(exam, subject, topic)] = {
                    "estimated_time": est,
                    "practice_time": practice,
                    "revision_time": 1,
                    "status": "pending",
                    "last_studied": None,
                    "next_revision": []
                }
    return topic_status

# -------------------------------
# 3) Download & Extract ZIP
# -------------------------------
if drive_link:
    try:
        file_id = drive_link.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        os.makedirs(extract_dir, exist_ok=True)

        if not os.path.exists(local_zip):
            response = requests.get(download_url)
            with open(local_zip, "wb") as f:
                f.write(response.content)
            st.success("✅ Syllabus ZIP downloaded successfully!")
        else:
            st.info("ℹ️ ZIP already exists, using the local file.")

        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        st.success(f"📂 ZIP extracted to {extract_dir}")

        # -------------------------------
        # 4) Parse PDFs and calculate times
        # -------------------------------
        syllabus = extract_syllabus_from_pdfs(extract_dir)
        st.success("📚 Syllabus parsed successfully!")

        topic_status = calc_estimated_time(syllabus)
        st.success("🕒 Estimated times calculated for topics!")

    except Exception as e:
        st.error(f"❌ Error downloading/extracting/parsing ZIP: {e}")

# -------------------------------
# 5) Streamlit Daily Planner
# -------------------------------
if topic_status:
    st.subheader("📌 Daily Planner")
    capacity = st.number_input("Enter study capacity today (hours):", min_value=1.0, value=6.0, step=0.5)

    all_subjects = sorted({sub for _, sub, _ in topic_status})
    selected_subjects = st.multiselect("Select subjects to study today:", all_subjects)

    if st.button("Assign Topics"):
        assigned = []
        used = 0
        pending = [k for k,v in topic_status.items() if v['status']=='pending' and k[1] in selected_subjects]
        for k in pending:
            est_time = topic_status[k]['estimated_time'] + topic_status[k]['practice_time']
            if used + est_time <= capacity:
                assigned.append(k)
                used += est_time
            else:
                break

        if assigned:
            st.write("📌 **Topics assigned today:**")
            for k in assigned:
                st.write(f"- {k[0]} > {k[1]} > {k[2]} | Est: {topic_status[k]['estimated_time']}h, Practice: {topic_status[k]['practice_time']}h")

            for k in assigned:
                completed = st.checkbox(f"Completed: {k[0]} > {k[1]} > {k[2]}", key=str(k))
                if completed:
                    topic_status[k]['status'] = 'completed'
                    topic_status[k]['last_studied'] = datetime.now()
                    topic_status[k]['next_revision'] = [
                        datetime.now() + timedelta(days=1),
                        datetime.now() + timedelta(days=3),
                        datetime.now() + timedelta(days=7)
                    ]
        else:
            st.info("No topics fit your capacity today or all topics are done!")

        # Progress
        total = len(topic_status)
        completed_count = len([v for v in topic_status.values() if v['status']=='completed'])
        pending_count = len([v for v in topic_status.values() if v['status']=='pending'])
        st.subheader("📊 Progress")
        st.write(f"Total: {total} | Completed: {completed_count} | Pending: {pending_count}")

        # Revisions due today
        now = datetime.now()
        due = []
        for k, info in topic_status.items():
            if info['status']=='completed':
                for rev in info['next_revision']:
                    if now >= rev:
                        due.append(k)
                        break
        if due:
            st.subheader("🕑 Topics due for revision today:")
            for k in due:
                st.write(f"- {k[0]} > {k[1]} > {k[2]}")
