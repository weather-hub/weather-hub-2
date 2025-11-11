from unittest.mock import patch
from flask import url_for


def test_signup_sends_email(test_client):
    with patch("app.modules.auth.routes.send_email") as mock_send_email:
        response = test_client.post(
            "/signup",
            data=dict(name="Test", surname="User", email="testuser@example.com", password="password123"),
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert response.request.path == url_for("public.index")

    mock_send_email.assert_called_once_with(
        "Tu correo es válido - WeatherHub",
        ["testuser@example.com"],
        (
            "Hola,\n\n"
            "Si estás viendo este correo, tu dirección de correo es válida. "
            "Gracias por usar WeatherHub.\n\n"
            "— El equipo de WeatherHub"
        ),
    )
