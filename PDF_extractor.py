import fitz  # PyMuPDF
import re
import openai
import os

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

# Summarize each section using OpenAI's GPT (or another summarizer)
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
    content = response.choices[0].message.content.strip()  # Corrected access pattern
    return content

# Generate questions based on the summary of each section
def generate_questions_from_summary(summary):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    
    # Request questions based on the summary
    response = openai.chat.completions.create(
        model="gpt-4",  # You can also use gpt-3.5-turbo
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Based on the following summary, generate 5 questions for review: {summary}"}
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

# Main function to prompt the user for a file path and execute the steps
def main():
    # Ask the user to input the file path for the PDF
    pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")

    # Validate the file path and check if it is a PDF
    if not pdf_path.endswith('.pdf'):
        print("Error: The file must be a PDF. Please provide a valid PDF file.")
        pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")
    if fitz.open(pdf_path).page_count > 5:
        print("Error: The PDF file exceeds 5 pages. Please provide a PDF with 5 or fewer pages.")
        pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")
    if not os.path.exists(pdf_path):
        print("Error: The file does not exist. Please check the path and try again.")
        pdf_path = input("Please enter the file path of the PDF (ensure it is less than 5 pages): ")
    
    # Check if the file exists and process it
    try:
        with open(pdf_path, 'rb'):  # Open the file in binary mode to check its existence
            print(f"Extracting and processing text from: {pdf_path}")
            summary, questions = process_pdf_text(pdf_path)
            
            print("\nSummary of the document:\n")
            print(summary)
            
            print("\nGenerated Questions for the document:\n")
            print(questions)
            
    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
