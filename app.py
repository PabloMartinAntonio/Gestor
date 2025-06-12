import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash

# Logging
logging.basicConfig(level=logging.DEBUG)

# Base para modelos
class Base(DeclarativeBase):
    pass

# Inicializar SQLAlchemy sin app todavía
db = SQLAlchemy(model_class=Base)

# Crear Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configurar SQLite (o PostgreSQL si hay variable de entorno)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL") or "sqlite:///tasks.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Inicializar extensiones con app
db.init_app(app)
migrate = Migrate(app, db)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor iniciá sesión para acceder a esta página.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Crear tablas y usuario admin por defecto
with app.app_context():
    # Import models to ensure they're registered for migrations
    import models

    # Crear usuario admin si no existe
    from models import User
    from werkzeug.security import generate_password_hash

    #admin_user = User.query.filter_by(username='admin').first()
    #if not admin_user:
    #    admin_user = User(
    #        username='admin',
    #        email='admin@taskapp.com',
    #        password_hash=generate_password_hash('admin123'),
    #        is_admin=True
    #    )
    #    db.session.add(admin_user)
    #    db.session.commit()
    #    app.logger.info("Usuario administrador creado: admin/admin123")


# Importar rutas
import routes
