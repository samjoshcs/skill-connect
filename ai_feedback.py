"""
AI voice-note feedback.

Kept in its own file, separate from routes.py, because it's the one piece
of the app that talks to an external AI service — easy to point to on its
own when explaining "how does the AI feature work."

How it works, in plain terms:
  1. A mentor uploads a short reference recording (e.g. playing a riff correctly)
  2. A learner uploads their own attempt at the same thing
  3. We send BOTH audio files to Gemini with a prompt asking it to compare
     them and give a few short, specific tips
  4. Gemini does the actual "listening" and comparison — this file just
     handles sending the request and returning the text response
"""

from google import genai
from config import Config

FEEDBACK_PROMPT = """You are a friendly, encouraging music mentor.
You are given two short audio recordings of the same musical exercise:
- The FIRST recording is the reference — how it's supposed to be played.
- The SECOND recording is a learner's practice attempt at the same thing.

Compare them and give the learner 2-3 short, specific, encouraging tips on
what to improve (for example: timing, pitch/tuning, rhythm, technique).
Keep it brief and supportive — a few sentences, not an essay."""


def get_practice_feedback(reference_path, practice_path):
    """
    Sends the two audio files to Gemini and returns its feedback as plain text.
    Returns a clear, friendly error message instead of raising an exception
    if anything goes wrong (missing API key, network issue, etc.) — a
    student demo should never crash outright from an API hiccup.
    """
    if not Config.GEMINI_API_KEY:
        return (
            "AI feedback isn't available right now — no Gemini API key is "
            "configured. Add one in config.py or as a GEMINI_API_KEY "
            "environment variable to enable this feature."
        )

    try:
        client = genai.Client(api_key=Config.GEMINI_API_KEY)

        # Gemini needs the audio files uploaded first, then referenced in
        # the actual generation request — similar idea to attaching files
        # to an email before sending it.
        reference_file = client.files.upload(file=reference_path)
        practice_file = client.files.upload(file=practice_path)

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[FEEDBACK_PROMPT, reference_file, practice_file],
        )

        return response.text.strip()

    except Exception as e:
        # In a student project, showing *something* useful is better than
        # a raw stack trace on screen. We still print the real error to the
        # server log so it can be debugged.
        print(f"[AI feedback error] {e}")
        return (
            "Something went wrong getting AI feedback. This can happen if "
            "the API key is invalid, the audio file is too long, or there's "
            "a network issue. Please try again."
        )
