# This file exists to avoid "circular imports" — a common Flask gotcha.
# db and login_manager are created here (with no app attached yet), then
# "attached" to the real app inside app.py using db.init_app(app).
# This way, models.py can safely import `db` without needing the app itself.

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# If someone tries to access a page that needs login without being logged in,
# Flask-Login redirects them here automatically.
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"
