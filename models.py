from datetime import datetime
from app import db
from flask_login import UserMixin
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to tasks assigned to this user
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to_id', backref='assigned_user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, in_progress, completed
    priority = db.Column(db.String(10), default='medium', nullable=False)  # low, medium, high
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key to user who is assigned this task
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Foreign key to user who created this task (admin)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    @property
    def status_badge_class(self):
        status_classes = {
            'pending': 'bg-warning',
            'in_progress': 'bg-info',
            'completed': 'bg-success'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @property
    def priority_badge_class(self):
        priority_classes = {
            'low': 'bg-secondary',
            'medium': 'bg-primary',
            'high': 'bg-danger'
        }
        return priority_classes.get(self.priority, 'bg-secondary')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # task_assigned, status_change, deadline, task_created
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='notifications')
    
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    task = db.relationship('Task', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.title}>'
