"""
Admin panel — a restricted area only accessible to users with is_admin=True.

This does NOT have its own separate login form; it reuses the normal
login system. The only difference is the @admin_required check below,
which blocks anyone who isn't flagged as an admin from reaching these
routes at all — same idea as @login_required, just one level stricter.
"""

from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import User, ExchangeRequest, UserSkill, Rating

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view_func):
    """
    Like @login_required, but also checks current_user.is_admin.
    Applied on top of @login_required on every route below.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("You don't have access to that page.", "error")
            return redirect(url_for("main.dashboard"))
        return view_func(*args, **kwargs)
    return wrapped


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_exchanges_accepted = ExchangeRequest.query.filter(
        ExchangeRequest.status.in_(["accepted", "completed"])
    ).count()
    total_pending_requests = ExchangeRequest.query.filter_by(status="pending").count()
    total_ratings = Rating.query.count()

    # Most-listed "can teach" skills — a simple GROUP BY, good example of
    # basic SQL aggregation for the report/viva.
    top_skills = (
        db.session.query(UserSkill.skill_name, db.func.count(UserSkill.id).label("count"))
        .filter_by(type="can_teach")
        .group_by(UserSkill.skill_name)
        .order_by(db.desc("count"))
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_exchanges_accepted=total_exchanges_accepted,
        total_pending_requests=total_pending_requests,
        total_ratings=total_ratings,
        top_skills=top_skills,
    )


@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You can't delete your own account from here.", "error")
        return redirect(url_for("admin.manage_users"))

    user = User.query.get_or_404(user_id)

    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Deleted user: {user.name}.", "success")
    except Exception as e:
        # If this user has messages/exchanges/posts referencing them, some
        # databases (like MySQL with foreign key constraints) will refuse
        # the delete rather than leave orphaned data. SQLite is more
        # lenient, but this keeps the app from crashing either way.
        db.session.rollback()
        print(f"[admin delete_user error] {e}")
        flash("Couldn't delete this user — they may have existing activity linked to their account.", "error")

    return redirect(url_for("admin.manage_users"))
