from flask import current_app
from flask_mail import Mail, Message

mail = Mail()


def init_mail(app):
    """Inicializa Flask-Mail con la app principal."""
    mail.init_app(app)


def send_email(subject, recipients, body):
    print(f"send_email called with subject: {subject}, recipients: {recipients}")
    """Envía un correo utilizando Flask-Mail."""
    msg = Message(subject, recipients=recipients, body=body)
    with current_app.app_context():
        mail.send(msg)
