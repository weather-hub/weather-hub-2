from flask import Blueprint

bp = Blueprint('notifications', __name__)

from app.modules.notifications import routes  # si creas endpoints en routes.py
