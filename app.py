import streamlit as st
import json

st.set_page_config(page_title="GATE Syllabus Viewer", layout="wide")

st.title("📘 GATE Syllabus Viewer")

# -----------------------------
# 1️⃣ Upload JSON
# -----------------------------
uploaded_file = st.file_uploader(
    "Upload GATE syllabus JSON file",
    type=["json"]
)

if not uploaded_file:
    st.info("⬆️ Please upload gate_syllabus.json")
    st.stop()

# -----------------------------
# 2️⃣ Load JSON
# -----------------------------
try:
    gate_syllabus = json.load(uploaded_file)
except Exception as e:
    st.error("❌ Invalid JSON file")
    st.stop()

if not gate_syllabus:
    st.error("❌ JSON is empty")
    st.stop()

st.success("✅ GATE syllabus loaded successfully")

# -----------------------------
# 3️⃣ Sidebar Controls
# -----------------------------
st.sidebar.header("🎯 Selection")

branches = list(gate_syllabus.keys())
selected_branch = st.sidebar.selectbox("Select Branch", branches)

subjects = list(gate_syllabus[selected_branch].keys())
selected_subject = st.sidebar.selectbox("Select Subject", subjects)

# -----------------------------
# 4️⃣ Display Syllabus
# -----------------------------
st.header(f"🧠 Branch: {selected_branch}")
st.subheader(f"📚 Subject: {selected_subject}")

topics = gate_syllabus[selected_branch][selected_subject]

for topic, subtopics in topics.items():
    with st.expander(f"📌 {topic}"):
        if subtopics:
            for s in subtopics:
                st.write(f"- {s}")
        else:
            st.write("No subtopics listed")

# -----------------------------
# 5️⃣ Debug View
# -----------------------------
with st.expander("🔍 View Raw JSON"):
    st.json(gate_syllabus)
