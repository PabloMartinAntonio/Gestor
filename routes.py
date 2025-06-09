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
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
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
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
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
            flash('La fecha de inicio no puede ser posterior a la fecha de fin', 'error')
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
        
        flash('¡Tarea creada exitosamente!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('task_form.html', users=users, task=None)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check permissions
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        flash('Acceso denegado.', 'error')
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
            flash('La fecha de inicio no puede ser posterior a la fecha de fin', 'error')
            users = User.query.filter_by(is_admin=False).all() if current_user.is_admin else []
            return render_template('task_form.html', task=task, users=users)
        
        db.session.commit()
        flash('¡Tarea actualizada exitosamente!', 'success')
        
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
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(task)
    db.session.commit()
    
    flash('¡Tarea eliminada exitosamente!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/assign_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def assign_task(task_id):
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
        return redirect(url_for('dashboard'))
    
    task = Task.query.get_or_404(task_id)
    
    if request.method == 'POST':
        assigned_to_id = request.form.get('assigned_to_id')
        task.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('¡Asignación de tarea actualizada exitosamente!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('assign_task.html', task=task, users=users)

@app.route('/update_task_status/<int:task_id>', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check permissions
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        flash('Acceso denegado.', 'error')
        return redirect(url_for('dashboard'))
    
    new_status = request.form['status']
    task.status = new_status
    task.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('¡Estado de la tarea actualizado exitosamente!', 'success')
    
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/database_admin')
@login_required
def database_admin():
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
        return redirect(url_for('dashboard'))
    
    # Obtener estadísticas
    stats = {
        'total_users': User.query.count(),
        'total_tasks': Task.query.count(),
        'completed_tasks': Task.query.filter_by(status='completed').count(),
        'admin_users': User.query.filter_by(is_admin=True).count()
    }
    
    # Obtener todos los usuarios y tareas
    users = User.query.order_by(User.created_at.desc()).all()
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    
    # Información de la base de datos
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    if db_url.startswith('postgresql'):
        db_type = 'PostgreSQL'
        db_url_masked = db_url.split('@')[0] + '@***'
    else:
        db_type = 'SQLite'
        db_url_masked = 'sqlite:///tasks.db'
    
    db_info = {
        'type': db_type,
        'url_masked': db_url_masked,
        'last_update': datetime.utcnow().strftime('%d/%m/%Y %H:%M')
    }
    
    return render_template('database_admin.html', 
                         stats=stats, users=users, tasks=tasks, db_info=db_info)

# API endpoints para administración de base de datos
@app.route('/api/toggle_user_role/<int:user_id>', methods=['POST'])
@login_required
def api_toggle_user_role(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    user = User.query.get_or_404(user_id)
    
    # No permitir que el usuario se quite admin a sí mismo si es el único admin
    if user.id == current_user.id and user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({
                'success': False, 
                'message': 'No podés quitarte privilegios de administrador siendo el único admin'
            })
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    action = 'otorgados' if user.is_admin else 'quitados'
    return jsonify({
        'success': True, 
        'message': f'Privilegios de administrador {action} a {user.username}'
    })

@app.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
@login_required
def api_delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    user = User.query.get_or_404(user_id)
    
    # No permitir eliminar el propio usuario
    if user.id == current_user.id:
        return jsonify({
            'success': False, 
            'message': 'No podés eliminar tu propio usuario'
        })
    
    # Verificar si es el único admin
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({
                'success': False, 
                'message': 'No podés eliminar el único administrador del sistema'
            })
    
    # Reasignar tareas creadas por este usuario al admin actual
    tasks_created = Task.query.filter_by(created_by_id=user.id).all()
    for task in tasks_created:
        task.created_by_id = current_user.id
    
    # Desasignar tareas asignadas a este usuario
    tasks_assigned = Task.query.filter_by(assigned_to_id=user.id).all()
    for task in tasks_assigned:
        task.assigned_to_id = None
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Usuario {username} eliminado exitosamente'
    })

@app.route('/api/delete_task/<int:task_id>', methods=['DELETE'])
@login_required
def api_delete_task(task_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    task = Task.query.get_or_404(task_id)
    title = task.title
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Tarea "{title}" eliminada exitosamente'
    })

@app.route('/api/create_backup', methods=['POST'])
@login_required
def api_create_backup():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        import json
        from datetime import datetime
        
        # Crear backup de usuarios
        users_data = []
        for user in User.query.all():
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat()
            })
        
        # Crear backup de tareas
        tasks_data = []
        for task in Task.query.all():
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'start_date': task.start_date.isoformat() if task.start_date else None,
                'end_date': task.end_date.isoformat() if task.end_date else None,
                'status': task.status,
                'priority': task.priority,
                'created_by_id': task.created_by_id,
                'assigned_to_id': task.assigned_to_id,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat()
            })
        
        backup_data = {
            'backup_date': datetime.utcnow().isoformat(),
            'version': '1.0',
            'users': users_data,
            'tasks': tasks_data
        }
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_tareas_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True, 
            'message': f'Backup creado exitosamente: {filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error al crear backup: {str(e)}'
        })

@app.route('/api/clean_old_tasks', methods=['POST'])
@login_required
def api_clean_old_tasks():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        from datetime import datetime, timedelta
        
        # Eliminar tareas completadas de más de 30 días
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_tasks = Task.query.filter(
            Task.status == 'completed',
            Task.updated_at < cutoff_date
        ).all()
        
        count = len(old_tasks)
        for task in old_tasks:
            db.session.delete(task)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Se eliminaron {count} tareas completadas antiguas'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error al limpiar tareas: {str(e)}'
        })

@app.route('/api/execute_sql', methods=['POST'])
@login_required
def api_execute_sql():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        # Validar que sea una consulta SELECT
        if not query.lower().startswith('select'):
            return jsonify({
                'success': False, 
                'message': 'Solo se permiten consultas SELECT'
            })
        
        # Ejecutar consulta
        from sqlalchemy import text
        result = db.session.execute(text(query))
        rows = result.fetchall()
        columns = list(result.keys()) if rows else []
        
        # Convertir resultados a formato JSON serializable
        results = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convertir datetime a string
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                row_dict[col] = value
            results.append(row_dict)
        
        return jsonify({
            'success': True,
            'results': results,
            'columns': columns,
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error en la consulta: {str(e)}'
        })
