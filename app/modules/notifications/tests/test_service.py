from app.modules.notifications.service import send_email


def test_send_email(test_app, mocker):
    # Mockea la librería de envío de correos
    mock_smtp = mocker.patch("flask_mail.Mail.send")

    # Usa el contexto de la app para permitir current_app
    with test_app.app_context():
        send_email("Test Subject", ["recipient@example.com"], "Test Body")

    mock_smtp.assert_called_once()
