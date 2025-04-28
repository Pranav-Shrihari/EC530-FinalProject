import fitz  # PyMuPDF
import re
import openai
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import difflib
import io

# Step 1: PDF Text Extraction
def extract_text_from_pdf(pdf_path):
    # Open the provided PDF file
    doc = fitz.open(pdf_path)
    text = ""
    
    # Loop through each page and extract text
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text += page.get_text("text")  # Extract text
    
    return text

# Step 2: Text Preprocessing and Organization

# Clean text: remove unwanted content like page numbers, headers, and footers
def clean_text(text):
    # Remove page numbers (for example: "Page 1", "Page 2", etc.)
    text = re.sub(r'Page \d+', '', text)

    # Remove any unwanted extra whitespaces (between words, paragraphs, etc.)
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# Step 3: Summary Generation using AI

# Summarize the entire content using OpenAI's GPT (or another summarizer)
def summarize_text(text):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Correct API call for v1/chat/completions endpoint
    response = openai.chat.completions.create(
        model="gpt-4",  # Ensure the correct model name is used, you can use gpt-3.5-turbo or gpt-4
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Please summarize the following content: {text}"}
        ],
        max_tokens=500,  # Optionally, you can limit the number of tokens in the response
        temperature=0.7  # Controls the randomness of the response
    )
    
    # Extract and return the summary content
    content = response.choices[0].message.content.strip()
    return content

# Step 4: Question Generation using AI

# Generate questions based on the summary of the entire text
def generate_questions_from_summary(summary, num_questions=5, points_per_question=10):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Request questions based on the summary
    response = openai.chat.completions.create(
        model="gpt-4",  # You can also use gpt-3.5-turbo
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Based on the following summary, generate {num_questions} questions for review: {summary}, with each question worth {points_per_question} points."}
        ],
        max_tokens=300,  # You can adjust this number for longer or shorter responses
        temperature=0.7
    )
    
    # Extract and return the generated questions
    questions = response.choices[0].message.content.strip()
    return questions

# Process the entire document: summarize and generate questions
def process_pdf_text(pdf_path):
    # Step 1: Extract text from the PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Step 2: Clean and preprocess the text
    cleaned_text = clean_text(pdf_text)
    
    # Step 3: Summarize the entire content
    summary = summarize_text(cleaned_text)
    
    # Step 4: Generate questions based on the summary
    questions = generate_questions_from_summary(summary)
    
    return summary, questions

# Step 5: Grading User's Response using AI

# Function to grade the user's response using AI
def grade_answer(question, user_answer, max_points = 10):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Request grading feedback based on the user's answer
    response = openai.chat.completions.create(
        model="gpt-4",  # You can also use gpt-3.5-turbo
        messages=[
            {"role": "system", "content": "You are a grading assistant."},
            {"role": "user", "content": f"Question: {question}\nUser Answer: {user_answer}\nGrade the answer out of {max_points} points and provide feedback with an example answer."}
        ],
        max_tokens=200,  # You can adjust this number for longer or shorter responses
        temperature=0.7
    )
    
    # Extract and return the feedback
    feedback = response.choices[0].message.content.strip()
    return feedback

# Step 6: PDF Generation using ReportLab
def create_polished_pdf(summary_text, title="Summary"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Define custom styles
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=20
    )
    body_style = ParagraphStyle(
        name='BodyStyle',
        parent=styles['BodyText'],
        fontSize=12,
        spaceAfter=12
    )
    
    story = []

    # Add the Title
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Spacer(1, 20))

    # Preprocess summary text
    paragraphs = summary_text.strip().split('\n')
    bullet_items = []
    inside_bullet_list = False

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue  # skip empty lines

        # Detect bullets (lines starting with "-" or "•")
        if para.startswith(("-", "•")):
            bullet_text = para.lstrip("-• ").strip()
            # Convert **bold** markers inside bullet
            bullet_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', bullet_text)
            bullet_items.append(Paragraph(bullet_text, body_style))
            inside_bullet_list = True
        else:
            if inside_bullet_list:
                # Close the previous bullet list
                story.append(ListFlowable(
                    [ListItem(item) for item in bullet_items],
                    bulletType='bullet'
                ))
                bullet_items = []
                inside_bullet_list = False

            # Process normal paragraph with bold conversion
            para = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para)
            story.append(Paragraph(para, body_style))
            story.append(Spacer(1, 12))

    # If the summary ends with a bullet list, add it
    if bullet_items:
        story.append(ListFlowable(
            [ListItem(item) for item in bullet_items],
            bulletType='bullet'
        ))

    doc.build(story)
    buffer.seek(0)
    return buffer

# Step 7: Check if the answer is copied from the summary
def is_copied_from_summary(answer, summary, threshold=0.8):
    """
    Check if a significant portion of the answer overlaps with the summary.
    If more than `threshold` similarity, flag as copied.
    """
    answer = answer.strip().lower()
    summary = summary.strip().lower()

    if not answer or not summary:
        return False

    # Direct substring match (quick and strong flag)
    if answer in summary:
        return True

    # Token-based similarity (word overlap)
    answer_words = set(re.findall(r'\w+', answer))
    summary_words = set(re.findall(r'\w+', summary))

    if not answer_words:
        return False

    common_words = answer_words & summary_words
    overlap_ratio = len(common_words) / len(answer_words)

    if overlap_ratio >= threshold:
        return True

    # Fallback: sequence matching (fuzzy matching)
    matcher = difflib.SequenceMatcher(None, answer, summary)
    if matcher.quick_ratio() >= threshold:
        return True

    return False

def highlight_copied_parts(answer, summary, threshold=0.9):
    """
    Returns highlighted answer: copied parts are wrapped in special markdown highlighting
    """
    answer = answer.strip()
    summary = summary.strip()

    summary_sentences = re.split(r'(?<=[.!?]) +', summary)
    marked_answer = answer

    for sentence in summary_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        matcher = difflib.SequenceMatcher(None, answer.lower(), sentence.lower())
        if matcher.ratio() >= threshold or sentence.lower() in answer.lower():
            if sentence in marked_answer:
                # Wrap copied parts with a markdown highlight
                marked_answer = marked_answer.replace(sentence, f"**:red[{sentence}]**")

    return marked_answer

# Main function to prompt the user for a file path and execute the steps
def main():
    # Ask the user to input the file path for the PDF
    pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")

    # Validate the file path and check if it is a PDF
    if not pdf_path.endswith('.pdf'):
        print("Error: The file must be a PDF. Please provide a valid PDF file.")
        pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")
    
    # Check if the file exists and is under 5 pages
    try:
        pdf_doc = fitz.open(pdf_path)
        if pdf_doc.page_count > 5:
            print("Error: The PDF file exceeds 5 pages. Please provide a PDF with 5 or fewer pages.")
            return
    except Exception as e:
        print(f"Error: The file at {pdf_path} could not be opened. Please check the path and try again.")
        return
    
    # Prompt user for either summary or questions
    user_choice = input("Do you want a summary of the document or questions based on it? (Enter 'summary' or 'questions'): ").strip().lower()
    
    # Process the file based on the user's choice
    try:
        with open(pdf_path, 'rb'):  # Open the file in binary mode to check its existence
            
            summary, questions = process_pdf_text(pdf_path)
            
            if user_choice == 'summary':
                print("\nSummary of the document:\n")
                print(summary)
                add_questions = input("\nDo you want to generate questions based on the summary? (yes/no): ").strip().lower()
                if add_questions == 'yes':
                    print("\nGenerated Questions for the summary:")
                    # Ask each question one by one
                    for idx, question in enumerate(questions.split('\n')):
                        print(f"\nQuestion {question}")
                        user_answer = input("Your answer: ").strip()
                        feedback = grade_answer(question, user_answer)
                        print("\nAI Feedback:\n", feedback)
                else:
                    print("\nNo questions generated, have a nice day!\n")

            
            elif user_choice == 'questions':
                print("\nGenerated Questions for the document:")
                
                # Ask each question one by one
                for idx, question in enumerate(questions.split('\n')):
                    print(f"\nQuestion {question}")
                    user_answer = input("Your answer: ").strip()
                    feedback = grade_answer(question, user_answer)
                    print("\nAI Feedback:\n", feedback)
            
            else:
                print("Invalid input. Please enter 'summary' or 'questions'.")
            
    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
