"""
Small, standalone helper functions used across the app.
Kept separate from routes.py so each one is easy to find and explain on its own.
"""

import re
from markupsafe import Markup, escape

URL_PATTERN = re.compile(r'(https?://\S+)')


def linkify(text):
    """
    Turns any http(s):// links inside a plain-text message into clickable
    <a> tags, so a mentor can share a YouTube tutorial or a Zoom link and
    the learner can just click it instead of copy-pasting.

    We escape the text FIRST (to prevent someone injecting raw HTML/JS into
    a message — a basic but important security habit), then only afterwards
    wrap anything that looks like a URL in a link tag.
    """
    safe_text = str(escape(text))  # neutralise any HTML in the message itself
    linked = URL_PATTERN.sub(
        lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        safe_text
    )
    return Markup(linked)  # tells Jinja "this is safe HTML, don't escape it again"
