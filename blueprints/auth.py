from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, g, jsonify
from models import db, User

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username:
            return render_template('login.html', error="사용자 이름을 입력해주세요.", users=User.query.all())

        user = User.query.filter_by(username=username).first()
        if not user:
            # Auto-create user for frictionless experience (Apple-like simplicity)
            user_count = User.query.count()
            user = User(username=username, is_admin=(user_count == 0))
            if password:
                user.set_password(password)
            db.session.add(user)
            db.session.commit()
        else:
            if user.password_hash and not user.check_password(password):
                return render_template('login.html', error="비밀번호가 일치하지 않습니다.", users=User.query.all())

        session.clear()
        session['user_id'] = user.id
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('library.index'))

    users = User.query.all()
    return render_template('login.html', users=users)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
