import os
import secrets
from datetime import datetime, timezone

from flask import request, session
from flask_login import current_user

from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository, UserSessionRepository
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService


class AuthenticationService(BaseService):
    def __init__(self):
        super().__init__(UserRepository())
        self.user_profile_repository = UserProfileRepository()
        self.session_repository = UserSessionRepository()

    def login(self, email, password, remember=True):
        """Authenticate user and return the User on success, otherwise None.

        Important: do NOT call flask_login.login_user() here. The route expects
        this method to return the User object so it can handle 2FA and logging
        in. Creating the session record is best-effort: any errors while
        recording session should not prevent login.
        """
        user = self.repository.get_by_email(email)
        if user is not None and user.check_password(password):
            # try to create/update session record but do not let failures block login
            try:
                self._create_session_record(user)
            except Exception:
                # tolerate session tracking failures
                pass
            return user
        return None

    def _create_session_record(self, user):
        """Create a session record for tracking"""
        # Generate or get session ID
        if "session_id" not in session:
            session["session_id"] = secrets.token_urlsafe(32)
        session_id = session["session_id"]

        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent", "")
        device_info = self._extract_device_info(user_agent)

        # If a session with this session_id already exists, update it
        existing = None

        try:
            existing = self.session_repository.get_by_session_id(session_id)
        except Exception:
            # If repository lookup fails, continue and try to create
            existing = None

        if existing:
            try:
                existing.user_id = user.id
                existing.ip_address = ip_address
                existing.user_agent = user_agent
                existing.device_info = device_info
                existing.is_active = True
                existing.last_activity = datetime.now(timezone.utc)
                self.session_repository.session.commit()
                return existing
            except Exception:
                try:
                    self.session_repository.session.rollback()
                except Exception:
                    pass

        # Create new session record (best-effort). If a unique constraint
        # prevents creation, try to fetch and return the existing record.
        session_data = {
            "user_id": user.id,
            "session_id": session_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_info": device_info,
        }

        try:
            return self.session_repository.create(**session_data)
        except Exception:
            try:
                self.session_repository.session.rollback()
            except Exception:
                pass
            try:
                return self.session_repository.get_by_session_id(session_id)
            except Exception:
                return None

    def _extract_device_info(self, user_agent: str) -> str:
        """Extract simplified device info from user agent"""
        if not user_agent:
            return "Unknown Device"

        ua = user_agent.lower()
        if "mobile" in ua or "android" in ua or "iphone" in ua:
            return "Mobile Device"
        elif "tablet" in ua or "ipad" in ua:
            return "Tablet"
        else:
            return "Desktop"

    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_with_profile(self, **kwargs):
        try:
            email = kwargs.pop("email", None)
            password = kwargs.pop("password", None)
            name = kwargs.pop("name", None)
            surname = kwargs.pop("surname", None)

            if not email:
                raise ValueError("Email is required.")
            if not password:
                raise ValueError("Password is required.")
            if not name:
                raise ValueError("Name is required.")
            if not surname:
                raise ValueError("Surname is required.")

            user_data = {"email": email, "password": password}

            profile_data = {
                "name": name,
                "surname": surname,
            }

            user = self.create(commit=False, **user_data)
            profile_data["user_id"] = user.id
            self.user_profile_repository.create(**profile_data)
            self.repository.session.commit()
        except Exception as exc:
            self.repository.session.rollback()
            raise exc
        return user

    def update_profile(self, user_profile_id, form):
        if form.validate():
            updated_instance = self.update(user_profile_id, **form.data)
            return updated_instance, None

        return None, form.errors

    def get_authenticated_user(self) -> User | None:
        if current_user.is_authenticated:
            return current_user
        return None

    def get_authenticated_user_profile(self) -> UserProfile | None:
        if current_user.is_authenticated:
            return current_user.profile
        return None

    def temp_folder_by_user(self, user: User) -> str:
        return os.path.join(uploads_folder_name(), "temp", str(user.id))


def get_user_by_id(self, user_id: int) -> User | None:
    return self.repository.get_by_id(user_id)


class SessionManagementService(BaseService):
    """Service for managing user sessions"""

    def __init__(self):
        super().__init__(UserSessionRepository())

    def get_active_sessions(self, user_id: int):
        """Get all active sessions for a user"""
        return self.repository.get_active_sessions_by_user(user_id)

    def get_current_session_id(self):
        """Get the current session ID"""
        return session.get("session_id")

    def close_session(self, session_id: str, user_id: int):
        """Close a specific session if it belongs to the user"""
        user_session = self.repository.get_by_session_id(session_id)
        if user_session and user_session.user_id == user_id:
            return self.repository.deactivate_session(session_id)
        return False

    def close_all_other_sessions(self, user_id: int, current_session_id: str):
        """Close all sessions except the current one"""
        sessions = self.get_active_sessions(user_id)
        closed_count = 0
        for user_session in sessions:
            if user_session.session_id != current_session_id:
                if self.repository.deactivate_session(user_session.session_id, commit=False):
                    closed_count += 1
        self.repository.session.commit()
        return closed_count

    def update_session_activity(self, session_id: str):
        """Update the last activity timestamp"""
        return self.repository.update_last_activity(session_id)
