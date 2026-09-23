# SkillConnect — Setup & Run Guide

## What's built so far
- Full folder structure (Flask "application factory" pattern with blueprints)
- Database models for all 5 tables (users, user_skills, exchange_requests, messages, ratings, plus audio_notes and ai_feedback for the AI feature)
- **Auth module — fully working:** signup, login, logout (passwords hashed, never stored in plain text)
- **Profile module — fully working:** edit bio, availability, multiple "can teach" / "wants to learn" skills (comma-separated)
- **Matches module — fully working:** browse other users, mutual (two-way) matches shown first, one-directional matches shown below
- **Requests module — fully working:** send an exchange request, view sent/received requests, accept/decline
- **Messaging module — fully working:** conversation list, chat page with polling-based live updates (new messages appear within ~3 seconds, no page reload), links in messages are automatically made clickable, access is locked to only the two people in the exchange
- **Ratings module — fully working:** mark an exchange as completed, both people rate each other (1-5 stars + optional comment), can't rate before completion or rate twice, average rating shows on match cards
- **Video call button — fully working:** embeds a free Jitsi Meet room (no account/API key needed) directly in the chat page, unique per exchange, only connects when you actually click the button (not automatically)
- **AI voice-note feedback — built, needs your Gemini API key to fully test:** upload a reference recording and a practice attempt on the chat page, click "Get AI feedback," and Gemini compares the two and returns a few tips. Tested everything except the actual AI call (file upload, storage, display, and the "no API key configured" fallback message all confirmed working) — see the "Setting up AI feedback" section below.
- Dashboard page linking into all of the above
- Custom design (no default Bootstrap look) — dark, music-inspired theme

## How to run it yourself

1. Install Python 3.10+ if you don't have it.
2. Open a terminal in this folder and install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the app:
   ```
   python app.py
   ```
4. Open your browser to: **http://127.0.0.1:5000**

The database (`skillconnect.db`) is created automatically the first time you run it — it's a SQLite file, so there's nothing else to install or configure.

## Try it out
1. Go to `/signup`, create an account
2. You'll be sent straight to your profile — fill in a skill you can teach and one you want to learn
3. You'll land on the dashboard and see your skills displayed as pills
4. Try logging out and back in

## Deploying to Render (free hosting)

Render can host this whole app for free — one service handles both your Flask app and (optionally) a PostgreSQL database.

### Step 1: Push your code to GitHub
1. Make sure `.gitignore` is in your project folder (it already is) — this keeps your database file, uploaded files, and cache files out of GitHub.
2. If your `config.py` still has a real API key typed directly into it, remove it first — Step 3 below sets it safely instead.
3. Push as normal:
   ```
   git init
   git add .
   git commit -m "SkillConnect"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

### Step 2: Create the database on Render
1. Go to [render.com](https://render.com) and sign up/log in (GitHub login is easiest)
2. Click **New +** → **PostgreSQL**
3. Give it any name (e.g. `skillconnect-db`), keep the free plan, click **Create Database**
4. Once it's ready, copy the **Internal Database URL** shown on its page — you'll need it in Step 3

### Step 3: Create the web service
1. Click **New +** → **Web Service**
2. Connect your GitHub repo (Render will ask for permission the first time)
3. Fill in:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Under **Environment Variables**, add:
   | Key | Value |
   |---|---|
   | `SECRET_KEY` | any random long string, e.g. `sk_a8f3k2m9x7q1` |
   | `DATABASE_URL` | paste the Internal Database URL from Step 2 |
   | `GEMINI_API_KEY` | your real Gemini API key |
5. Click **Create Web Service**

Render will build and deploy automatically — this takes a few minutes the first time. You'll get a live URL like `https://skillconnect-xyz.onrender.com`.

### Known limitations on Render's free tier (honest, worth mentioning in your report)
- **Free web services "sleep"** after 15 minutes of no traffic, and take ~30-50 seconds to wake up on the next visit — normal for free hosting, not a bug in your code.
- **Uploaded audio files may not persist** across redeploys on the free tier, since the filesystem isn't guaranteed to stick around. A production version would store uploads in cloud storage (e.g. AWS S3) instead — reasonable to mention as future scope.
- The free PostgreSQL database expires after 90 days on Render's free tier — fine for a semester project, just something to know if you need it live for a long time.

## Switching to MySQL later (for your final submission)
Right now the project uses SQLite because it needs zero setup — perfect while you're actively building. When you're ready to switch to MySQL (as stated in your proposal):

1. Install the MySQL driver: `pip install pymysql --break-system-packages`
2. In `config.py`, replace the `SQLALCHEMY_DATABASE_URI` line with:
   ```python
   SQLALCHEMY_DATABASE_URI = "mysql+pymysql://your_username:your_password@localhost/skillconnect"
   ```
3. Create an empty `skillconnect` database in MySQL first (e.g., via phpMyAdmin or the MySQL command line: `CREATE DATABASE skillconnect;`)
4. Run `python app.py` again — Flask-SQLAlchemy will create all the tables in MySQL automatically, same as it did in SQLite.

Nothing else in the code needs to change — this is the benefit of using SQLAlchemy instead of writing raw SQL queries.

## Project structure
```
skillconnect/
├── app.py                 # Creates and runs the Flask app
├── config.py               # Database & upload settings
├── extensions.py            # Shared db/login_manager instances (avoids circular imports)
├── models.py                # All 7 database tables defined as Python classes
├── matching.py               # The mutual-match logic — kept separate so it's easy to point to
├── utils.py                  # Small helpers (e.g. linkify — turns links in messages into clickable ones)
├── ai_feedback.py             # Calls Gemini to compare a reference recording vs a practice attempt
├── requirements.txt
├── auth/
│   └── routes.py            # /signup, /login, /logout
├── main/
│   └── routes.py            # /, /dashboard, /profile/edit, /matches, /requests, /conversation/...
├── templates/                # HTML pages (Jinja2 templates)
│   ├── base.html             # Shared layout (navbar, footer, flash messages)
│   ├── home.html
│   ├── signup.html
│   ├── login.html
│   ├── edit_profile.html
│   ├── dashboard.html
│   ├── matches.html
│   ├── requests.html
│   ├── conversations.html
│   └── conversation.html      # The chat page — has the polling JavaScript at the bottom
└── static/
    ├── css/style.css
    └── uploads/               # For profile photos / voice notes later
```

## Setting up AI feedback (Gemini API)
1. Get a free API key from https://aistudio.google.com/app/apikey (needs a Google account, no payment info required for the free tier)
2. Set it as an environment variable before running the app:
   ```
   # Mac/Linux
   export GEMINI_API_KEY="your-key-here"
   python app.py

   # Windows (Command Prompt)
   set GEMINI_API_KEY=your-key-here
   python app.py
   ```
   Or, for quick local testing only, paste it directly into `config.py` on the `GEMINI_API_KEY` line — just don't commit that to GitHub with a real key in it.
3. Without a key set, the "Get AI feedback" button still works — it just returns a friendly message explaining that no key is configured, instead of crashing. This means the rest of the app is fully testable even before you set up Gemini.

## What's next (in build order)
1. **Admin panel**

## Notes on how the code is organized (for your viva)
- **Blueprints** (`auth/`, `main/`) split routes into feature modules instead of one giant file — each one is small and focused.
- **`extensions.py`** exists purely to avoid a Python "circular import" error — `db` is created once here with no app attached, then connected to the real app inside `app.py`.
- **Passwords** are never stored directly — `werkzeug.security.generate_password_hash` turns them into an irreversible hash, and `check_password_hash` verifies a login attempt against that hash without ever decrypting it back.
- **Flask-Login** handles "remembering" that a user is logged in via a secure session cookie — `@login_required` on a route just checks that cookie before letting the request through.
