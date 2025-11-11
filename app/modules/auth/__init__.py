from core.blueprints.base_blueprint import BaseBlueprint

auth_bp = BaseBlueprint("auth", __name__, template_folder="templates")


@auth_bp.before_app_request
def enforce_active_user_session():
    from flask import session
    from flask_login import current_user, logout_user

    if getattr(current_user, "is_authenticated", False):
        try:
            from app.modules.auth.repositories import UserSessionRepository

            current_session_id = session.get("session_id")
            if not current_session_id or not UserSessionRepository().get_by_session_id(current_session_id):
                session.pop("session_id", None)
                logout_user()
        except Exception:
            # Do not block requests if DB/table is missing or another error occurs
            pass
