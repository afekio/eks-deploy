from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Establish a relationship to the user's files
    deployments = db.relationship('DeploymentHistory', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class DeploymentHistory(db.Model):
    __tablename__ = 'deployment_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    file_name = db.Column(db.String(255), nullable=False) # e.g., "app-server_20260320_1530.tf"
    file_type = db.Column(db.String(50), nullable=False)  # "terraform" or "json"
    file_content = db.Column(db.Text, nullable=False)     # The actual string/json payload
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        """Helper to return the data cleanly to the React frontend (excluding content for lists)"""
        return {
            'id': self.id,
            'fileName': self.file_name,
            'fileType': self.file_type,
            'createdAt': self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }