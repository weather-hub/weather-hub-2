from datetime import datetime, timezone

from app.modules.auth.models import Role, User, UserSession
from core.repositories.BaseRepository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def create(self, commit: bool = True, **kwargs):
        password = kwargs.pop("password")
        instance = self.model(**kwargs)
        instance.set_password(password)
        self.session.add(instance)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return instance

    def get_by_email(self, email: str):
        return self.model.query.filter_by(email=email).first()


class RoleRepository(BaseRepository):
    def __init__(self):
        super().__init__(Role)

    def get_by_name(self, name: str):
        return self.model.query.filter_by(name=name).first()

    def create_if_not_exists(self, name: str, description: str = None):
        role = self.get_by_name(name)
        if role:
            return role
        return self.create(name=name, description=description)


class UserSessionRepository(BaseRepository):
    def __init__(self):
        super().__init__(UserSession)

    def get_by_session_id(self, session_id: str):
        """Get session by session ID"""
        return self.model.query.filter_by(session_id=session_id, is_active=True).first()

    def get_active_sessions_by_user(self, user_id: int):
        """Get all active sessions for a user"""
        return (
            self.model.query.filter_by(user_id=user_id, is_active=True).order_by(self.model.last_activity.desc()).all()
        )

    def deactivate_session(self, session_id: str, commit: bool = True):
        """Deactivate a session"""
        session = self.get_by_session_id(session_id)
        if session:
            session.is_active = False
            if commit:
                self.session.commit()
            return True
        return False

    def update_last_activity(self, session_id: str, commit: bool = True):
        """Update the last activity timestamp of a session"""
        session = self.get_by_session_id(session_id)
        if session:
            session.last_activity = datetime.now(timezone.utc)
            if commit:
                self.session.commit()
            return True
        return False

    def cleanup_inactive_sessions(self, days: int = 30, commit: bool = True):
        """Remove sessions inactive for more than specified days"""
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        inactive_sessions = self.model.query.filter(
            self.model.last_activity < cutoff_date, self.model.is_active == True  # noqa: E712
        ).all()

        for session in inactive_sessions:
            session.is_active = False

        if commit:
            self.session.commit()

        return len(inactive_sessions)
