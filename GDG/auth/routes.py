from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
# We need to import db and User. 
# Since they are in app.py, we need to handle circular imports.
# A better way for this structure is to have db defined separately. 
# I will assume I can import `from app import db, User` but app.py imports auth.routes.
# To break this, I will move db and User to a separate file `database.py` even if not in the prompt list, 
# because "Production-quality" implies working code.
# OR I can define the blueprint here and import it in app.py (done), 
# and import db/User inside the functions or use current_app extensions?
# No, standard is `models.py`. I will add `models.py`.

from models import db, User, History 

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'Email already registered'}), 400
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        
        # Extract preferences
        preferences = {
            'topics': data.get('topics', []),
            'summary_length': data.get('summary_length', 'balanced')
        }
        
        new_user = User(name=name, email=email, password_hash=hashed_pw, preferences=preferences)
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'success': True, 'redirect': url_for('auth.login')})

    return render_template('register.html')

@auth_bp.route('/preferences', methods=['GET', 'POST'])
def preferences():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data = request.json
        # Merge new preferences with existing ones to avoid data loss if we add more fields later
        current_prefs = user.preferences or {}
        # Validate and sanitize data
        # Ensure topics is a list of objects or strings, normalize to list of objects
        raw_topics = data.get('topics', [])
        # ... validation logic could go here ...
        
        current_prefs['topics'] = raw_topics
        current_prefs['summary_length'] = data.get('summary_length', 'balanced')
        current_prefs['reading_time'] = data.get('reading_time', '5')
        
        user.preferences = current_prefs
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")
        
        db.session.commit()
        return jsonify({'success': True})
        
    # Ensure preferences is a dict using 'or {}'
    return render_template('preferences.html', preferences=user.preferences or {})

@auth_bp.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    # Sort by newest first
    query = History.query.filter_by(user_id=session['user_id'])
    
    selected_date = request.args.get('date')
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            query = query.filter(History.summary_date == filter_date)
        except ValueError:
            pass # Ignore invalid date formats
            
    user_history = query.order_by(History.created_at.desc()).all()
    return render_template('history.html', history=user_history, selected_date=selected_date)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
