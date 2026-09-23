import hashlib
import os
import random
import uuid
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import UserSkill, User, ExchangeRequest, Message, Rating, AudioNote, AIFeedback
from matching import find_matches
from utils import linkify
from config import Config, BASE_DIR
from ai_feedback import get_practice_feedback

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "webm"}

TAGLINES = [
    "Someone's out there waiting to learn what you know.",
    "Pick up where you left off.",
    "New chords, new friends.",
    "Ready to trade some skills today?",
    "Your next collaborator is one match away.",
]

main_bp = Blueprint("main", __name__)


def _time_of_day_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


MUSIC_QUOTES = [
    ("Music is the universal language of mankind.", "Henry Wadsworth Longfellow"),
    ("Where words fail, music speaks.", "Hans Christian Andersen"),
    ("Music gives a soul to the universe, wings to the mind.", "Plato"),
    ("One good thing about music, when it hits you, you feel no pain.", "Bob Marley"),
    ("Without music, life would be a mistake.", "Friedrich Nietzsche"),
]


@main_bp.route("/")
def home():
    # If already logged in, skip the marketing homepage and go straight
    # to the dashboard — no point showing a "sign up" page to someone
    # who already has an account.
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    quote_text, quote_author = random.choice(MUSIC_QUOTES)
    return render_template("home.html", quote_text=quote_text, quote_author=quote_author)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    pending_received = ExchangeRequest.query.filter_by(
        to_user=current_user.id, status="pending"
    ).count()

    return render_template(
        "dashboard.html",
        pending_received=pending_received,
        greeting=_time_of_day_greeting(),
        tagline=random.choice(TAGLINES),
    )


@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.bio = request.form.get("bio", "").strip()
        current_user.availability = request.form.get("availability", "").strip()

        # Clear old skills and re-add from the form. Simpler than trying to
        # diff old vs new skill lists, and profiles aren't edited often
        # enough for this to be a performance concern.
        UserSkill.query.filter_by(user_id=current_user.id).delete()

        can_teach_raw = request.form.get("can_teach", "")
        wants_to_learn_raw = request.form.get("wants_to_learn", "")
        proficiency = request.form.get("proficiency", "beginner")

        # Support multiple skills separated by commas, e.g. "Guitar, Flute"
        # -> ["Guitar", "Flute"]. Splitting on "," and stripping whitespace
        # from each piece means "Guitar,Flute" and "Guitar, Flute" both work.
        can_teach_list = [s.strip() for s in can_teach_raw.split(",") if s.strip()]
        wants_to_learn_list = [s.strip() for s in wants_to_learn_raw.split(",") if s.strip()]

        for skill_name in can_teach_list:
            db.session.add(UserSkill(
                user_id=current_user.id,
                skill_name=skill_name,
                type="can_teach",
                proficiency=proficiency,
            ))
        for skill_name in wants_to_learn_list:
            db.session.add(UserSkill(
                user_id=current_user.id,
                skill_name=skill_name,
                type="wants_to_learn",
            ))

        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("edit_profile.html")


@main_bp.route("/matches")
@login_required
def matches():
    # If the user hasn't listed anything yet, matching can't work —
    # send them to complete their profile first instead of showing an
    # empty, confusing page.
    if not current_user.can_teach_skills() and not current_user.wants_to_learn_skills():
        flash("Add your skills first so we can find matches for you.", "info")
        return redirect(url_for("main.edit_profile"))

    mutual, partial = find_matches(current_user.id)

    # Figure out which of these users I've already sent a request to,
    # so the template can show "Requested" instead of the button again.
    sent_to_ids = {
        r.to_user for r in ExchangeRequest.query.filter_by(from_user=current_user.id).all()
    }

    return render_template("matches.html", mutual=mutual, partial=partial, sent_to_ids=sent_to_ids)


@main_bp.route("/explore")
@login_required
def explore():
    """
    Unlike /matches (which only shows people whose skills complement
    yours), this shows EVERYONE on the platform — useful for just browsing
    who's around, or finding someone whose skills don't happen to overlap
    with yours but you still want to reach out to.
    """
    skill_filter = request.args.get("skill", "").strip()

    query = User.query.filter(User.id != current_user.id)
    users = query.order_by(User.created_at.desc()).all()

    # Only show people who've actually listed at least one skill — an
    # empty profile isn't useful to browse.
    users = [u for u in users if u.can_teach_skills() or u.wants_to_learn_skills()]

    if skill_filter:
        # Simple case-insensitive substring match across both what they
        # teach and what they want to learn.
        def matches_filter(u):
            all_skill_names = [s.skill_name.lower() for s in u.skills]
            return any(skill_filter.lower() in name for name in all_skill_names)
        users = [u for u in users if matches_filter(u)]

    sent_to_ids = {
        r.to_user for r in ExchangeRequest.query.filter_by(from_user=current_user.id).all()
    }

    return render_template(
        "explore.html",
        users=users,
        skill_filter=skill_filter,
        sent_to_ids=sent_to_ids,
    )


@main_bp.route("/request/send/<int:user_id>", methods=["POST"])
@login_required
def send_request(user_id):
    # Lets the caller specify where to return to afterward, instead of
    # always landing on Matches. Only accepts an internal path (starts
    # with "/") so this can't be abused to redirect somewhere outside the app.
    next_url = request.form.get("next", "")
    fallback_url = url_for("main.matches")
    return_url = next_url if next_url.startswith("/") else fallback_url

    if user_id == current_user.id:
        flash("You can't send a request to yourself.", "error")
        return redirect(return_url)

    # Avoid creating duplicate pending requests to the same person.
    existing = ExchangeRequest.query.filter_by(
        from_user=current_user.id, to_user=user_id, status="pending"
    ).first()
    if existing:
        flash("You've already sent a request to this person.", "info")
        return redirect(return_url)

    new_request = ExchangeRequest(
        from_user=current_user.id,
        to_user=user_id,
        message=request.form.get("message", "").strip(),
    )
    db.session.add(new_request)
    db.session.commit()
    flash("Request sent!", "success")
    return redirect(return_url)


@main_bp.route("/requests")
@login_required
def view_requests():
    received = ExchangeRequest.query.filter_by(to_user=current_user.id).order_by(
        ExchangeRequest.created_at.desc()
    ).all()
    sent = ExchangeRequest.query.filter_by(from_user=current_user.id).order_by(
        ExchangeRequest.created_at.desc()
    ).all()
    return render_template("requests.html", received=received, sent=sent)


@main_bp.route("/request/<int:request_id>/respond", methods=["POST"])
@login_required
def respond_request(request_id):
    exchange = ExchangeRequest.query.get_or_404(request_id)

    # Only the person the request was sent TO is allowed to accept/decline it.
    if exchange.to_user != current_user.id:
        flash("You can't respond to this request.", "error")
        return redirect(url_for("main.view_requests"))

    decision = request.form.get("decision")
    if decision in ("accepted", "declined"):
        exchange.status = decision
        db.session.commit()
        flash(f"Request {decision}.", "success")

    return redirect(url_for("main.view_requests"))


def _get_exchange_or_403(exchange_id):
    """
    Shared check used by every messaging route: makes sure the exchange
    exists, the current user is actually one of the two people involved
    (not just anyone guessing a URL), and it's been accepted — messaging
    only unlocks after both sides have agreed to the exchange.
    """
    exchange = ExchangeRequest.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.from_user, exchange.to_user):
        flash("You don't have access to this conversation.", "error")
        return None
    if exchange.status not in ("accepted", "completed"):
        flash("This conversation isn't available yet.", "error")
        return None
    return exchange


@main_bp.route("/conversations")
@login_required
def conversations():
    accepted = ExchangeRequest.query.filter(
        ExchangeRequest.status.in_(["accepted", "completed"]),
        (ExchangeRequest.from_user == current_user.id) | (ExchangeRequest.to_user == current_user.id)
    ).order_by(ExchangeRequest.created_at.desc()).all()

    return render_template("conversations.html", exchanges=accepted)


import hashlib

def _video_room_name(exchange_id):
    """
    Builds a unique, hard-to-guess room name for Jitsi Meet, so two random
    strangers can't accidentally (or deliberately) land in the same video
    call room. We combine the exchange id with a short hash of the app's
    secret key — good enough obscurity for a student project; a production
    app would use a proper random token stored in the database instead.
    """
    raw = f"{exchange_id}-{Config.SECRET_KEY}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:10]
    return f"skillconnect-{exchange_id}-{short_hash}"


@main_bp.route("/conversation/<int:exchange_id>")
@login_required
def conversation(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    other_user = exchange.recipient if exchange.from_user == current_user.id else exchange.requester
    messages = Message.query.filter_by(exchange_request_id=exchange.id).order_by(Message.created_at.asc()).all()

    my_rating = None
    if exchange.status == "completed":
        my_rating = Rating.query.filter_by(
            exchange_request_id=exchange.id, from_user=current_user.id
        ).first()

    audio_notes = AudioNote.query.filter_by(exchange_request_id=exchange.id).order_by(AudioNote.created_at.desc()).all()
    feedback_entries = AIFeedback.query.filter_by(exchange_request_id=exchange.id).order_by(AIFeedback.created_at.desc()).all()

    return render_template(
        "conversation.html",
        exchange=exchange,
        other_user=other_user,
        messages=messages,
        my_rating=my_rating,
        video_room=_video_room_name(exchange.id),
        audio_notes=audio_notes,
        feedback_entries=feedback_entries,
    )


@main_bp.route("/conversation/<int:exchange_id>/send", methods=["POST"])
@login_required
def send_message(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    text = request.form.get("message_text", "").strip()
    if text:
        db.session.add(Message(
            exchange_request_id=exchange.id,
            sender_id=current_user.id,
            message_text=text,
        ))
        db.session.commit()

    return redirect(url_for("main.conversation", exchange_id=exchange.id))


@main_bp.route("/conversation/<int:exchange_id>/poll")
@login_required
def poll_messages(exchange_id):
    """
    This is what the JavaScript on the conversation page calls every few
    seconds to check for new messages. It only returns messages newer than
    `after_id` (the id of the last message the browser already has), so we're
    not re-sending the whole conversation every time — just what's new.
    """
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return jsonify({"error": "not allowed"}), 403

    after_id = request.args.get("after_id", 0, type=int)

    new_messages = Message.query.filter(
        Message.exchange_request_id == exchange.id,
        Message.id > after_id
    ).order_by(Message.created_at.asc()).all()

    return jsonify([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": "You" if m.sender_id == current_user.id else exchange_other_name(exchange, current_user.id),
            "text": str(linkify(m.message_text)),
            "is_me": m.sender_id == current_user.id,
            # Sent as raw UTC ISO format — the browser converts this to the
            # viewer's own local time when displaying it (see the JS below),
            # rather than the server guessing everyone's timezone.
            "created_at_utc": m.created_at.isoformat() + "Z",
        }
        for m in new_messages
    ])


def exchange_other_name(exchange, my_id):
    other = exchange.recipient if exchange.from_user == my_id else exchange.requester
    return other.name if other else "Them"


@main_bp.route("/exchange/<int:exchange_id>/complete", methods=["POST"])
@login_required
def complete_exchange(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    if exchange.status == "accepted":
        exchange.status = "completed"
        db.session.commit()
        flash("Exchange marked as completed — you can now rate each other.", "success")

    return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="rating"))


@main_bp.route("/exchange/<int:exchange_id>/rate", methods=["POST"])
@login_required
def rate_exchange(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    if exchange.status != "completed":
        flash("You can only rate an exchange after it's marked completed.", "error")
        return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="rating"))

    # Don't allow rating the same exchange twice.
    already_rated = Rating.query.filter_by(
        exchange_request_id=exchange.id, from_user=current_user.id
    ).first()
    if already_rated:
        flash("You've already rated this exchange.", "info")
        return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="rating"))

    other_user_id = exchange.to_user if exchange.from_user == current_user.id else exchange.from_user

    try:
        rating_value = int(request.form.get("rating", 0))
    except ValueError:
        rating_value = 0

    if rating_value < 1 or rating_value > 5:
        flash("Please choose a rating between 1 and 5.", "error")
        return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="rating"))

    db.session.add(Rating(
        exchange_request_id=exchange.id,
        from_user=current_user.id,
        to_user=other_user_id,
        rating=rating_value,
        comment=request.form.get("comment", "").strip(),
    ))
    db.session.commit()
    flash("Thanks for rating your exchange partner!", "success")
    return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="rating"))


def _allowed_audio_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


@main_bp.route("/conversation/<int:exchange_id>/upload_audio", methods=["POST"])
@login_required
def upload_audio(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    audio_file = request.files.get("audio_file")
    note_type = request.form.get("note_type", "practice")

    if not audio_file or audio_file.filename == "":
        flash("Please choose an audio file to upload.", "error")
        return redirect(url_for("main.conversation", exchange_id=exchange.id))

    if not _allowed_audio_file(audio_file.filename):
        flash("Please upload an audio file (mp3, wav, m4a, ogg, or webm).", "error")
        return redirect(url_for("main.conversation", exchange_id=exchange.id))

    # Save with a random filename to avoid two different uploads accidentally
    # overwriting each other if they happen to share the same original name.
    ext = audio_file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    exchange_folder = os.path.join(Config.UPLOAD_FOLDER, "audio", str(exchange.id))
    os.makedirs(exchange_folder, exist_ok=True)
    save_path = os.path.join(exchange_folder, safe_name)
    audio_file.save(save_path)

    # Stored relative to static/ so it's easy to build a URL for playback later.
    relative_path = os.path.join("uploads", "audio", str(exchange.id), safe_name)

    db.session.add(AudioNote(
        exchange_request_id=exchange.id,
        uploaded_by=current_user.id,
        file_path=relative_path,
        note_type=note_type if note_type in ("reference", "practice") else "practice",
    ))
    db.session.commit()
    flash("Audio uploaded!", "success")
    return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="practice"))


@main_bp.route("/conversation/<int:exchange_id>/get_feedback", methods=["POST"])
@login_required
def get_feedback(exchange_id):
    exchange = _get_exchange_or_403(exchange_id)
    if not exchange:
        return redirect(url_for("main.conversations"))

    latest_reference = AudioNote.query.filter_by(
        exchange_request_id=exchange.id, note_type="reference"
    ).order_by(AudioNote.created_at.desc()).first()

    latest_practice = AudioNote.query.filter_by(
        exchange_request_id=exchange.id, note_type="practice"
    ).order_by(AudioNote.created_at.desc()).first()

    if not latest_reference or not latest_practice:
        flash("You need both a reference recording and a practice recording before requesting feedback.", "error")
        return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="practice"))

    reference_full_path = os.path.join(BASE_DIR, "static", latest_reference.file_path)
    practice_full_path = os.path.join(BASE_DIR, "static", latest_practice.file_path)

    feedback_text = get_practice_feedback(reference_full_path, practice_full_path)

    db.session.add(AIFeedback(
        exchange_request_id=exchange.id,
        reference_note_id=latest_reference.id,
        practice_note_id=latest_practice.id,
        feedback_text=feedback_text,
    ))
    db.session.commit()

    flash("AI feedback ready!", "success")
    return redirect(url_for("main.conversation", exchange_id=exchange.id, tab="practice"))
