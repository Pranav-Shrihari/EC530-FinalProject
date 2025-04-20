import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path):
    # Open the provided PDF file
    doc = fitz.open(pdf_path)
    text = ""
    
    # Loop through each page and extract text
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text += page.get_text("text")  # Extract text
    
    return text

def main():
    # Ask the user to input the file path
    pdf_path = input("Please enter the file path of the PDF: ")
    
    # Check if the file exists
    try:
        with open(pdf_path, 'rb'):  # Try to open the file in binary mode
            print(f"Extracting text from: {pdf_path}")
            pdf_text = extract_text_from_pdf(pdf_path)
            print("Text extraction complete.")
            print(pdf_text)
    except FileNotFoundError:
        print(f"Error: The file at {pdf_path} was not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
