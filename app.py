import streamlit as st
import fitz
from PDF_extractor import extract_text_from_pdf, clean_text, summarize_text, generate_questions_from_summary, grade_answer
import tempfile
import openai

st.set_page_config(page_title="PDF Summarizer & Quizzer", layout="centered")
st.title("📄 PDF Summarizer & Quiz Generator")

# 🔐 Prompt for API Key
if "api_key_validated" not in st.session_state or not st.session_state.api_key_validated:
    api_key = st.text_input("Enter your OpenAI API Key:", placeholder="sk-...", type="password")

    if not api_key:
        st.warning("Please enter your API key to proceed.")
        st.stop()

    # Set key for OpenAI
    client = openai.OpenAI(api_key=api_key)

    # Validate API key by listing models (minimal test)
    try:
        client.models.list()  # this will raise if the key is invalid
        st.session_state.api_key_validated = True
        st.session_state.api_key = api_key  # store it if needed elsewhere
        st.rerun()  # refresh to hide the key field
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
    # Key has already been validated in session
    api_key = st.session_state.api_key
    client = openai.OpenAI(api_key=api_key)

# If needed, set the key in environment (optional)
import os
os.environ["OPENAI_API_KEY"] = api_key

# Show success message only if file has not yet been uploaded
api_success = st.success("✅ API Key validated successfully! You can now upload your PDF.")

uploaded_file = st.file_uploader("Upload your PDF file (max 5 pages)", type="pdf")

if uploaded_file:
    api_success.empty()  # Clear the success message
    # Save to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    # Check if the file is a PDF and less than 5 pages
    try:
        pdf_doc = fitz.open(tmp_path)
        if pdf_doc.page_count > 5:
            st.error("The PDF file exceeds 5 pages. Please provide a PDF with 5 or fewer pages.")
            st.stop()
    except Exception as e:
        st.error(f"Error: The file could not be opened. Please check the path and try again.")
        st.stop()

    st.success("✅ PDF uploaded successfully!")

    if "summary" not in st.session_state:
        with st.spinner("Generating summary..."):
            pdf_text = extract_text_from_pdf(tmp_path)
            cleaned_text = clean_text(pdf_text)
            summary = summarize_text(cleaned_text)
            st.session_state.summary = summary
    else:
        summary = st.session_state.summary

    st.subheader("📝 Summary")
    st.write(summary)

    if st.checkbox("Would you like to generate questions based on this summary?"):
        if "questions_text" not in st.session_state:
            with st.spinner("Generating questions..."):
                questions_text = generate_questions_from_summary(summary)
                st.session_state.questions_text = questions_text
        else:
            questions_text = st.session_state.questions_text

        st.subheader("🧠 Questions")
        questions = questions_text.split("\n")

        for i, question in enumerate(questions):
            question_container = st.container()  # Keeps everything grouped together

            with question_container:
                st.markdown(f"**Q{question.strip()}**")
                user_answer = st.text_area("Your Answer:", key=f"answer_{i}")

                # Prepare a persistent area for feedback
                feedback_placeholder = st.empty()

                # Initialize feedback in session state if not present
                if f"feedback_{i}" not in st.session_state:
                    st.session_state[f"feedback_{i}"] = ""

                # Handle grading button
                if st.button(f"Grade Answer {i+1}", key=f"grade_button_{i}"):
                    if user_answer.strip():
                        with st.spinner("Grading..."):
                            feedback = grade_answer(question, user_answer)
                        st.session_state[f"feedback_{i}"] = feedback
                    else:
                        st.warning("Please enter an answer before grading.")

                # Always show the feedback (if available)
                if st.session_state[f"feedback_{i}"]:
                    feedback_placeholder.markdown(f"**Feedback for Q{i+1}:**\n\n{st.session_state[f'feedback_{i}']}")