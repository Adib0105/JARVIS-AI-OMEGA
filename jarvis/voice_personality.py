from __future__ import annotations

import re

# Speech-only formatting. The chat transcript remains unchanged.
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MARKDOWN_RE = re.compile(r"[*_>#~|]+")
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+", re.UNICODE)
_LONG_ID_RE = re.compile(r"\b(?=[A-Za-z0-9_-]{24,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_-]+\b")
_PERCENT_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*%")
_BULLET_RE = re.compile(r"(?:^|\n)\s*(?:[-+•]|\d+[.)])\s+", re.MULTILINE)
_WS_RE = re.compile(r"\s+")


def speechify(text: str) -> str:
    """Turn display-oriented assistant text into natural TTS text.

    This deliberately removes formatting/noise rather than changing meaning.
    URLs, code blocks and opaque IDs are not read aloud by default.
    """
    value = str(text or "")
    if not value.strip():
        return ""

    value = _CODE_BLOCK_RE.sub(" The code is shown on screen. ", value)
    value = _MARKDOWN_LINK_RE.sub(r"\1", value)
    value = _URL_RE.sub(" the link shown on screen ", value)
    value = _INLINE_CODE_RE.sub(r"\1", value)
    value = _EMOJI_RE.sub(" ", value)
    value = _LONG_ID_RE.sub(" the identifier shown on screen ", value)
    value = _BULLET_RE.sub(". ", value)
    value = _MARKDOWN_RE.sub("", value)
    value = _PERCENT_RE.sub(r"\1 percent", value)

    # Spoken punctuation: preserve sentence rhythm, remove visual separators.
    value = value.replace("→", " then ").replace("=>", " then ")
    value = value.replace("//", ". ").replace("::", ": ")
    value = re.sub(r"[-=]{3,}", ". ", value)
    value = re.sub(r"\.{3,}", "…", value)
    value = _WS_RE.sub(" ", value).strip(" .")
    if value and value[-1] not in ".!?…":
        value += "."
    return value


def conversational_system_instructions() -> str:
    """Prompt fragment for responses that are pleasant when spoken aloud."""
    return """VOICE-FIRST CONVERSATION
- Sound like a premium modern personal assistant: warm, calm, intelligent, confident, friendly, and subtly futuristic.
- Never imitate or claim to be a specific real person or proprietary assistant voice.
- Match the user's language naturally: English -> English, Hindi -> natural Hindi, Hinglish -> natural Hinglish.
- Prefer conversational phrasing over text that sounds like a report being read aloud.
- For simple requests, answer briefly and directly. Natural phrases such as “Done.”, “Got it.”, “Checking that.”, or “Yeah, I found it.” are fine when truthful.
- Do not repeatedly say “Sir”, “Certainly”, “Of course”, or “How may I assist you?”. Use formal address only when it genuinely fits.
- Avoid excessive headings, emoji, decorative punctuation, and long preambles in ordinary conversation.
- Use short sentences and natural thought breaks. Emphasize the important result first.
- Be slightly expressive but never theatrical, overly enthusiastic, or robotic.
- When an action is still running, say so briefly; never claim completion before verification.
""".strip()
