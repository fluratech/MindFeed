from flask import Flask, render_template, session, redirect, url_for, jsonify, request
import os
import json
import requests
import feedparser
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from models import db, User, History
from datetime import datetime, timedelta, timezone
import urllib.parse
import PyPDF2
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
load_dotenv()

# --- CONFIGURATION ---
# ⚠️ REPLACE WITH YOUR ACTUAL API KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyArUhdCpqR01kgN-aXUP_0yM-v6Udkoo2M")
client = genai.Client(api_key=GEMINI_API_KEY)

# --- HELPER: INDIAN STANDARD TIME ---
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Returns current time in IST"""
    return datetime.now(IST)

# --- HELPER: EXTRACT TEXT FROM PDF ---
def extract_text_from_pdf(file_storage):
    """Extracts text from an uploaded PDF file in memory."""
    try:
        pdf_reader = PyPDF2.PdfReader(file_storage)
        text = ""
        max_pages = min(len(pdf_reader.pages), 12) 
        for page_num in range(max_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"PDF Error: {e}")
        return ""

def extract_text_from_url(url):
    """Scrapes the main text content from a news URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Kill all script and style elements (removes ads/tracking code)
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()    

        # Get text from paragraph tags (most news sites store articles in <p>)
        text = " ".join([p.get_text() for p in soup.find_all('p')])
        
        # Clean up whitespace
        return " ".join(text.split())
        
    except Exception as e:
        print(f"Scraping Error: {e}")
        return ""

def clean_json_string(text):
    """Removes Markdown formatting from AI response"""
    text = text.strip()
    if text.startswith("```json"): text = text.replace("```json", "", 1)
    if text.startswith("```"): text = text.replace("```", "", 1)
    if text.endswith("```"): text = text.replace("```", "", 1)
    return text.strip()

# --- HELPER: DYNAMIC RSS FETCH ---
def fetch_rss_news_for_topics(topics):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    combined_text = ""
    
    if not topics: topics = ["Kerala"]

    print(f"🔍 Fetching custom news for: {topics}")
    
    for topic in topics:
        query_term = topic
        if isinstance(topic, dict): query_term = topic.get("id", "")
        if not query_term: continue

        encoded_topic = urllib.parse.quote(query_term)
        rss_url = f"https://news.google.com/rss/search?q={encoded_topic}&hl=ml&gl=IN&ceid=IN:ml"
        
        try:
            print(f"   -> {query_term}: {rss_url}")
            response = requests.get(rss_url, headers=headers, timeout=4)
            if response.status_code == 200:
                feed = feedparser.parse(BytesIO(response.content))
                if not feed.entries: continue

                count = 0
                for entry in feed.entries:
                    if count >= 2: break
                    title = entry.title if 'title' in entry else ""
                    clean_title = title.rsplit('-', 1)[0].strip()
                    combined_text += f"Topic: {query_term} | Headline: {clean_title}\n"
                    count += 1
        except Exception as e:
            print(f"      ❌ Error fetching {query_term}: {e}")

    return combined_text

def generate_ai_news(topics):
    raw_text = fetch_rss_news_for_topics(topics)
    
    backup_data = {
        "headlines": ["വാർത്തകൾ ലഭ്യമാകുന്നില്ല.", "ഇന്റർനെറ്റ് കണക്ഷൻ പരിശോധിക്കുക."],
        "details": ["സാങ്കേതിക തകരാർ മൂലം വാർത്തകൾ ലഭ്യമാക്കാൻ സാധിക്കുന്നില്ല.", "അല്പസമയത്തിന് ശേഷം വീണ്ടും ശ്രമിക്കുക."]
    }

    if not raw_text or len(raw_text) < 50:
        print("⚠️ RSS Empty. Using Backup.")
        return backup_data

    prompt = f"""
    You are a professional Malayalam Radio News Editor.
    The listener is interested in these topics: {", ".join(topics)}.
    Below are the latest raw headlines fetched for them.
    
    Task:
    1. Select the 3-4 most important stories relevant to their interests.
    2. Rewrite them into a professional script for a Radio Broadcast.
    3. Output MUST be valid JSON.
    4. Language: Malayalam.
    
    Raw News:
    {raw_text[:12000]}
    
    Output Format (JSON):
    {{
        "headlines": ["Short Headline 1", "Short Headline 2"],
        "details": ["Detail 1", "Detail 2"]
    }}
    """

    try:
        response = client.models.generate_content(
            model='gemma-3-27b-it', 
            contents=prompt
        )
        cleaned = clean_json_string(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return backup_data

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev_secret_key_change_in_prod'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    from auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    # --- ROUTES ---
    @app.route('/')
    def index():
        if 'user_id' in session: return redirect(url_for('dashboard'))
        return redirect(url_for('auth.login'))

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session: return redirect(url_for('auth.login'))
        return render_template('dashboard.html')

    @app.route('/live-news')
    def live_news():
        if 'user_id' not in session: return redirect(url_for('auth.login'))
        return render_template('live_news.html')

    @app.route('/history')
    def history():
        if 'user_id' not in session: return redirect(url_for('auth.login'))
        
        selected_date = request.args.get('date')
        query = db.session.query(History).filter_by(user_id=session['user_id'])
        
        if selected_date:
            query = query.filter(History.summary_date == selected_date)
        
        # Sort by Newest First
        user_history = query.order_by(History.created_at.desc()).all()
            
        return render_template('history.html', history=user_history, selected_date=selected_date)

    @app.route('/upload-news')
    def upload_news_page():
        if 'user_id' not in session: return redirect(url_for('auth.login'))
        return render_template('upload_news.html')

    # --- API ENDPOINTS ---

    # API 1: PROCESS PDF NEWSPAPER
    @app.route('/api/process-pdf', methods=['POST'])
    def process_pdf():
        if 'user_id' not in session: return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        if 'file' not in request.files: return jsonify({'success': False, 'message': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '': return jsonify({'success': False, 'message': 'No file selected'}), 400

        print(f"📄 Processing PDF: {file.filename}")
        raw_text = extract_text_from_pdf(file)
        
        if len(raw_text) < 100:
            return jsonify({'success': False, 'message': 'Could not read text. Is this an image scan?'}), 400

        user = db.session.get(User, session['user_id'])
        user_prefs = user.preferences if user.preferences else {}
        user_topics = user_prefs.get('topics', [])
        
        cleaned_topics = []
        for t in user_topics:
            if isinstance(t, dict): cleaned_topics.append(t.get('id', 'General'))
            else: cleaned_topics.append(str(t))
        if not cleaned_topics: cleaned_topics = ["General News"]

        print(f"🧠 Filtering PDF for topics: {cleaned_topics}")
        
        prompt = f"""
        You are a professional Malayalam Radio News Editor.
        I have uploaded a newspaper PDF. 
        The listener is ONLY interested in these topics: {", ".join(cleaned_topics)}.
        
        Task:
        1. Scan the raw PDF text below.
        2. STRICTLY FILTER out stories that do not match the user's topics.
        3. Select the 3 most important stories that match their interests.
        4. Rewrite them into a professional script for a Radio Broadcast.
        5. Output MUST be valid JSON.
        6. Language: Malayalam.
        
        Raw PDF Text (Truncated):
        {raw_text[:25000]} 
        
        Output Format (JSON):
        {{
            "headlines": ["Short Headline 1", "Short Headline 2"],
            "details": ["Detail 1", "Detail 2"]
        }}
        """

        try:
            response = client.models.generate_content(
                model='gemma-3-27b-it', 
                contents=prompt
            )
            cleaned_json = clean_json_string(response.text)
            news_data = json.loads(cleaned_json)

            # --- SAVE PDF HISTORY (FIXED) ---
            try:
                headlines = news_data.get('headlines', [])
                summary_text = f"PDF: {file.filename} | " + (" | ".join(headlines) if headlines else "")

                new_history = History(
                    user_id=user.id,
                    summary_date=get_ist_now().date(),  # Uses IST
                    created_at=get_ist_now(),           # Uses IST
                    content=summary_text[:500], 
                    meta_data=news_data 
                )
                db.session.add(new_history)
                db.session.commit()
                print(f"✅ PDF History SAVED for User {user.id}")
            except Exception as db_e:
                db.session.rollback()
                print(f"❌ PDF DB Save Error: {db_e}")
            
            return jsonify({'success': True, 'news_data': news_data})
            
        except Exception as e:
            print(f"❌ AI PDF Error: {e}")
            return jsonify({'success': False, 'message': 'AI failed to process PDF.'}), 500

    # ROUTE 3: Upload Link Page
    @app.route('/upload-link')
    def upload_link_page():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('upload_link.html')

    # API 3: PROCESS NEWS LINK
    @app.route('/api/process-link', methods=['POST'])
    def process_link():
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'success': False, 'message': 'No URL provided'}), 400

        print(f"🔗 Processing URL: {url}")
        
        # 1. Scrape Text
        raw_text = extract_text_from_url(url)
        
        if len(raw_text) < 200:
            return jsonify({'success': False, 'message': 'Could not extract enough text from this link. It might be behind a paywall.'}), 400

        # 2. Get User
        user = db.session.get(User, session['user_id'])
        
        # 3. AI Generate
        prompt = f"""
        You are a professional Malayalam Radio News Editor.
        I have provided the raw text of a news article below.
        
        Task:
        1. Summarize this specific article into a short, engaging radio news segment.
        2. Keep it under 60 words.
        3. Language: Malayalam.
        4. Output MUST be valid JSON.
        
        Article Text:
        {raw_text[:15000]}
        
        Output Format (JSON):
        {{
            "headlines": ["Main Headline"],
            "details": ["Summary of the article..."]
        }}
        """

        try:
            response = client.models.generate_content(
                model='gemma-3-27b-it', 
                contents=prompt
            )
            cleaned_json = clean_json_string(response.text)
            news_data = json.loads(cleaned_json)

            # 4. Save to History
            try:
                headlines = news_data.get('headlines', [])
                summary_text = f"Link: {url[:30]}... | " + (" | ".join(headlines) if headlines else "")
                
                new_history = History(
                    user_id=user.id,
                    summary_date=get_ist_now().date(),
                    created_at=get_ist_now(),
                    content=summary_text[:500],
                    meta_data=news_data
                )
                db.session.add(new_history)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"History Save Error: {e}")

            return jsonify({'success': True, 'news_data': news_data})

        except Exception as e:
            print(f"❌ AI Link Error: {e}")
            return jsonify({'success': False, 'message': 'AI failed to process link.'}), 500
    # API 2: PROCESS LIVE RSS NEWS
    @app.route('/api/process-news', methods=['POST'])
    def process_news():
        if 'user_id' not in session: return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        user = db.session.get(User, session['user_id'])
        if not user: return jsonify({'success': False, 'message': 'User not found'}), 404

        # Safe Preferences Loading
        user_prefs = user.preferences if user.preferences else {}
        user_topics = user_prefs.get('topics', [])
        
        cleaned_topics = []
        for t in user_topics:
            if isinstance(t, dict): cleaned_topics.append(t.get('id', 'General'))
            else: cleaned_topics.append(str(t))
        if not cleaned_topics: cleaned_topics = ["Kerala"]

        print(f"👤 User {user.id} requested topics: {cleaned_topics}")

        news_data = generate_ai_news(cleaned_topics)
        
        # Save History
        try:
            headlines = news_data.get('headlines', [])
            summary_text = " | ".join(headlines) if headlines else "News Briefing"

            new_history = History(
                user_id=user.id,
                summary_date=get_ist_now().date(),  # Uses IST
                created_at=get_ist_now(),           # Uses IST
                content=summary_text[:500], 
                meta_data=news_data 
            )
            db.session.add(new_history)
            db.session.commit()
            print(f"✅ RSS History SAVED for User {user.id}")
        except Exception as e:
            db.session.rollback()
            print(f"❌ History Save Error: {e}")

        return jsonify({'success': True, 'news_data': news_data})

    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)