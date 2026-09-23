from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    """
    UserMixin (from Flask-Login) automatically gives this class the methods
    Flask-Login needs (is_authenticated, is_active, get_id, etc.) so we don't
    have to write them ourselves.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, default="")
    availability = db.Column(db.String(255), default="")
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One user can have many skill rows (both "can_teach" and "wants_to_learn")
    skills = db.relationship("UserSkill", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        # Never store the actual password — only a one-way hash of it.
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def can_teach_skills(self):
        return [s for s in self.skills if s.type == "can_teach"]

    def wants_to_learn_skills(self):
        return [s for s in self.skills if s.type == "wants_to_learn"]

    def average_rating(self):
        ratings = Rating.query.filter_by(to_user=self.id).all()
        if not ratings:
            return None
        return round(sum(r.rating for r in ratings) / len(ratings), 1)

    def __repr__(self):
        return f"<User {self.email}>"


class UserSkill(db.Model):
    __tablename__ = "user_skills"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    skill_name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'can_teach' or 'wants_to_learn'
    proficiency = db.Column(db.String(20), default="")  # only used for can_teach rows


class ExchangeRequest(db.Model):
    __tablename__ = "exchange_requests"

    id = db.Column(db.Integer, primary_key=True)
    from_user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")  # pending / accepted / declined / completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # These let us write `some_request.requester.name` in templates instead
    # of manually looking up the User by from_user/to_user every time.
    requester = db.relationship("User", foreign_keys=[from_user])
    recipient = db.relationship("User", foreign_keys=[to_user])


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    exchange_request_id = db.Column(db.Integer, db.ForeignKey("exchange_requests.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Rating(db.Model):
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    exchange_request_id = db.Column(db.Integer, db.ForeignKey("exchange_requests.id"), nullable=False)
    from_user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AudioNote(db.Model):
    """
    A short audio recording attached to an exchange — either a mentor's
    reference recording ("play it like this") or a learner's practice
    attempt. Used later by the AI feedback feature to compare the two.
    """
    __tablename__ = "audio_notes"

    id = db.Column(db.Integer, primary_key=True)
    exchange_request_id = db.Column(db.Integer, db.ForeignKey("exchange_requests.id"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    note_type = db.Column(db.String(20), nullable=False)  # 'reference' or 'practice'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", foreign_keys=[uploaded_by])


class AIFeedback(db.Model):
    """
    Stores the AI-generated comparison text for a pair of audio notes, so
    it stays visible in the conversation instead of disappearing after
    being shown once.
    """
    __tablename__ = "ai_feedback"

    id = db.Column(db.Integer, primary_key=True)
    exchange_request_id = db.Column(db.Integer, db.ForeignKey("exchange_requests.id"), nullable=False)
    reference_note_id = db.Column(db.Integer, db.ForeignKey("audio_notes.id"), nullable=False)
    practice_note_id = db.Column(db.Integer, db.ForeignKey("audio_notes.id"), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
