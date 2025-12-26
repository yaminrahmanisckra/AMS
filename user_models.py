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
    role = db.Column(db.String(20), nullable=False, default='teacher')
    photo = db.Column(db.String(255), nullable=True)  # Path to user's photo
    theme = db.Column(db.String(50), nullable=True, default='default')  # Color theme preference

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha512', salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>" 