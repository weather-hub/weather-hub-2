import os

from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from core.configuration.configuration import get_app_version
from core.managers.config_manager import ConfigManager
from core.managers.error_handler_manager import ErrorHandlerManager
from core.managers.logging_manager import LoggingManager
from core.managers.module_manager import ModuleManager

# Load environment variables
load_dotenv()

# Create the instances
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name="development"):
    app = Flask(__name__)

    # Load configuration according to environment
    config_manager = ConfigManager(app)
    config_manager.load_config(config_name=config_name)
    
    def _to_bool(val, default=False):
        if val is None:
            return default
        return str(val).lower() in ("1", "true", "yes", "on")

    app.config.update(
        MAIL_SERVER=os.getenv("MAIL_SERVER", app.config.get("MAIL_SERVER", "localhost")),
        MAIL_PORT=int(os.getenv("MAIL_PORT", app.config.get("MAIL_PORT", 25))),
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", app.config.get("MAIL_USERNAME")),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", app.config.get("MAIL_PASSWORD")),
        MAIL_USE_TLS=_to_bool(os.getenv("MAIL_USE_TLS", app.config.get("MAIL_USE_TLS", True))),
        MAIL_USE_SSL=_to_bool(os.getenv("MAIL_USE_SSL", app.config.get("MAIL_USE_SSL", False))),
        MAIL_DEFAULT_SENDER=os.getenv(
            "MAIL_DEFAULT_SENDER", app.config.get("MAIL_DEFAULT_SENDER", "no-reply@example.com")
        ),
        MAIL_SUPPRESS_SEND=_to_bool(os.getenv("MAIL_SUPPRESS_SEND", app.config.get("MAIL_SUPPRESS_SEND", False))),
    )

    # Initialize mail service
    # Import here to avoid potential circular imports at module import time
    from app.modules.notifications.service import init_mail
    init_mail(app)

    # Initialize SQLAlchemy and Migrate with the app
    db.init_app(app)
    migrate.init_app(app, db)

    # Register modules
    module_manager = ModuleManager(app)
    module_manager.register_modules()

    # Register login manager
    from flask_login import LoginManager

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        from app.modules.auth.models import User

        return User.query.get(int(user_id))

    # Set up logging
    logging_manager = LoggingManager(app)
    logging_manager.setup_logging()

    # Initialize error handler manager
    error_handler_manager = ErrorHandlerManager(app)
    error_handler_manager.register_error_handlers()

    # Injecting environment variables into jinja context
    @app.context_processor
    def inject_vars_into_jinja():
        return {
            "FLASK_APP_NAME": os.getenv("FLASK_APP_NAME"),
            "FLASK_ENV": os.getenv("FLASK_ENV"),
            "DOMAIN": os.getenv("DOMAIN", "localhost"),
            "APP_VERSION": get_app_version(),
        }

    return app


app = create_app()
