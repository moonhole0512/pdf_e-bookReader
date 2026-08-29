import os
import secrets
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

def get_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key

    secret_file = os.path.join(basedir, 'instance', '.secret_key')
    os.makedirs(os.path.dirname(secret_file), exist_ok=True)

    if os.path.exists(secret_file):
        try:
            with open(secret_file, 'r', encoding='utf-8') as f:
                stored = f.read().strip()
                if stored:
                    return stored
        except Exception:
            pass

    new_key = secrets.token_hex(32)
    try:
        with open(secret_file, 'w', encoding='utf-8') as f:
            f.write(new_key)
    except Exception:
        pass
    return new_key

class Config:
    SECRET_KEY = get_secret_key()

    # Database path
    db_env = os.environ.get('DB_PATH', 'instance/library.db')
    if os.path.isabs(db_env):
        DB_PATH = os.path.normpath(db_env)
    else:
        DB_PATH = os.path.normpath(os.path.join(basedir, db_env))

    # PDF storage root path
    pdf_env = os.environ.get('PDF_ROOT_PATH')
    if pdf_env:
        PDF_ROOT_PATH = os.path.normpath(pdf_env) if os.path.isabs(pdf_env) else os.path.normpath(os.path.join(basedir, pdf_env))
    else:
        PDF_ROOT_PATH = os.path.normpath(os.path.join(basedir, 'pdfs'))

    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 15 # Wait up to 15s if SQLite is briefly locked
        }
    }
