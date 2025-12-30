from gtts import gTTS
import os
import uuid

def generate_audio(text, output_folder):
    """
    Generates audio from text using gTTS and saves it to the output folder.
    Returns the filename.
    """
    try:
        # Clean markdown characters for better TTS
        clean_text = text.replace('*', '').replace('#', '').replace('-', ' ')
        
        tts = gTTS(text=clean_text, lang='en')
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(output_folder, filename)
        tts.save(filepath)
        return filename
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None
