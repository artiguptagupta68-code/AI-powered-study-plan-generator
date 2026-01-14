# app.py
import streamlit as st
import json
import os

# -----------------------------
# 1️⃣ CONFIGURATION
# -----------------------------
GATE_JSON_PATH = "gate_syllabus.json"  # put JSON in same folder

st.set_page_config(page_title="GATE Syllabus Viewer", layout="wide")

st.title("📘 GATE Syllabus Viewer")

# -----------------------------
# 2️⃣ LOAD JSON
# -----------------------------
if not os.path.exists(GATE_JSON_PATH):
    st.error("❌ gate_syllabus.json not found")
    st.stop()

with open(GATE_JSON_PATH, "r") as f:
    gate_syllabus = json.load(f)

if not gate_syllabus:
    st.error("❌ GATE syllabus JSON is empty")
    st.stop()

st.success("✅ GATE syllabus loaded successfully")

# -----------------------------
# 3️⃣ SIDEBAR CONTROLS
# -----------------------------
st.sidebar.header("🎯 Selection")

branches = list(gate_syllabus.keys())
selected_branch = st.sidebar.selectbox("Select Branch", branches)

subjects = list(gate_syllabus[selected_branch].keys())
selected_subject = st.sidebar.selectbox("Select Subject", subjects)

# -----------------------------
# 4️⃣ DISPLAY SYLLABUS
# -----------------------------
st.header(f"🧠 Branch: {selected_branch}")
st.subheader(f"📚 Subject: {selected_subject}")

topics = gate_syllabus[selected_branch][selected_subject]

for topic, subtopics in topics.items():
    with st.expander(f"📌 {topic}", expanded=False):
        if subtopics:
            for s in subtopics:
                st.write(f"- {s}")
        else:
            st.write("No subtopics listed")

# -----------------------------
# 5️⃣ OPTIONAL JSON DEBUG
# -----------------------------
with st.expander("🔍 View Raw JSON"):
    st.json(gate_syllabus)
