from flask_mail import Mail, Message
from flask import current_app

mail = Mail()


def init_mail(app):
    """Inicializa Flask-Mail con la app principal."""
    mail.init_app(app)


def send_email(subject, recipients, body):
    """Envía un correo utilizando Flask-Mail."""
    msg = Message(subject, recipients=recipients, body=body)
    with current_app.app_context():
        mail.send(msg)
