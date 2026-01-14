# app.py
import streamlit as st
import os
import zipfile
import gdown
import fitz  # PyMuPDF
import re
import json
from collections import defaultdict
from datetime import datetime

# ---------------------------------
# CONFIGURATION
# ---------------------------------
DRIVE_FILE_ID = "1S6fcsuq9KvICTsOBOdp6_WN9FhzruixM"
ZIP_PATH = "plan.zip"
EXTRACT_DIR = "syllabus_data"

# ---------------------------------
# UTILITY FUNCTIONS
# ---------------------------------
def download_and_extract():
    """Download zip from Google Drive and extract."""
    if not os.path.exists(ZIP_PATH):
        url = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}"
        gdown.download(url, ZIP_PATH, quiet=False)
    
    if not os.path.exists(EXTRACT_DIR):
        with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

def list_pdfs():
    """List all PDFs in the extracted directory."""
    pdf_files = []
    for root, _, files in os.walk(EXTRACT_DIR):
        for file in files:
            if file.endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def parse_syllabus(text):
    """Parse syllabus text into a structured dictionary."""
    syllabus = defaultdict(list)
    lines = text.split("\n")
    current_module = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Assume module headers contain "Module" or "Unit"
        if re.search(r"(Module|Unit)\s*\d+", line, re.I):
            current_module = line
        elif current_module:
            syllabus[current_module].append(line)
    return syllabus

# ---------------------------------
# MAIN STREAMLIT APP
# ---------------------------------
st.title("📄 Syllabus Explorer")

download_and_extract()
pdf_files = list_pdfs()

if not pdf_files:
    st.warning("No PDF files found in the extracted folder.")
else:
    st.sidebar.header("Select PDFs to view")
    
    selected_pdfs = []
    for idx, pdf_file in enumerate(pdf_files):
        if st.sidebar.checkbox(os.path.basename(pdf_file), key=f"pdf_checkbox_{idx}"):
            selected_pdfs.append(pdf_file)

    for pdf_file in selected_pdfs:
        st.subheader(os.path.basename(pdf_file))
        text = extract_text_from_pdf(pdf_file)
        syllabus = parse_syllabus(text)

        for module, topics in syllabus.items():
            with st.expander(module):
                for topic_idx, topic in enumerate(topics):
                    st.checkbox(topic, key=f"{os.path.basename(pdf_file)}_topic_{topic_idx}")
