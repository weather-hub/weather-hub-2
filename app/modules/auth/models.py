from datetime import datetime, timezone

from flask_login import UserMixin
from user_agents import parse as parse_user_agent
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

# Association table between users and roles
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    otp_secret = db.Column(db.String(16), nullable=True)  # Base32 secret
    twofa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    data_sets = db.relationship("DataSet", backref="user", lazy=True)
    profile = db.relationship("UserProfile", backref="user", uselist=False)
    sessions = db.relationship("UserSession", backref="user", lazy=True, cascade="all, delete-orphan")

    # Roles relationship (many-to-many)
    roles = db.relationship("Role", secondary=user_roles, backref=db.backref("users", lazy="dynamic"))

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if "password" in kwargs:
            self.set_password(kwargs["password"])

    def __repr__(self):
        return f"<User {self.email}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def temp_folder(self) -> str:
        from app.modules.auth.services import AuthenticationService

        return AuthenticationService().temp_folder_by_user(self)


class UserSession(db.Model):
    """Model to track active user sessions for security management"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    session_id = db.Column(db.String(256), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(512), nullable=True)
    device_info = db.Column(db.String(256), nullable=True)
    location = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<UserSession {self.session_id} - User {self.user_id}>"

    def get_browser_name(self) -> str:
        """Obtener el nombre del navegador de forma automática"""
        if not self.user_agent:
            return "Unknown Browser"
        ua = parse_user_agent(self.user_agent)
        return ua.browser.family or "Unknown Browser"

    def get_os_name(self) -> str:
        """Obtener el sistema operativo de forma automática"""
        if not self.user_agent:
            return "Unknown OS"
        ua = parse_user_agent(self.user_agent)
        return ua.os.family or "Unknown OS"

    def is_current_session(self, current_session_id: str) -> bool:
        """Check if this is the current session"""
        return self.session_id == current_session_id
