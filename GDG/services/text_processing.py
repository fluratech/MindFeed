import os
import PyPDF2

def extract_text_from_pdf(filepath):
    """
    Extracts text from a PDF file.
    """
    text = ""
    try:
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None
    return text

def clean_text(text):
    """
    Basic text cleaning.
    """
    # Remove excessive whitespace
    text = " ".join(text.split())
    return text
