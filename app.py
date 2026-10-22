from flask import Flask, render_template
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db, login_manager, oauth
from models import User


def create_app():
    """
    This 'application factory' pattern just means: instead of creating the
    Flask app as a global variable, we build it inside a function. This makes
    it easier to test and keeps imports clean (avoids circular imports).
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # On Render the app sits behind a proxy that handles https. This makes
    # Flask build correct https:// links (needed for Google's redirect URL).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Attach our shared extensions (db, login_manager) to this specific app.
    db.init_app(app)
    login_manager.init_app(app)

    # Register Google as a login provider (OpenID Connect).
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

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

    @app.errorhandler(413)
    def file_too_large(_e):
        from flask import flash, redirect, request, url_for
        flash("That file is too big — the limit is 50 MB. Try a shorter clip.", "error")
        return redirect(request.referrer or url_for("main.dashboard"))

    return app


# Flask-Login needs to know how to load a user from the ID stored in the
# session cookie. This function is called automatically on every request.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
