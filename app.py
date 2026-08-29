import os
import sqlite3
import logging
from flask import Flask, session, g
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import Config
from models import db, User
from services.migration import migrate_database

# Configure dual-level logging
log_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '_testcode', 'debug')
os.makedirs(log_dir, exist_ok=True)
debug_log_path = os.path.join(log_dir, 'debug.log')

root_logger = logging.getLogger()
if not root_logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

# File handler for detailed debug log (overwrite on start per project rule)
file_handler = logging.FileHandler(debug_log_path, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s'))
root_logger.addHandler(file_handler)

# Configure SQLite PRAGMA for high concurrency and zero-lock performance on low-spec NAS
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Register Blueprints
    from blueprints.auth import auth_bp
    from blueprints.library import library_bp
    from blueprints.reader import reader_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(reader_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Maintain 100% backward compatibility with existing templates and URL endpoints
    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        g.user = db.session.get(User, user_id) if user_id is not None else None

    # Setup database and run migration
    with app.app_context():
        db_path = app.config['DB_PATH']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db.create_all()

        pdf_root = app.config.get('PDF_ROOT_PATH')
        try:
            migrate_database(db_path, pdf_root)
        except Exception as e:
            app.logger.error(f"Migration error: {e}")

        # Register legacy endpoint aliases so existing templates continue working without changes
        app.view_functions['index'] = app.view_functions['library.index']
        app.view_functions['login'] = app.view_functions['auth.login']
        app.view_functions['logout'] = app.view_functions['auth.logout']
        app.view_functions['reader'] = app.view_functions['reader.reader_view']
        app.view_functions['static_pdfs'] = app.view_functions['reader.static_pdfs']
        app.view_functions['get_books'] = app.view_functions['library.get_books']

    return app

app = create_app()

if __name__ == '__main__':
    # Local development server
    app.run(debug=True, host='0.0.0.0', port=8000)
