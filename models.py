from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)

    reading_states = relationship('ReadingState', back_populates='user', cascade="all, delete-orphan")

    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None

    def check_password(self, password):
        if not self.password_hash:
            # If no password set, allow empty or any password (backward compatibility)
            return True
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Book(db.Model):
    __tablename__ = 'book'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    total_volumes = Column(Integer, default=1)
    cover_url = Column(String(500), nullable=True)
    # Compact metadata for discovery; provider payloads are intentionally not stored wholesale.
    isbn_13 = Column(String(13), nullable=True, index=True)
    source_category = Column(String(255), nullable=True)
    category = Column(String(50), nullable=True, index=True)
    metadata_source = Column(String(50), nullable=True)
    
    files = relationship('File', back_populates='book', cascade="all, delete-orphan", order_by="File.volume_number")

    def __repr__(self):
        return f'<Book {self.title}>'

class File(db.Model):
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('book.id'), nullable=False, index=True)
    file_path = Column(String(1024), unique=True, nullable=False, index=True)
    volume_number = Column(Integer, default=1)
    total_pages = Column(Integer, default=0, nullable=False)

    # File-specific metadata
    title = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    cover_url = Column(String(500), nullable=True)

    book = relationship('Book', back_populates='files')
    reading_states = relationship('ReadingState', back_populates='file', cascade="all, delete-orphan")

    @property
    def reading_state(self):
        """Backward compatibility helper for templates that access file.reading_state."""
        from flask import g
        if hasattr(g, 'user') and g.user:
            return next((s for s in self.reading_states if s.user_id == g.user.id), None)
        return self.reading_states[0] if self.reading_states else None

    def __repr__(self):
        return f'<File {self.file_path}>'

class ReadingState(db.Model):
    __tablename__ = 'reading_state'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False, index=True)
    current_page = Column(Integer, default=1)
    last_read_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'file_id', name='uq_user_file_reading_state'),
    )

    user = relationship('User', back_populates='reading_states')
    file = relationship('File', back_populates='reading_states')

    def __repr__(self):
        return f'<ReadingState User:{self.user_id} File:{self.file_id} Page:{self.current_page}>'

class PageEdit(db.Model):
    __tablename__ = 'page_edit'
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('file.id'), nullable=False, index=True)
    page_num = Column(Integer, nullable=False) # 1-based target page number
    action = Column(String(20), nullable=False) # 'replace', 'delete', 'insert_before', 'insert_after'
    image_path = Column(String(1024), nullable=True) # relative path to instance/overrides/...
    created_at = Column(DateTime, default=func.now())

    file = relationship('File', backref=db.backref('page_edits', cascade='all, delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'file_id': self.file_id,
            'page_num': self.page_num,
            'action': self.action,
            'image_path': self.image_path,
            'has_image': bool(self.image_path),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'book_title': self.file.book.title if self.file and self.file.book else '',
            'volume_number': self.file.volume_number if self.file else 1
        }

    def __repr__(self):
        return f'<PageEdit File:{self.file_id} Page:{self.page_num} Action:{self.action}>'
