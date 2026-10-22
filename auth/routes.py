import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db, oauth
from models import User

# A Blueprint groups related routes together (all the /signup, /login, /logout
# routes live here) so app.py doesn't become one giant file with everything in it.
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup")
def signup():
    # New accounts are created ONLY through Google, so every email is real
    # and verified by Google. The page just shows the Google button.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("signup.html")


@auth_bp.route("/login/google")
def google_login():
    """Step 1: send the user to Google's sign-in page."""
    if not current_app.config["GOOGLE_CLIENT_ID"]:
        flash("Google login isn't set up yet. See the README for setup steps.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    try:
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception:
        flash("Could not reach Google right now. Check your internet and try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/auth/google/callback")
def google_callback():
    """Step 2: Google sends the user back here after they sign in."""
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        flash("Google sign-in was cancelled or failed. Please try again.", "error")
        return redirect(url_for("auth.login"))

    info = token.get("userinfo") or {}
    email = (info.get("email") or "").strip().lower()

    # Only accept emails that Google itself has verified.
    if not email or not info.get("email_verified"):
        flash("Your Google email could not be verified.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    is_new = user is None
    if is_new:
        user = User(name=info.get("name") or email.split("@")[0], email=email)
        # Google users never type a password here, so store a random
        # unguessable one (the column can't be empty).
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()

    login_user(user)
    if is_new:
        flash(f"Welcome to SkillConnect, {user.name}!", "success")
        return redirect(url_for("main.edit_profile"))
    flash(f"Welcome back, {user.name}!", "success")
    return redirect(url_for("main.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        # Deliberately vague error message — doesn't reveal whether the
        # email exists or the password was wrong, which is better security
        # practice than telling an attacker which part was incorrect.
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        login_user(user)
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.home"))
