import fitz  # PyMuPDF
from collections import defaultdict
import streamlit as st
import zipfile, os, requests

# -------------------------------
# 1) Streamlit: Google Drive ZIP link input
# -------------------------------
st.title("📚 Adaptive Study Planner for UPSC / GATE / SSC")
drive_link = st.text_input("Enter Google Drive file link for syllabus ZIP:")

local_zip = "syllabus.zip"
extract_dir = "syllabus_data"

if drive_link:
    try:
        # Extract file_id from Google Drive link
        file_id = drive_link.split("/d/")[1].split("/")[0]
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # Create extraction folder if not exists
        os.makedirs(extract_dir, exist_ok=True)

        # Download ZIP only if not already present
        if not os.path.exists(local_zip):
            response = requests.get(download_url)
            with open(local_zip, "wb") as f:
                f.write(response.content)
            st.success("✅ Syllabus ZIP downloaded successfully!")
        else:
            st.info("ℹ️ ZIP already exists, using the local file.")

        # Extract ZIP
        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        st.success(f"📂 ZIP extracted to {extract_dir}")

    except Exception as e:
        st.error(f"❌ Error downloading or extracting ZIP: {e}")

# -------------------------------
# 2) Read PDFs and build syllabus hierarchy
# -------------------------------
def read_pdf_text(pdf_path):
    """
    Reads all text lines from a PDF using PyMuPDF (fitz)
    """
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        for line in page.get_text("text").split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines

def extract_syllabus_from_pdfs(root_dir):
    """
    Parses all PDFs in root_dir to build:
    Exam -> Subject -> Topic -> Subtopic
    """
    syllabus = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(root, file)
            lines = read_pdf_text(pdf_path)

            # 1) Detect Exam Name
            exam = None
            for line in lines[:10]:  # first 10 lines
                if "GATE" in line.upper():
                    exam = "GATE 2026"
                    break
                elif "SSC" in line.upper():
                    exam = "SSC"
                    break
                elif "UPSC" in line.upper():
                    exam = "UPSC"
                    break
            if not exam:
                exam = "Unknown Exam"

            # 2) Detect Subject, Topic, Subtopics
            current_subject = None
            current_topic = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Subject heuristic: UPPERCASE lines, <=5 words
                if line.isupper() and len(line.split()) <= 5:
                    current_subject = line.title()
                    continue

                # Topic heuristic: short line, contains ":", or numbered
                if (len(line.split()) <= 6 and ":" in line) or any(c.isdigit() for c in line[:3]):
                    current_topic = line
                    syllabus[exam][current_subject][current_topic] = []
                    continue

                # Subtopic
                if current_subject and current_topic:
                    syllabus[exam][current_subject][current_topic].append(line)

    return syllabus

    # After ZIP extraction
syllabus = extract_syllabus_from_pdfs(extract_dir)
st.success("📚 Syllabus parsed successfully!")

# Display hierarchy
for exam, subjects in syllabus.items():
    st.write(f"### {exam}")
    for subject, topics in subjects.items():
        st.write(f"**Subject:** {subject}")
        for topic, subtopics in topics.items():
            st.write(f"- Topic: {topic}")
            for sub in subtopics:
                st.write(f"    • {sub}")

