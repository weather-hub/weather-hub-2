import logging

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import increment_failed_attempts, is_blocked, reset_failed_attempts
from app.modules.auth import auth_bp
from app.modules.auth.forms import LoginForm, SignupForm, Verify2FAForm
from app.modules.auth.services import AuthenticationService, SessionManagementService
from app.modules.notifications.service import send_email
from app.modules.profile.services import UserProfileService

logger = logging.getLogger(__name__)
authentication_service = AuthenticationService()
user_profile_service = UserProfileService()
session_management_service = SessionManagementService()


@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        logger.info(f"Signup attempt with email: {email}")

        if not authentication_service.is_email_available(email):
            error_msg = f"Email {email} in use"
            logger.warning(f"Signup failed: {error_msg}")
            template = "auth/signup_form.html"
            return render_template(template, form=form, error=error_msg)

        try:
            user = authentication_service.create_with_profile(**form.data)
            logger.info(f"User created successfully: {email}")
        except Exception as exc:
            error_msg = f"Error creating user: {exc}"
            logger.error(f"Signup error: {error_msg}")
            template = "auth/signup_form.html"
            return render_template(template, form=form, error=error_msg)

        # Send a simple confirmation email stating the address is valid.
        try:
            subject = "Tu correo es válido - WeatherHub"
            body = (
                "Hola,\n\nSi estás viendo este correo, tu dirección de correo es válida. "
                "Gracias por usar WeatherHub.\n\n— El equipo de WeatherHub"
            )
            logger.info(f"Attempting to send confirmation email to {email}")
            send_email(subject, [user.email], body)
            logger.info(f"Confirmation email sent successfully to {email}")
        except Exception as exc:
            # Don't block signup if email sending fails; just continue.
            logger.error(f"Failed to send confirmation email to {email}: {str(exc)}")
            pass

        # Log user in and redirect to home
        logger.info(f"User {email} logged in after signup")
        login_user(user, remember=True)
        return redirect(url_for("public.index"))

    return render_template("auth/signup_form.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = LoginForm()
    if is_blocked():
        error_m = "Too many attempts. Try again in 3 minutes."
        logger.warning("Login blocked due to too many attempts")
        template = "auth/login_form.html"
        return (
            render_template(template, form=form, error=error_m),
            429,
        )

    if request.method == "POST" and form.validate_on_submit():
        email = form.email.data
        pwd = form.password.data
        logger.info(f"Login attempt for email: {email}")

        user = authentication_service.login(email, pwd)
        if user:
            # Login exitoso → reinicia contador
            logger.info(f"Login successful for user: {email}")
            reset_failed_attempts()
            if user.twofa_enabled:
                logger.info(f"2FA enabled for user {email}, redirecting to verification")
                session["2fa_user_id"] = user.id
                return redirect(url_for("auth.verify_2fa"))
            login_user(user, remember=True)
            return redirect(url_for("public.index"))
        # Login fallido → incrementar contador
        logger.warning(f"Login failed for email: {email} (invalid credentials)")
        increment_failed_attempts()
        if is_blocked():
            error_m = "Too many attempts. Try again in 3 minutes."
            logger.warning(f"Login blocked after failed attempt for {email}")
            template = "auth/login_form.html"
            return (
                render_template(template, form=form, error=error_m),
                429,
            )
        return render_template("auth/login_form.html", form=form, error="Invalid credentials")

    return render_template("auth/login_form.html", form=form)


@auth_bp.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa():
    from flask import session

    user_id = session.get("2fa_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    user = authentication_service.get_user_by_id(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    form = Verify2FAForm()

    if request.method == "POST" and form.validate_on_submit():
        otp = form.otp_code.data
        import pyotp  # type: ignore

        totp = pyotp.TOTP(user.otp_secret)
        if totp.verify(otp):
            session.pop("2fa_user_id")
            login_user(user, remember=True)
            return redirect(url_for("public.index"))
        else:
            error_msg = "Invalid 2FA code"
            template = "auth/verify_2fa.html"
            return render_template(template, form=form, error=error_msg)
    return render_template("auth/verify_2fa.html", form=form)


@auth_bp.route("/logout")
def logout():
    # Try to deactivate the current user_session row and remove the session_id
    try:
        user_email = current_user.email if getattr(current_user, "is_authenticated", False) else "anonymous"
        logger.info(f"Logout initiated for user: {user_email}")
        current_session_id = session_management_service.get_current_session_id()
        if getattr(current_user, "is_authenticated", False) and current_session_id:
            # deactivate the session row for this session_id if it belongs to the user
            try:
                session_management_service.close_session(current_session_id, current_user.id)
                logger.info(f"Session closed for user: {current_user.email}")
            except Exception as e:
                # non-fatal: continue to logout even if DB call fails
                logger.warning(f"Failed to close session in DB: {str(e)}")
                pass
        # Remove the session cookie value so next requests don't reuse it
        session.pop("session_id", None)
    except Exception as e:
        # ensure logout proceeds even if any of the above fails
        logger.warning(f"Logout cleanup encountered an error: {str(e)}")
        pass
    logout_user()
    logger.info("User logged out successfully")
    return redirect(url_for("public.index"))


@auth_bp.route("/sessions")
@login_required
def manage_sessions():
    """View to manage active sessions"""
    logger.info(f"Session management page accessed by user: {current_user.email}")
    active_sessions = session_management_service.get_active_sessions(current_user.id)
    current_session_id = session_management_service.get_current_session_id()
    logger.debug(f"Found {len(active_sessions)} active sessions for user {current_user.email}")
    return render_template("auth/sessions.html", sessions=active_sessions, current_session_id=current_session_id)


@auth_bp.route("/sessions/close/<session_id>", methods=["POST"])
@login_required
def close_session(session_id):
    """Close a specific session"""
    logger.info(f"Attempting to close session {session_id} for user: {current_user.email}")
    if session_management_service.close_session(session_id, current_user.id):
        logger.info(f"Session {session_id} closed successfully")
        flash("Session closed successfully", "success")
    else:
        logger.warning(f"Failed to close session {session_id}")
        flash("Could not close session", "error")
    return redirect(url_for("auth.manage_sessions"))


@auth_bp.route("/sessions/close-all", methods=["POST"])
@login_required
def close_all_sessions():
    """Close all sessions except the current one"""
    logger.info(f"Closing all sessions except current for user: {current_user.email}")
    current_session_id = session_management_service.get_current_session_id()
    closed_count = session_management_service.close_all_other_sessions(current_user.id, current_session_id)
    logger.info(f"Closed {closed_count} sessions for user {current_user.email}")
    flash(f"{closed_count} session(s) closed successfully", "success")
    return redirect(url_for("auth.manage_sessions"))
