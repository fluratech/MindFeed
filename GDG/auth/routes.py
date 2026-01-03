from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, History
from sqlalchemy.orm.attributes import flag_modified  # <--- The Fix

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
            'summary_length': data.get('summary_length', 'balanced'),
            'language': 'malayalam' # Default lang
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
        
    user = db.session.get(User, session['user_id'])
    
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data = request.json
        
        # 1. Get current preferences safely
        current_prefs = user.preferences if user.preferences else {}
        
        # 2. Update dictionary
        # We create a new dict to ensure Python treats it as a fresh object
        updated_prefs = dict(current_prefs)
        
        # Update fields
        if 'topics' in data: updated_prefs['topics'] = data['topics']
        if 'summary_length' in data: updated_prefs['summary_length'] = data['summary_length']
        if 'reading_time' in data: updated_prefs['reading_time'] = data['reading_time']
        if 'language' in data: updated_prefs['language'] = data['language'] # <--- Save Language
        
        # 3. Assign back
        user.preferences = updated_prefs
        
        # 4. 🔥 FORCE SAVE 🔥
        flag_modified(user, "preferences")
        
        try:
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        
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
            pass 
            
    user_history = query.order_by(History.created_at.desc()).all()
    return render_template('history.html', history=user_history, selected_date=selected_date)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
