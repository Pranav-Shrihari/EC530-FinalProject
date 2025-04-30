import streamlit as st
import fitz
from pdf_quiz_generator.PDF_extractor import (
    extract_text_from_pdf,
    clean_text,
    summarize_text,
    generate_questions_from_summary,
    grade_answer,
    create_polished_pdf,
    create_quiz_feedback_pdf
)
import tempfile
import openai
import os
import re

# --- Page Config ---
st.set_page_config(page_title="PDF Summarizer & Quiz Generator", layout="centered")
st.title("📄 PDF Summarizer & Quiz Generator")

# --- API Key Prompt ---
if "api_key_validated" not in st.session_state or not st.session_state.api_key_validated:
    api_key = st.text_input(
        "Enter your OpenAI API Key:", placeholder="sk-...", type="password"
    )
    if not api_key:
        st.warning("Please enter your API key to proceed.")
        st.stop()
    client = openai.OpenAI(api_key=api_key)
    try:
        client.models.list()
        st.session_state.api_key_validated = True
        st.session_state.api_key = api_key
        st.rerun()
    except openai.AuthenticationError:
        st.error("Invalid API key. Please enter a valid OpenAI API key.")
        st.stop()
    except openai.OpenAIError as e:
        st.error(f"OpenAI Error: {str(e)}")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        st.stop()
else:
    api_key = st.session_state.api_key
    client = openai.OpenAI(api_key=api_key)

# Ensure downstream OpenAI calls pick up the key
os.environ["OPENAI_API_KEY"] = api_key

# --- PDF Upload & Summary Reset ---
if "summary" not in st.session_state:
    api_success = st.success("✅ API Key validated successfully! You can now upload your PDF.")
    uploaded_file = st.file_uploader("Upload your PDF file (max 5 pages)", type="pdf")
    if not uploaded_file:
        st.stop()
    api_success.empty()

    # Save to temp and check page count
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    try:
        pdf_doc = fitz.open(tmp_path)
        if pdf_doc.page_count > 5:
            st.error("The PDF exceeds 5 pages. Please upload up to 5 pages.")
            st.stop()
    except Exception:
        st.error("Error opening PDF. Please check the file and try again.")
        st.stop()

    # Generate summary once
    with st.spinner("PDF Uploaded Successfully! Generating summary..."):
        raw = extract_text_from_pdf(tmp_path)
        cleaned = clean_text(raw)
        st.session_state.summary = summarize_text(cleaned)
    st.rerun()

# At this point, we have a summary
summary = st.session_state.summary

# --- Summary vs Quiz Toggle ---
quiz_active = (
    st.session_state.get("questions_generated", False)
    and not st.session_state.get("graded_all", False)
)
show_questions = st.session_state.get("questions_generated", False)

# Display checkbox only before quiz generation or after grading reset
if not quiz_active and not show_questions:
    if st.checkbox("Would you like to generate questions based on this summary?", key="show_questions_checkbox"):
        st.session_state.questions_generated = True
        st.session_state.pop("graded_all", None)
        st.rerun()

# --- Render Content ---
if not show_questions:
    # Summary display
    st.subheader("📝 Summary")
    st.write(summary)
    buffer = create_polished_pdf(summary, title="Generated Summary")

    col_backpage, col_quiz = st.columns([2, 1])
    with col_backpage:
        # Upload New PDF button
        if st.button("🔄 Upload New PDF", key="reset_pdf"):
            # clear summary + quiz state
            for key in [
                "summary", "questions_generated", "questions_text", "graded_all",
                "quiz_settings_locked", "num_q_input", "pts_q_input"
            ]:
                st.session_state.pop(key, None)
            # clear dynamic answers/feedback
            for k in list(st.session_state.keys()):
                if k.startswith("answer_") or k.startswith("feedback_"):
                    st.session_state.pop(k, None)
            st.rerun()

    with col_quiz:
        st.download_button(
            label="Download Summary as PDF",
            data=buffer,
            file_name="summary.pdf",
            mime="application/pdf",
        )

else:
    # --- Quiz Settings & Generation ---
    if "quiz_settings_locked" not in st.session_state:
        st.session_state.quiz_settings_locked = False
    if not st.session_state.quiz_settings_locked:
        st.subheader("🛠 Customize Your Quiz")
        num_q = st.text_input("How many questions?", key="num_q_input")
        pts_q = st.text_input("Points per question?", key="pts_q_input")
        if st.button("✅ Confirm Settings", key="confirm_settings_button"):
            try:
                n = int(num_q)
                p = int(pts_q)
                if n <= 0 or p <= 0:
                    st.error("Enter positive integers.")
                    st.stop()
                st.session_state.num_questions = n
                st.session_state.points_per_question = p
                st.session_state.quiz_settings_locked = True
                st.rerun()
            except ValueError:
                st.error("Please enter valid integers.")
                st.stop()
    else:
        # --- Generate Questions ---
        if "questions_text" not in st.session_state:
            with st.spinner("Generating questions..."):
                qt = generate_questions_from_summary(
                    summary,
                    num_questions=st.session_state.num_questions,
                    points_per_question=st.session_state.points_per_question,
                )
                st.session_state.questions_text = qt
        questions = st.session_state.questions_text.split("\n")

        st.subheader("🧠 Questions")
        for i, ques in enumerate(questions):
            st.markdown(f"**Q{ques.strip()}**")
            st.session_state.setdefault(f"answer_{i}", "")
            st.session_state.setdefault(f"feedback_{i}", "")

            readonly = st.session_state.get("graded_all", False)
            _ = st.text_area(
                "Your Answer:", key=f"answer_{i}", height=150,
                disabled=readonly
            )

            if st.session_state[f"feedback_{i}"]:
                feedback_html = st.session_state[f"feedback_{i}"]
                st.markdown(f"**Feedback for Q{i+1}:**", unsafe_allow_html=True)
                st.markdown(feedback_html, unsafe_allow_html=True)

        # --- Grade All Questions (stepwise) ---
        st.session_state.setdefault("grading_all", False)
        st.session_state.setdefault("grading_index", 0)

        if not st.session_state.get("graded_all", False) \
           and not st.session_state.get("grading_all", False):
            if st.button("📖 Grade All Questions", key="grade_all_button"):
                missing = [
                    idx for idx in range(len(questions))
                    if not st.session_state.get(f"answer_{idx}", "").strip()
                ]
                if missing:
                    st.warning("Please answer all questions before grading.")
                else:
                    for idx in range(len(questions)):
                        st.session_state.pop(f"feedback_{idx}", None)
                    st.session_state.grading_all = True
                    st.session_state.grading_index = 0
                    st.rerun()

        if st.session_state.get("grading_all", False):
            idx = st.session_state.grading_index
            ques = questions[idx]
            ans = st.session_state.get(f"answer_{idx}", "").strip()
            with st.spinner(f"Grading Q{idx+1}..."):
                fb = grade_answer(
                    ques,
                    ans,
                    summary,
                    st.session_state.points_per_question,
                )
            fb_norm = re.sub(r"(?i)(\d+)\s*out of\s*(\d+)", r"\1/\2", fb)
            st.session_state[f"feedback_{idx}"] = fb_norm
            st.session_state.grading_index += 1
            if st.session_state.grading_index >= len(questions):
                st.session_state.grading_all = False
                st.session_state.graded_all = True
            st.rerun()

    # --- Quiz Summary & Back to Summary Button ---
    if st.session_state.get("graded_all", False):
        total_score = 0
        total_possible = st.session_state.num_questions * st.session_state.points_per_question
        for i in range(st.session_state.num_questions):
            fb = st.session_state.get(f"feedback_{i}", "")
            match = re.search(r"(\d+)/(\d+)", fb)
            if match:
                total_score += int(match.group(1))
        percentage = (total_score / total_possible) * 100 if total_possible > 0 else 0
        if percentage >= 90:
            letter = "A"
        elif percentage >= 80:
            letter = "B"
        elif percentage >= 65:
            letter = "C"
        elif percentage >= 50:
            letter = "D"
        else:
            letter = "F"
        st.subheader("🎉 Quiz Summary")
        st.markdown(f"**Total Score:** {total_score}/{total_possible}")
        st.markdown(f"**Percentage:** {percentage:.1f}%")
        st.markdown(f"**Grade:** {letter}")

        # Download Quiz Feedback PDF
        quiz_buf = create_quiz_feedback_pdf(
            questions,
            [st.session_state[f"answer_{i}"] for i in range(len(questions))],
            [st.session_state[f"feedback_{i}"] for i in range(len(questions))],
            title="Quiz & Feedback"
        )

        # Two columns: left for Back, right for Download
        col_back, col_download = st.columns([2, 1])
        with col_back:
            if st.button("🔙 Back to Summary", key="back_to_summary"):
                # clear quiz-related state (keep summary)
                for key in [
                    "questions_generated", "questions_text", "graded_all",
                    "quiz_settings_locked", "num_q_input", "pts_q_input"
                ]:
                    st.session_state.pop(key, None)
                for k in list(st.session_state.keys()):
                    if k.startswith("answer_") or k.startswith("feedback_"):
                        st.session_state.pop(k, None)
                st.rerun()

        with col_download:
            st.download_button(
                label="📥 Download Quiz + Feedback as PDF",
                data=quiz_buf,
                file_name="quiz_feedback.pdf",
                mime="application/pdf",
            )

        # Three columns: left for Back, right for Download
        col_spacer, col_newpdf, col_spacer2 = st.columns([2, 1, 2])
        with col_spacer:
            st.empty()
        with col_spacer2:
            st.empty()
        with col_newpdf:
            # Upload New PDF button
            if st.button("🔄 Upload New PDF", key="reset_pdf_from_quiz"):
                # clear summary + quiz state
                for key in [
                    "summary", "questions_generated", "questions_text", "graded_all",
                    "quiz_settings_locked", "num_q_input", "pts_q_input"
                ]:
                    st.session_state.pop(key, None)
                # clear dynamic answers/feedback
                for k in list(st.session_state.keys()):
                    if k.startswith("answer_") or k.startswith("feedback_"):
                        st.session_state.pop(k, None)
                st.rerun()
