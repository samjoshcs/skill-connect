"""
Run this once to make yourself an admin, so you can access /admin.

Usage:
    python make_admin.py your@email.com

This just flips the is_admin flag on your existing account — you still
log in normally through the regular /login page afterward.
"""

import sys
from app import app
from extensions import db
from models import User

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py your@email.com")
        sys.exit(1)

    email = sys.argv[1].strip().lower()

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No account found with email: {email}")
            print("Make sure you've signed up with this email first.")
            sys.exit(1)

        user.is_admin = True
        db.session.commit()
        print(f"Done — {user.name} ({email}) is now an admin.")
        print("Log in normally and visit /admin to see the panel.")
