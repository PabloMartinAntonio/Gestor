from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from models import User, Task

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=False
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('¡Registro exitoso! Por favor iniciá sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get tasks assigned to current user
    status_filter = request.args.get('status', 'all')
    
    query = Task.query.filter_by(assigned_to_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    tasks = query.order_by(Task.created_at.desc()).all()
    
    return render_template('dashboard.html', tasks=tasks, status_filter=status_filter)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all tasks with filtering
    status_filter = request.args.get('status', 'all')
    user_filter = request.args.get('user', 'all')
    
    query = Task.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if user_filter != 'all':
        if user_filter == 'unassigned':
            query = query.filter_by(assigned_to_id=None)
        else:
            query = query.filter_by(assigned_to_id=int(user_filter))
    
    tasks = query.order_by(Task.created_at.desc()).all()
    users = User.query.filter_by(is_admin=False).all()
    
    return render_template('admin_dashboard.html', tasks=tasks, users=users, 
                         status_filter=status_filter, user_filter=user_filter)

@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        priority = request.form['priority']
        assigned_to_id = request.form.get('assigned_to_id')
        
        # Convert date strings to date objects
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        
        # Validation
        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            flash('Start date cannot be after end date', 'error')
            return render_template('task_form.html', users=User.query.filter_by(is_admin=False).all())
        
        task = Task(
            title=title,
            description=description,
            start_date=start_date_obj,
            end_date=end_date_obj,
            priority=priority,
            assigned_to_id=int(assigned_to_id) if assigned_to_id else None,
            created_by_id=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Task created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('task_form.html', users=users, task=None)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check permissions
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        
        task.start_date = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
        task.end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        
        # Only admins can change priority and assignment
        if current_user.is_admin:
            task.priority = request.form['priority']
            assigned_to_id = request.form.get('assigned_to_id')
            task.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        
        # Users can update status
        if 'status' in request.form:
            task.status = request.form['status']
        
        task.updated_at = datetime.utcnow()
        
        # Validation
        if task.start_date and task.end_date and task.start_date > task.end_date:
            flash('Start date cannot be after end date', 'error')
            users = User.query.filter_by(is_admin=False).all() if current_user.is_admin else []
            return render_template('task_form.html', task=task, users=users)
        
        db.session.commit()
        flash('Task updated successfully!', 'success')
        
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    users = User.query.filter_by(is_admin=False).all() if current_user.is_admin else []
    return render_template('task_form.html', task=task, users=users)

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Only admins can delete tasks
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(task)
    db.session.commit()
    
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/assign_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def assign_task(task_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    task = Task.query.get_or_404(task_id)
    
    if request.method == 'POST':
        assigned_to_id = request.form.get('assigned_to_id')
        task.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Task assignment updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('assign_task.html', task=task, users=users)

@app.route('/update_task_status/<int:task_id>', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check permissions
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    new_status = request.form['status']
    task.status = new_status
    task.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Task status updated successfully!', 'success')
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('dashboard'))
