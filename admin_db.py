import sqlite3
import os
from datetime import datetime

class AdminDatabase:
    """Clase para manejar la base de datos SQLite de administración"""
    
    def __init__(self, db_path='admin_management.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializar la base de datos con las tablas necesarias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de logs de administración
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user_id INTEGER NOT NULL,
                admin_username TEXT NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de backups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_name TEXT NOT NULL,
                backup_path TEXT NOT NULL,
                size_mb REAL,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'completed'
            )
        ''')
        
        # Tabla de configuraciones del sistema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                updated_by INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de grupos privados para administración
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_groups_admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                created_by_id INTEGER NOT NULL,
                member_count INTEGER DEFAULT 0,
                last_activity DATETIME,
                admin_notes TEXT,
                monitored_since DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de estadísticas diarias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                total_tasks INTEGER DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                total_groups INTEGER DEFAULT 0,
                private_groups INTEGER DEFAULT 0,
                new_registrations INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_admin_action(self, admin_user_id, admin_username, action, target_type, target_id=None, details=None):
        """Registrar acción de administrador"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO admin_logs 
            (admin_user_id, admin_username, action, target_type, target_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_user_id, admin_username, action, target_type, target_id, details))
        
        conn.commit()
        conn.close()
    
    def add_backup_record(self, backup_name, backup_path, size_mb, created_by):
        """Registrar backup creado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backup_history (backup_name, backup_path, size_mb, created_by)
            VALUES (?, ?, ?, ?)
        ''', (backup_name, backup_path, size_mb, created_by))
        
        conn.commit()
        conn.close()
    
    def monitor_private_group(self, group_id, group_name, created_by_id, member_count=0, admin_notes=None):
        """Agregar grupo privado al monitoreo"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verificar si ya existe
        cursor.execute('SELECT id FROM private_groups_admin WHERE group_id = ?', (group_id,))
        if cursor.fetchone():
            # Actualizar existente
            cursor.execute('''
                UPDATE private_groups_admin 
                SET group_name = ?, member_count = ?, last_activity = CURRENT_TIMESTAMP, admin_notes = ?
                WHERE group_id = ?
            ''', (group_name, member_count, admin_notes, group_id))
        else:
            # Insertar nuevo
            cursor.execute('''
                INSERT INTO private_groups_admin 
                (group_id, group_name, created_by_id, member_count, admin_notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, group_name, created_by_id, member_count, admin_notes))
        
        conn.commit()
        conn.close()
    
    def get_admin_logs(self, limit=100, offset=0, filter_action=None):
        """Obtener logs de administración"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT admin_username, action, target_type, target_id, details, timestamp
            FROM admin_logs
        '''
        params = []
        
        if filter_action:
            query += ' WHERE action LIKE ?'
            params.append(f'%{filter_action}%')
        
        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()
        
        return logs
    
    def get_private_groups_admin(self):
        """Obtener grupos privados monitoreados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT group_id, group_name, created_by_id, member_count, 
                   last_activity, admin_notes, monitored_since
            FROM private_groups_admin
            ORDER BY monitored_since DESC
        ''')
        
        groups = cursor.fetchall()
        conn.close()
        
        return groups
    
    def update_daily_stats(self, date, **stats):
        """Actualizar estadísticas diarias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verificar si existe registro para la fecha
        cursor.execute('SELECT id FROM daily_stats WHERE date = ?', (date,))
        exists = cursor.fetchone()
        
        if exists:
            # Actualizar existente
            set_clause = ', '.join([f'{key} = ?' for key in stats.keys()])
            values = list(stats.values()) + [date]
            cursor.execute(f'''
                UPDATE daily_stats SET {set_clause} WHERE date = ?
            ''', values)
        else:
            # Insertar nuevo
            columns = ', '.join(['date'] + list(stats.keys()))
            placeholders = ', '.join(['?'] * (len(stats) + 1))
            values = [date] + list(stats.values())
            cursor.execute(f'''
                INSERT INTO daily_stats ({columns}) VALUES ({placeholders})
            ''', values)
        
        conn.commit()
        conn.close()
    
    def get_config(self, key, default=None):
        """Obtener configuración del sistema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_value FROM system_config WHERE config_key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else default
    
    def set_config(self, key, value, description=None, updated_by=None):
        """Establecer configuración del sistema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_config 
            (config_key, config_value, description, updated_by, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (key, value, description, updated_by))
        
        conn.commit()
        conn.close()

# Instancia global de la base de datos de administración
admin_db = AdminDatabase()