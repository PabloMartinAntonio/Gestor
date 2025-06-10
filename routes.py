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
        
        # Generar notificación para el usuario asignado
        if task.assigned_to_id:
            notify_task_creation(task, current_user)
        
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
        old_assigned_id = task.assigned_to_id
        assigned_to_id = request.form.get('assigned_to_id')
        new_assigned_id = int(assigned_to_id) if assigned_to_id else None
        task.assigned_to_id = new_assigned_id
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Generar notificación por asignación de tarea
        if old_assigned_id != new_assigned_id and new_assigned_id:
            assigned_user = User.query.get(new_assigned_id)
            notify_task_assignment(task, assigned_user, current_user)
        
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
    
    old_status = task.status
    new_status = request.form['status']
    task.status = new_status
    task.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # Generar notificación por cambio de estado
    if old_status != new_status:
        notify_status_change(task, old_status, new_status, current_user)
    
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

# Funciones auxiliares para notificaciones
def create_notification(user_id, title, message, notification_type, task_id=None):
    """Crear una nueva notificación para un usuario"""
    from models import Notification
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        task_id=task_id
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def notify_task_assignment(task, assigned_user, assigned_by):
    """Notificar cuando se asigna una tarea"""
    if assigned_user:
        title = "Nueva tarea asignada"
        message = f"{assigned_by.username} te asignó la tarea '{task.title}'"
        create_notification(assigned_user.id, title, message, 'task_assigned', task.id)

def notify_status_change(task, old_status, new_status, changed_by):
    """Notificar cuando cambia el estado de una tarea"""
    status_names = {
        'pending': 'Pendiente',
        'in_progress': 'En Progreso', 
        'completed': 'Completada'
    }
    
    # Notificar al creador de la tarea
    if task.created_by_id != changed_by.id:
        title = "Estado de tarea actualizado"
        message = f"{changed_by.username} cambió el estado de '{task.title}' de {status_names.get(old_status, old_status)} a {status_names.get(new_status, new_status)}"
        create_notification(task.created_by_id, title, message, 'status_change', task.id)
    
    # Notificar al usuario asignado si es diferente
    if task.assigned_to_id and task.assigned_to_id != changed_by.id and task.assigned_to_id != task.created_by_id:
        title = "Estado de tu tarea actualizado"
        message = f"El estado de tu tarea '{task.title}' cambió a {status_names.get(new_status, new_status)}"
        create_notification(task.assigned_to_id, title, message, 'status_change', task.id)

def notify_task_creation(task, created_by):
    """Notificar cuando se crea una nueva tarea"""
    if task.assigned_to_id and task.assigned_to_id != created_by.id:
        title = "Nueva tarea creada y asignada"
        message = f"{created_by.username} creó y te asignó la tarea '{task.title}'"
        create_notification(task.assigned_to_id, title, message, 'task_created', task.id)

def check_upcoming_deadlines():
    """Verificar y notificar sobre fechas límite próximas"""
    from datetime import datetime, timedelta
    tomorrow = datetime.utcnow().date() + timedelta(days=1)
    
    # Buscar tareas que vencen mañana y no están completadas
    upcoming_tasks = Task.query.filter(
        Task.end_date == tomorrow,
        Task.status != 'completed'
    ).all()
    
    for task in upcoming_tasks:
        # Verificar si ya se envió esta notificación
        from models import Notification
        existing = Notification.query.filter(
            Notification.task_id == task.id,
            Notification.type == 'deadline',
            Notification.created_at >= datetime.utcnow().date()
        ).first()
        
        if not existing:
            if task.assigned_to_id:
                title = "Fecha límite próxima"
                message = f"La tarea '{task.title}' vence mañana"
                create_notification(task.assigned_to_id, title, message, 'deadline', task.id)
            
            # También notificar al creador si es diferente
            if task.created_by_id != task.assigned_to_id:
                title = "Fecha límite próxima"
                message = f"La tarea '{task.title}' que creaste vence mañana"
                create_notification(task.created_by_id, title, message, 'deadline', task.id)

# Rutas para notificaciones
@app.route('/notifications')
@login_required
def notifications():
    from models import Notification
    
    filter_type = request.args.get('filter', 'all')
    type_filter = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)
    
    # Construir consulta base
    query = Notification.query.filter_by(user_id=current_user.id)
    
    # Aplicar filtros
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)
    
    if type_filter != 'all':
        query = query.filter_by(type=type_filter)
    
    # Ordenar por fecha (más recientes primero)
    query = query.order_by(Notification.created_at.desc())
    
    # Paginación
    notifications = query.paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Contar notificaciones no leídas
    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    return render_template('notifications.html',
                         notifications=notifications,
                         unread_count=unread_count,
                         filter_type=filter_type,
                         type_filter=type_filter)

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    from models import Notification
    notification = Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first_or_404()
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Notificación marcada como leída'
    })

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_notifications_read():
    from models import Notification
    notifications = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).all()
    
    count = len(notifications)
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{count} notificaciones marcadas como leídas'
    })

@app.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def api_delete_notification(notification_id):
    from models import Notification
    notification = Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Notificación eliminada'
    })

@app.route('/api/notifications/count')
@login_required
def api_notification_count():
    from models import Notification
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    return jsonify({'count': count})

# Función de tarea en segundo plano para verificar fechas límite
@app.route('/api/check_deadlines', methods=['POST'])
@login_required
def api_check_deadlines():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    check_upcoming_deadlines()
    return jsonify({
        'success': True,
        'message': 'Verificación de fechas límite completada'
    })

# Función para generar notificaciones de ejemplo
@app.route('/api/generate_sample_notifications', methods=['POST'])
@login_required
def api_generate_sample_notifications():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        # Crear algunas notificaciones de ejemplo para demostrar el sistema
        sample_notifications = [
            {
                'title': 'Bienvenido al sistema de notificaciones',
                'message': 'Este es un ejemplo de notificación del sistema. Aquí recibirás actualizaciones sobre tus tareas.',
                'type': 'task_created'
            },
            {
                'title': 'Función de notificaciones activada',
                'message': 'Las notificaciones automáticas están funcionando correctamente. Te avisaremos sobre cambios en tus tareas.',
                'type': 'status_change'
            }
        ]
        
        count = 0
        for notif in sample_notifications:
            create_notification(
                user_id=current_user.id,
                title=notif['title'],
                message=notif['message'],
                notification_type=notif['type']
            )
            count += 1
        
        return jsonify({
            'success': True,
            'message': f'Se generaron {count} notificaciones de ejemplo'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al generar notificaciones: {str(e)}'
        })

# Ruta para análisis y estadísticas
@app.route('/analytics')
@login_required
def analytics():
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
        return redirect(url_for('dashboard'))
    
    from models import Notification
    from datetime import datetime, timedelta
    
    # Métricas principales
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()
    in_progress_tasks = Task.query.filter_by(status='in_progress').count()
    pending_tasks = Task.query.filter_by(status='pending').count()
    
    # Tareas vencidas
    today = datetime.utcnow().date()
    overdue_tasks = Task.query.filter(
        Task.end_date < today,
        Task.status != 'completed'
    ).count()
    
    # Calcular tasas
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    in_progress_rate = (in_progress_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Tareas creadas esta semana
    week_ago = datetime.utcnow() - timedelta(days=7)
    tasks_this_week = Task.query.filter(Task.created_at >= week_ago).count()
    
    metrics = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_rate': completion_rate,
        'in_progress_rate': in_progress_rate,
        'tasks_change': tasks_this_week
    }
    
    # Estadísticas por usuario
    users = User.query.all()
    user_stats = []
    
    for user in users:
        assigned_tasks = Task.query.filter_by(assigned_to_id=user.id).all()
        total_assigned = len(assigned_tasks)
        
        if total_assigned > 0:
            completed = len([t for t in assigned_tasks if t.status == 'completed'])
            in_progress = len([t for t in assigned_tasks if t.status == 'in_progress'])
            pending = len([t for t in assigned_tasks if t.status == 'pending'])
            user_completion_rate = (completed / total_assigned * 100)
            
            # Calcular tiempo promedio de finalización
            completed_tasks_with_dates = [t for t in assigned_tasks if t.status == 'completed' and t.start_date and t.updated_at]
            if completed_tasks_with_dates:
                total_days = sum([(t.updated_at.date() - t.start_date).days for t in completed_tasks_with_dates])
                avg_completion_time = total_days / len(completed_tasks_with_dates)
            else:
                avg_completion_time = 0
            
            user_stats.append({
                'username': user.username,
                'is_admin': user.is_admin,
                'total_assigned': total_assigned,
                'completed': completed,
                'in_progress': in_progress,
                'pending': pending,
                'completion_rate': user_completion_rate,
                'avg_completion_time': round(avg_completion_time, 1)
            })
    
    # Datos para gráficos
    chart_data = {
        'weeks': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'],
        'created': [8, 12, 10, tasks_this_week],
        'completed': [6, 9, 8, completed_tasks // 4],
        'high_priority': Task.query.filter_by(priority='high').count(),
        'medium_priority': Task.query.filter_by(priority='medium').count(),
        'low_priority': Task.query.filter_by(priority='low').count(),
        'status_labels': ['Pendiente', 'En Progreso', 'Completada'],
        'status_data': [pending_tasks, in_progress_tasks, completed_tasks]
    }
    
    # Actividad reciente
    recent_activities = []
    recent_tasks = Task.query.order_by(Task.updated_at.desc()).limit(5).all()
    
    for task in recent_tasks:
        if task.status == 'completed':
            color = 'success'
            icon = 'fa-check'
            title = 'Tarea Completada'
        elif task.status == 'in_progress':
            color = 'warning'
            icon = 'fa-spinner'
            title = 'Tarea en Progreso'
        else:
            color = 'secondary'
            icon = 'fa-clock'
            title = 'Tarea Pendiente'
        
        recent_activities.append({
            'title': title,
            'description': f'{task.title} - {task.assigned_user.username if task.assigned_user else "Sin asignar"}',
            'timestamp': task.updated_at,
            'color': color,
            'icon': icon
        })
    
    # Alertas y recomendaciones
    alerts = []
    
    if overdue_tasks > 0:
        alerts.append({
            'type': 'danger',
            'icon': 'fa-exclamation-triangle',
            'title': 'Tareas Vencidas',
            'message': f'Hay {overdue_tasks} tareas vencidas que requieren atención inmediata.'
        })
    
    if completion_rate < 70:
        alerts.append({
            'type': 'warning',
            'icon': 'fa-chart-line',
            'title': 'Tasa de Finalización Baja',
            'message': f'La tasa de finalización es del {completion_rate:.1f}%. Considerá revisar la carga de trabajo.'
        })
    
    unread_notifications = Notification.query.filter_by(is_read=False).count()
    if unread_notifications > 10:
        alerts.append({
            'type': 'info',
            'icon': 'fa-bell',
            'title': 'Muchas Notificaciones Pendientes',
            'message': f'Hay {unread_notifications} notificaciones sin leer en el sistema.'
        })
    
    if not alerts:
        alerts.append({
            'type': 'success',
            'icon': 'fa-thumbs-up',
            'title': 'Todo en Orden',
            'message': 'El sistema está funcionando correctamente sin alertas.'
        })
    
    return render_template('analytics.html',
                         metrics=metrics,
                         user_stats=user_stats,
                         chart_data=chart_data,
                         recent_activities=recent_activities,
                         alerts=alerts)

@app.route('/api/export_analytics_report', methods=['POST'])
@login_required
def api_export_analytics_report():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        import json
        from datetime import datetime
        
        # Generar reporte completo
        total_tasks = Task.query.count()
        completed_tasks = Task.query.filter_by(status='completed').count()
        
        report_data = {
            'generated_at': datetime.utcnow().isoformat(),
            'report_type': 'analytics_summary',
            'metrics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                'total_users': User.query.count(),
                'admin_users': User.query.filter_by(is_admin=True).count()
            },
            'tasks_by_status': {
                'pending': Task.query.filter_by(status='pending').count(),
                'in_progress': Task.query.filter_by(status='in_progress').count(),
                'completed': completed_tasks
            },
            'tasks_by_priority': {
                'high': Task.query.filter_by(priority='high').count(),
                'medium': Task.query.filter_by(priority='medium').count(),
                'low': Task.query.filter_by(priority='low').count()
            }
        }
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_analytics_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': f'Reporte de análisis exportado: {filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al exportar reporte: {str(e)}'
        })

# Funciones de gamificación
def calculate_points_for_task(task, completion_time_days=None):
    """Calcular puntos por completar una tarea"""
    base_points = 10
    
    # Puntos por prioridad
    priority_multiplier = {'low': 1, 'medium': 1.5, 'high': 2}
    points = base_points * priority_multiplier.get(task.priority, 1)
    
    # Bonificación por completar antes de tiempo
    if completion_time_days and task.end_date:
        days_early = (task.end_date - datetime.utcnow().date()).days
        if days_early > 0:
            points += days_early * 2
    
    return int(points)

def check_and_award_achievements(user):
    """Verificar y otorgar logros al usuario"""
    from models import Achievement, UserAchievement
    
    # Obtener logros no obtenidos
    earned_achievement_ids = [ua.achievement_id for ua in user.user_achievements]
    available_achievements = Achievement.query.filter(
        Achievement.is_active == True,
        ~Achievement.id.in_(earned_achievement_ids)
    ).all()
    
    new_achievements = []
    
    for achievement in available_achievements:
        eligible = True
        
        # Verificar requisitos de puntos
        if achievement.points_required > 0 and user.points < achievement.points_required:
            eligible = False
        
        # Verificar requisitos de nivel
        if achievement.level_required > user.level:
            eligible = False
        
        # Verificar requisitos de tareas
        if achievement.tasks_required > 0:
            completed_tasks = Task.query.filter_by(
                assigned_to_id=user.id, status='completed'
            ).count()
            if completed_tasks < achievement.tasks_required:
                eligible = False
        
        if eligible:
            user_achievement = UserAchievement(
                user_id=user.id,
                achievement_id=achievement.id
            )
            db.session.add(user_achievement)
            new_achievements.append(achievement)
    
    if new_achievements:
        db.session.commit()
        # Crear notificaciones por logros
        for achievement in new_achievements:
            create_notification(
                user.id,
                f"¡Logro Desbloqueado!",
                f"Has desbloqueado el logro '{achievement.name}': {achievement.description}",
                'achievement'
            )
    
    return new_achievements

def update_user_level(user):
    """Actualizar nivel del usuario basado en puntos"""
    # Fórmula: Nivel = sqrt(puntos / 100) + 1
    import math
    new_level = int(math.sqrt(user.points / 100)) + 1
    
    if new_level > user.level:
        old_level = user.level
        user.level = new_level
        db.session.commit()
        
        # Notificar subida de nivel
        create_notification(
            user.id,
            f"¡Subiste de Nivel!",
            f"¡Felicitaciones! Subiste del nivel {old_level} al nivel {new_level}",
            'level_up'
        )
    
    return user.level

# Rutas de gamificación
@app.route('/gamification')
@login_required
def gamification():
    from models import Achievement, UserAchievement
    
    # Estadísticas del usuario
    total_tasks = Task.query.filter_by(assigned_to_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(
        assigned_to_id=current_user.id, status='completed'
    ).count()
    achievements_count = len(current_user.user_achievements)
    groups_count = current_user.groups.count()
    
    user_stats = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'achievements_count': achievements_count,
        'groups_count': groups_count
    }
    
    # Calcular progreso al siguiente nivel
    next_level_points = ((current_user.level) ** 2) * 100
    points_to_next_level = max(0, next_level_points - current_user.points)
    level_progress = min(100, (current_user.points / next_level_points * 100)) if next_level_points > 0 else 100
    
    # Ranking de usuarios
    users_ranking = User.query.order_by(User.points.desc()).limit(10).all()
    leaderboard = [(i+1, user) for i, user in enumerate(users_ranking)]
    
    # Logros recientes
    recent_achievements = db.session.query(UserAchievement, Achievement).join(
        Achievement
    ).filter(
        UserAchievement.user_id == current_user.id
    ).order_by(UserAchievement.earned_at.desc()).limit(5).all()
    
    recent_achievements = [
        {
            'name': ach.name,
            'description': ach.description,
            'icon': ach.icon,
            'earned_at': ua.earned_at
        }
        for ua, ach in recent_achievements
    ]
    
    # Todos los logros con estado
    all_achievements = Achievement.query.filter_by(is_active=True).all()
    earned_ids = [ua.achievement_id for ua in current_user.user_achievements]
    
    achievements_with_status = []
    for achievement in all_achievements:
        is_earned = achievement.id in earned_ids
        
        # Calcular progreso actual
        current_tasks = 0
        if achievement.tasks_required > 0:
            current_tasks = Task.query.filter_by(
                assigned_to_id=current_user.id, status='completed'
            ).count()
        
        earned_date = None
        if is_earned:
            user_ach = next((ua for ua in current_user.user_achievements 
                           if ua.achievement_id == achievement.id), None)
            if user_ach:
                earned_date = user_ach.earned_at
        
        achievements_with_status.append({
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'icon': achievement.icon,
            'points_required': achievement.points_required,
            'tasks_required': achievement.tasks_required,
            'level_required': achievement.level_required,
            'is_earned': is_earned,
            'current_tasks': current_tasks,
            'earned_date': earned_date
        })
    
    return render_template('gamification.html',
                         user_stats=user_stats,
                         next_level_points=next_level_points,
                         points_to_next_level=points_to_next_level,
                         level_progress=level_progress,
                         leaderboard=leaderboard,
                         recent_achievements=recent_achievements,
                         all_achievements=achievements_with_status)

# Rutas de grupos de trabajo
@app.route('/groups')
@login_required
def groups():
    from models import WorkGroup
    
    # Grupos donde es miembro
    my_groups = current_user.groups.all()
    
    # Grupos creados por el usuario
    created_groups = []
    if current_user.can_create_groups or current_user.is_admin:
        created_groups = WorkGroup.query.filter_by(created_by_id=current_user.id).all()
    
    # Invitaciones pendientes (simulado por ahora)
    pending_invitations = []
    
    return render_template('groups.html',
                         my_groups=my_groups,
                         created_groups=created_groups,
                         pending_invitations=pending_invitations)

@app.route('/api/groups/create', methods=['POST'])
@login_required
def api_create_group():
    if not (current_user.can_create_groups or current_user.is_admin):
        return jsonify({'success': False, 'message': 'No tenés permisos para crear grupos'})
    
    try:
        from models import WorkGroup
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('name'):
            return jsonify({'success': False, 'message': 'El nombre del grupo es requerido'})
        
        if data.get('is_private', True) and not data.get('password'):
            return jsonify({'success': False, 'message': 'Los grupos privados requieren contraseña'})

        group = WorkGroup(
            name=data['name'],
            description=data.get('description', ''),
            is_private=data.get('is_private', True),
            max_members=int(data.get('max_members', 50)),
            allow_member_invite=data.get('allow_member_invite', False),
            created_by_id=current_user.id
        )
        
        # Establecer contraseña si el grupo es privado
        if data.get('password'):
            group.set_password(data['password'])
        
        # Generar token de invitación
        group.generate_invite_token()
        
        db.session.add(group)
        db.session.flush()  # Para obtener el ID
        
        # Agregar al creador como miembro administrador
        group.members.append(current_user)
        
        db.session.commit()
        
        # Crear notificación
        create_notification(
            current_user.id,
            'Grupo Creado',
            f'Tu grupo "{group.name}" fue creado exitosamente',
            'group_created'
        )
        
        return jsonify({
            'success': True,
            'message': f'Grupo "{group.name}" creado exitosamente',
            'group_id': group.id,
            'invite_link': group.get_invite_link(request.url_root.rstrip('/'))
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al crear grupo: {str(e)}'
        })

@app.route('/group/<int:group_id>')
@login_required
def group_detail(group_id):
    from models import WorkGroup
    group = WorkGroup.query.get_or_404(group_id)
    
    # Verificar acceso
    if not group.is_member(current_user) and not current_user.is_admin:
        flash('No tenés acceso a este grupo', 'error')
        return redirect(url_for('groups'))
    
    # Tareas del grupo
    group_tasks = Task.query.filter(
        Task.assigned_to_id.in_([m.id for m in group.members])
    ).order_by(Task.created_at.desc()).all()
    
    return render_template('group_detail.html', group=group, tasks=group_tasks)

# Modificar la función de completar tareas para incluir gamificación
@app.route('/api/complete_task/<int:task_id>', methods=['POST'])
@login_required
def api_complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Verificar permisos
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    if task.status == 'completed':
        return jsonify({'success': False, 'message': 'La tarea ya está completada'})
    
    old_status = task.status
    task.status = 'completed'
    task.updated_at = datetime.utcnow()
    
    # Calcular puntos y otorgarlos
    if task.assigned_to_id:
        assigned_user = User.query.get(task.assigned_to_id)
        if assigned_user:
            completion_days = None
            if task.start_date:
                completion_days = (datetime.utcnow().date() - task.start_date).days
            
            points_earned = calculate_points_for_task(task, completion_days)
            assigned_user.points += points_earned
            
            # Actualizar nivel
            update_user_level(assigned_user)
            
            # Verificar logros
            new_achievements = check_and_award_achievements(assigned_user)
            
            db.session.commit()
            
            # Notificar puntos ganados
            create_notification(
                assigned_user.id,
                "¡Puntos Ganados!",
                f"Ganaste {points_earned} puntos por completar '{task.title}'",
                'points_earned'
            )
            
            # Notificar cambio de estado
            if old_status != 'completed':
                notify_status_change(task, old_status, 'completed', current_user)
            
            achievement_msg = ""
            if new_achievements:
                achievement_msg = f" ¡También desbloqueaste {len(new_achievements)} logro(s)!"
            
            return jsonify({
                'success': True,
                'message': f'Tarea completada. +{points_earned} puntos{achievement_msg}',
                'points_earned': points_earned,
                'new_achievements': [ach.name for ach in new_achievements]
            })
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Tarea completada'})

# Modo offline - guardar acciones para sincronizar
@app.route('/api/offline/store_action', methods=['POST'])
@login_required
def api_store_offline_action():
    try:
        from models import OfflineAction
        import json
        
        data = request.get_json()
        
        offline_action = OfflineAction(
            user_id=current_user.id,
            action_type=data['action_type'],
            action_data=json.dumps(data['action_data'])
        )
        
        db.session.add(offline_action)
        db.session.commit()
        
        return jsonify({'success': True, 'action_id': offline_action.id})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Sincronización de acciones offline
@app.route('/api/offline/sync', methods=['POST'])
@login_required
def api_sync_offline_actions():
    try:
        from models import OfflineAction
        import json
        
        # Obtener acciones no sincronizadas
        unsynced_actions = OfflineAction.query.filter_by(
            user_id=current_user.id, synced=False
        ).order_by(OfflineAction.created_at).all()
        
        synced_count = 0
        
        for action in unsynced_actions:
            try:
                action_data = json.loads(action.action_data)
                
                # Procesar según el tipo de acción
                if action.action_type == 'update_task_status':
                    task = Task.query.get(action_data['task_id'])
                    if task and (current_user.is_admin or task.assigned_to_id == current_user.id):
                        old_status = task.status
                        task.status = action_data['status']
                        task.updated_at = datetime.utcnow()
                        
                        # Si se completó offline, otorgar puntos
                        if action_data['status'] == 'completed' and old_status != 'completed':
                            if task.assigned_to_id == current_user.id:
                                points_earned = calculate_points_for_task(task)
                                current_user.points += points_earned
                                update_user_level(current_user)
                                check_and_award_achievements(current_user)
                
                elif action.action_type == 'create_task':
                    if current_user.is_admin or current_user.can_assign_tasks:
                        task = Task(
                            title=action_data['title'],
                            description=action_data.get('description', ''),
                            priority=action_data.get('priority', 'medium'),
                            assigned_to_id=action_data.get('assigned_to_id'),
                            created_by_id=current_user.id
                        )
                        
                        if action_data.get('start_date'):
                            task.start_date = datetime.strptime(action_data['start_date'], '%Y-%m-%d').date()
                        if action_data.get('end_date'):
                            task.end_date = datetime.strptime(action_data['end_date'], '%Y-%m-%d').date()
                        
                        db.session.add(task)
                
                # Marcar como sincronizado
                action.synced = True
                action.synced_at = datetime.utcnow()
                synced_count += 1
                
            except Exception as e:
                print(f"Error sincronizando acción {action.id}: {e}")
                continue
        
        current_user.last_sync = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Se sincronizaron {synced_count} acciones',
            'synced_count': synced_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error en sincronización: {str(e)}'
        })

# Rutas para Google Calendar
@app.route('/calendar')
@login_required
def calendar_integration():
    # Estadísticas de sincronización
    sync_stats = {
        'synced_tasks': Task.query.filter_by(assigned_to_id=current_user.id).count(),
        'calendar_events': Task.query.filter(
            Task.assigned_to_id == current_user.id,
            Task.end_date.isnot(None)
        ).count(),
        'pending_sync': 0
    }
    
    # Tareas sincronizadas recientemente
    recent_synced_tasks = Task.query.filter_by(
        assigned_to_id=current_user.id
    ).order_by(Task.updated_at.desc()).limit(5).all()
    
    return render_template('calendar_integration.html',
                         sync_stats=sync_stats,
                         recent_synced_tasks=recent_synced_tasks)

@app.route('/api/calendar/auth-url')
@login_required
def api_calendar_auth_url():
    # En una implementación real, generaría la URL de OAuth de Google
    # Por ahora simularemos la conexión
    return jsonify({
        'auth_url': f'{request.url_root}api/calendar/callback?code=simulated_auth_code&user_id={current_user.id}'
    })

@app.route('/api/calendar/callback')
@login_required
def api_calendar_callback():
    # Simular recepción del código de autorización
    auth_code = request.args.get('code')
    
    if auth_code:
        # En implementación real, intercambiaría el código por tokens
        current_user.google_calendar_token = f"simulated_token_{current_user.id}"
        current_user.last_sync = datetime.utcnow()
        db.session.commit()
        
        flash('Google Calendar conectado exitosamente', 'success')
        return redirect(url_for('calendar_integration'))
    else:
        flash('Error al conectar Google Calendar', 'error')
        return redirect(url_for('calendar_integration'))

@app.route('/api/calendar/disconnect', methods=['POST'])
@login_required
def api_calendar_disconnect():
    current_user.google_calendar_token = None
    current_user.last_sync = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Google Calendar desconectado exitosamente'
    })

@app.route('/api/calendar/sync', methods=['POST'])
@login_required
def api_calendar_sync():
    if not current_user.google_calendar_token:
        return jsonify({
            'success': False,
            'message': 'Google Calendar no está conectado'
        })
    
    try:
        # Simular sincronización con Google Calendar
        tasks_to_sync = Task.query.filter(
            Task.assigned_to_id == current_user.id,
            Task.end_date.isnot(None)
        ).all()
        
        synced_count = len(tasks_to_sync)
        current_user.last_sync = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Se sincronizaron {synced_count} tareas con Google Calendar'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al sincronizar: {str(e)}'
        })

@app.route('/api/calendar/config', methods=['POST'])
@login_required
def api_calendar_config():
    try:
        data = request.get_json()
        # Guardar configuración (en implementación real se guardaría en base de datos)
        
        return jsonify({
            'success': True,
            'message': 'Configuración de calendario guardada'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al guardar configuración: {str(e)}'
        })

# Modificar Task model para soportar múltiples asignaciones
@app.route('/api/tasks/<int:task_id>/assign_multiple', methods=['POST'])
@login_required
def api_assign_multiple_users(task_id):
    if not (current_user.is_admin or current_user.can_assign_tasks):
        return jsonify({'success': False, 'message': 'No tenés permisos para asignar tareas'})
    
    try:
        from models import task_assignments
        task = Task.query.get_or_404(task_id)
        data = request.get_json()
        user_ids = data.get('user_ids', [])
        
        # Limpiar asignaciones existentes
        db.session.execute(
            task_assignments.delete().where(task_assignments.c.task_id == task_id)
        )
        
        # Agregar nuevas asignaciones
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user:
                db.session.execute(
                    task_assignments.insert().values(
                        task_id=task_id,
                        user_id=user_id,
                        assigned_at=datetime.utcnow()
                    )
                )
                
                # Crear notificación
                notify_task_assignment(task, user, current_user)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tarea asignada a {len(user_ids)} usuarios'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al asignar tarea: {str(e)}'
        })

# Service Worker para modo offline
@app.route('/sw.js')
def service_worker():
    return app.send_static_file('js/sw.js')

# API para obtener datos offline
@app.route('/api/offline/data')
@login_required
def api_offline_data():
    try:
        # Datos necesarios para modo offline
        user_tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()
        user_groups = current_user.groups.all()
        
        offline_data = {
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'points': current_user.points,
                'level': current_user.level
            },
            'tasks': [{
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'start_date': task.start_date.isoformat() if task.start_date else None,
                'end_date': task.end_date.isoformat() if task.end_date else None,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat()
            } for task in user_tasks],
            'groups': [{
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'is_private': group.is_private
            } for group in user_groups],
            'last_sync': datetime.utcnow().isoformat()
        }
        
        return jsonify(offline_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Actualizar permisos de usuario
@app.route('/api/users/<int:user_id>/permissions', methods=['POST'])
@login_required
def api_update_user_permissions(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Solo administradores pueden modificar permisos'})
    
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        # No permitir que se quiten permisos a sí mismo si es el único admin
        if user.id == current_user.id and user.is_admin:
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count <= 1 and not data.get('is_admin', True):
                return jsonify({
                    'success': False,
                    'message': 'No podés quitarte permisos de administrador siendo el único admin'
                })
        
        user.can_assign_tasks = data.get('can_assign_tasks', False)
        user.can_create_groups = data.get('can_create_groups', False)
        
        # Solo admin puede modificar otros admins
        if 'is_admin' in data:
            user.is_admin = data.get('is_admin', False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Permisos de {user.username} actualizados exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al actualizar permisos: {str(e)}'
        })

# Ruta para gestión de permisos
@app.route('/user_permissions')
@login_required
def user_permissions():
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Estadísticas de permisos
    stats = {
        'total_users': len(users),
        'admin_users': len([u for u in users if u.is_admin]),
        'can_assign_users': len([u for u in users if u.can_assign_tasks]),
        'can_create_groups_users': len([u for u in users if u.can_create_groups])
    }
    
    return render_template('user_permissions.html', users=users, stats=stats)

@app.route('/api/users/<int:user_id>/stats')
@login_required
def api_user_stats(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Estadísticas de tareas
        total_tasks = Task.query.filter_by(assigned_to_id=user_id).count()
        completed_tasks = Task.query.filter_by(assigned_to_id=user_id, status='completed').count()
        in_progress_tasks = Task.query.filter_by(assigned_to_id=user_id, status='in_progress').count()
        pending_tasks = Task.query.filter_by(assigned_to_id=user_id, status='pending').count()
        
        # Gamificación
        achievements_count = len(user.user_achievements)
        groups_count = user.groups.count()
        
        # Tareas recientes
        recent_tasks = Task.query.filter_by(assigned_to_id=user_id).order_by(Task.updated_at.desc()).limit(5).all()
        recent_tasks_data = []
        
        for task in recent_tasks:
            status_text = {
                'pending': 'Pendiente',
                'in_progress': 'En Progreso',
                'completed': 'Completada'
            }.get(task.status, task.status)
            
            recent_tasks_data.append({
                'title': task.title,
                'status': task.status,
                'status_text': status_text,
                'updated_at': task.updated_at.strftime('%d/%m/%Y')
            })
        
        stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'pending_tasks': pending_tasks,
            'level': user.level,
            'points': user.points,
            'achievements': achievements_count,
            'groups': groups_count,
            'recent_tasks': recent_tasks_data
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
def api_reset_user_password(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'})
    
    try:
        import secrets
        import string
        
        user = User.query.get_or_404(user_id)
        
        # Generar contraseña temporal
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        # Actualizar contraseña
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'new_password': new_password,
            'message': f'Contraseña reseteada para {user.username}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
