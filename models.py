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
    can_assign_tasks = db.Column(db.Boolean, default=False, nullable=False)
    can_create_groups = db.Column(db.Boolean, default=False, nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    google_calendar_token = db.Column(db.Text)
    last_sync = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to tasks assigned to this user
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to_id', backref='assigned_user', lazy=True)
    
    def calculate_next_level_points(self):
        """Calcular puntos necesarios para el siguiente nivel"""
        return ((self.level) ** 2) * 100
    
    def get_level_progress(self):
        """Obtener progreso hacia el siguiente nivel (0-100)"""
        next_level_points = self.calculate_next_level_points()
        if next_level_points == 0:
            return 100
        return min(100, (self.points / next_level_points * 100))
    
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

# Tabla de asociación para usuarios y grupos
user_group_membership = db.Table('user_group_membership',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('work_group.id'), primary_key=True),
    db.Column('role', db.String(20), default='member'),  # admin, member
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)

# Tabla de asociación para tareas y múltiples usuarios asignados
task_assignments = db.Table('task_assignments',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow),
    db.Column('status', db.String(20), default='pending')  # pending, accepted, completed
)

class WorkGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_private = db.Column(db.Boolean, default=True, nullable=False)
    password_hash = db.Column(db.String(256))  # Contraseña hasheada del grupo
    invite_token = db.Column(db.String(128), unique=True)  # Token único para invitaciones
    max_members = db.Column(db.Integer, default=50)
    allow_member_invite = db.Column(db.Boolean, default=False)  # Si los miembros pueden invitar
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.relationship('User', backref='created_groups')
    
    # Relación many-to-many con usuarios
    members = db.relationship('User', secondary=user_group_membership, 
                            backref=db.backref('groups', lazy='dynamic'))
    
    def __repr__(self):
        return f'<WorkGroup {self.name}>'
    
    def is_member(self, user):
        return user in self.members
    
    def is_admin(self, user):
        # El administrador del sistema puede ver todos los grupos
        if user.is_admin:
            return True
        # El creador del grupo es admin
        if user.id == self.created_by_id:
            return True
        # Verificar si tiene rol de admin en el grupo
        membership = db.session.query(user_group_membership).filter_by(
            user_id=user.id, group_id=self.id
        ).first()
        return membership and membership.role == 'admin'
    
    def check_password(self, password):
        """Verificar contraseña del grupo"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def set_password(self, password):
        """Establecer contraseña del grupo"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def generate_invite_token(self):
        """Generar token único para invitaciones"""
        import secrets
        self.invite_token = secrets.token_urlsafe(32)
        
    def get_invite_link(self, base_url):
        """Obtener link de invitación completo"""
        return f"{base_url}/group/join/{self.invite_token}"

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='fa-trophy')
    points_required = db.Column(db.Integer, default=0)
    tasks_required = db.Column(db.Integer, default=0)
    level_required = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Achievement {self.name}>'

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref='user_achievements')
    achievement = db.relationship('Achievement', backref='user_achievements')
    
    def __repr__(self):
        return f'<UserAchievement {self.user.username} - {self.achievement.name}>'

class OfflineAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # create_task, update_task, etc.
    action_data = db.Column(db.Text, nullable=False)  # JSON data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    synced = db.Column(db.Boolean, default=False)
    synced_at = db.Column(db.DateTime)
    
    # Relaciones
    user = db.relationship('User', backref='offline_actions')
    
    def __repr__(self):
        return f'<OfflineAction {self.action_type} by {self.user.username}>'
