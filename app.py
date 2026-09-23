from flask import Flask, render_template
from flask_login import current_user

from config import Config
from extensions import db, login_manager
from models import User


def create_app():
    """
    This 'application factory' pattern just means: instead of creating the
    Flask app as a global variable, we build it inside a function. This makes
    it easier to test and keeps imports clean (avoids circular imports).
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Attach our shared extensions (db, login_manager) to this specific app.
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints — each blueprint is one "feature module" of routes.
    from auth.routes import auth_bp
    from main.routes import main_bp
    from admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Create all database tables if they don't exist yet.
    with app.app_context():
        db.create_all()

    return app


# Flask-Login needs to know how to load a user from the ID stored in the
# session cookie. This function is called automatically on every request.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
