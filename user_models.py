from datetime import datetime

from flask_login import UserMixin
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from passlib.hash import scrypt as passlib_scrypt
except ImportError:  # pragma: no cover
    passlib_scrypt = None

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Explicitly naming the table 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    role = db.Column(db.String(120), nullable=False, default='teacher')
    photo = db.Column(db.String(255), nullable=True)  # Path to user's photo
    signature_path = db.Column(db.String(255), nullable=True)  # Profile signature (admission, remuneration, etc.)
    theme = db.Column(db.String(50), nullable=True, default='default')  # Color theme preference
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)  # Link to Teacher (for admin edit/dashboard)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha512', salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class PasswordResetCode(db.Model):
    """Server-side password-reset challenge. Never send code_hash to the client."""

    __tablename__ = 'password_reset_code'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    salt = db.Column(db.String(64), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    password_fingerprint = db.Column(db.String(16), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User')