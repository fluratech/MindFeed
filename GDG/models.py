from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # Store preferences: { "topics": [{"id": "Tech", "interest": 80}], "summary_length": "concise", "reading_time": "5" }
    preferences = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to history
    history = db.relationship('History', backref='user', lazy=True)

class History(db.Model):
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    summary_date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    content = db.Column(db.Text, nullable=False)  # The AI generated summary
    meta_data = db.Column(db.JSON) # Snapshot of preferences used for this generation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
