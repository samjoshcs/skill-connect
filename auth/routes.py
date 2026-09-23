from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User

# A Blueprint groups related routes together (all the /signup, /login, /logout
# routes live here) so app.py doesn't become one giant file with everything in it.
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    # If someone is already logged in, sending them to signup again makes no sense.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # --- Basic validation ---
        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Try logging in instead.", "error")
            return render_template("signup.html")

        # --- Create the new user ---
        new_user = User(name=name, email=email)
        new_user.set_password(password)  # hashes the password, never stores it plain
        db.session.add(new_user)
        db.session.commit()

        # Log them in immediately after signing up, so they don't have to
        # sign up and then separately log in — smoother experience.
        login_user(new_user)
        flash(f"Welcome to SkillConnect, {new_user.name}!", "success")
        return redirect(url_for("main.edit_profile"))

    return render_template("signup.html")


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
