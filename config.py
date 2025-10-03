import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-hard-to-guess-string'
    
    # .env 파일에서 상대 경로를 읽어옵니다.
    DB_PATH_RELATIVE = os.environ.get('DB_PATH') or 'instance/library.db'
    # 상대 경로를 프로젝트 기준 절대 경로로 변환합니다.
    DB_PATH = os.path.join(basedir, DB_PATH_RELATIVE)

    PDF_ROOT_PATH = os.environ.get('PDF_ROOT_PATH')
    
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
