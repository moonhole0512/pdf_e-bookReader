
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, backref

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class Book(db.Model):
    __tablename__ = 'book'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    total_volumes = Column(Integer, default=1)
    cover_url = Column(String(255))
    
    files = relationship('File', back_populates='book', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Book {self.title}>'

class File(db.Model):
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('book.id'), nullable=False)
    file_path = Column(String(1024), unique=True, nullable=False)
    volume_number = Column(Integer, default=1)
    total_pages = Column(Integer, nullable=False)

    # File-specific metadata
    title = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    cover_url = Column(String(255), nullable=True)

    book = relationship('Book', back_populates='files')
    reading_state = relationship('ReadingState', uselist=False, back_populates='file', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<File {self.file_path}>'

class ReadingState(db.Model):
    __tablename__ = 'reading_state'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False, unique=True)
    current_page = Column(Integer, default=1)
    last_read_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship('User')
    file = relationship('File', back_populates='reading_state')

    def __repr__(self):
        return f'<ReadingState User:{self.user_id} File:{self.file_id} Page:{self.current_page}>'
