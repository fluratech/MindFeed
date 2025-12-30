import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def summarize_text(text, preferences):
    """
    Summarizes text using Google Gemini based on user preferences.
    """
    if not GOOGLE_API_KEY:
        return "Error: Google API Key not found."

    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    You are an AI news assistant. Please summarize the following text based on these preferences:
    - Topics of Interest: {preferences.get('topics', 'General')}
    - Summary Style (Length/Depth): {preferences.get('summary_length', 'Balanced')}
    - Reading Time Target: {preferences.get('reading_time', '5')} minutes
    - Language: {preferences.get('language', 'English')}

    Text to summarize:
    {text[:10000]}  # Truncate to avoid token limits if necessary, though Gemini has a large window.
    
    Provide a structured response using Markdown with sections for:
    - **Headline**
    - **Summary**
    - **Key Facts** (Who, What, When, Where, Why)
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error interacting with Gemini API: {e}"
