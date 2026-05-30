"""
Emoji rendering support for ReportLab.

Detects emoji characters in text and renders them as PIL images that can be
embedded as inline images in a Paragraph via <img> tags.
"""
import os
import re
import tempfile
import unicodedata

# Base emoji character class (without quantifier) — used to build both regexes
_EMOJI_BASE = (
    '\U0001F600-\U0001F64F'   # emoticons
    '\U0001F300-\U0001F5FF'   # symbols & pictographs
    '\U0001F680-\U0001F6FF'   # transport & map
    '\U0001F700-\U0001F77F'   # alchemical
    '\U0001F780-\U0001F7FF'   # geometric extended
    '\U0001F800-\U0001F8FF'   # supplemental arrows-C
    '\U0001F900-\U0001F9FF'   # supplemental symbols
    '\U0001FA00-\U0001FA6F'   # chess
    '\U0001FA70-\U0001FAFF'   # symbols extended-A
    '\U0001F1E0-\U0001F1FF'   # regional indicator symbols (used in flag pairs)
    '\U00002702-\U000027B0'   # dingbats
    '\U0000231A-\U0000231B'   # watch, hourglass
    '\U00002300-\U000023FF'   # miscellaneous technical (⏰ ⌚ ⏳ etc.)
    '\U000025AA-\U000025FE'   # geometric shapes
    '\U00002600-\U000026FF'   # misc symbols block (☀☁☺☻⛄⛅⚽⚾ etc.)
    '\U00002702'              # scissors
    '\U00002705'              # check mark
    '\U00002708-\U0000270D'   # airplane-writing hand
    '\U0000270F'              # pencil
    '\U00002712'              # black nib
    '\U00002714'              # check mark
    '\U00002716'              # x
    '\U00002733-\U00002734'   # sparkles
    '\U00002744'              # snowflake
    '\U00002747'              # sparkle
    '\U0000274C'              # cross mark
    '\U0000274E'              # cross mark
    '\U00002753-\U00002755'   # questions
    '\U00002757'              # exclamation
    '\U00002763-\U00002764'   # hearts
    '\U00002795-\U00002797'   # plus/minus/divide
    '\U000027A1'              # right arrow
    '\U000027B0'              # curly loop
    '\U000027BF'              # double curly loop
)

# Optional modifiers that can follow a base emoji character
_EMOJI_MODIFIERS = (
    '️'                  # variation selector-16 (emoji presentation)
    '\U0001F3FB-\U0001F3FF'   # skin tone modifiers
)

# ZWJ (Zero Width Joiner) sequence pattern — two or more emoji joined by U+200D.
# Examples: 👨‍👩‍👧‍👦  🏳️‍🌈  👩‍💻
# Must be tried BEFORE the plain emoji pattern so the longer match wins.
_ZWJ_SEQ = (
    r'(?:[' + _EMOJI_BASE + r'][' + _EMOJI_MODIFIERS + r']*'
    r'(?:‍[' + _EMOJI_BASE + r'][' + _EMOJI_MODIFIERS + r']*)+)'
)

# Detects whether a string contains any emoji (one-or-more match is fine here).
# Covers: tag flags, regional indicator pairs, ZWJ sequences, standard emoji.
_EMOJI_RE = re.compile(
    r'(?:'
    r'\U0001F3F4[\U000E0020-\U000E007E]+\U000E007F'  # RGI tag flag (🏴󠁧󠁢󠁥󠁮󠁧󠁿)
    r'|[\U0001F1E0-\U0001F1FF]{2}'                    # regional indicator pair (🇹🇷)
    r'|' + _ZWJ_SEQ +                                 # ZWJ sequence (👨‍👩‍👧‍👦)
    r'|[' + _EMOJI_BASE + _EMOJI_MODIFIERS + r']+'
    r')',
    flags=re.UNICODE,
)

# Splits text into individual emoji tokens — matches ONE emoji grapheme at a time.
# Handles:
#   • RGI tag flag sequences  🏴󠁧󠁢󠁥󠁮󠁧󠁿  (black-flag + E00xx tag chars + cancel tag)
#   • Regional indicator pairs  🇹🇷  (two consecutive U+1F1E0–U+1F1FF chars)
#   • ZWJ sequences            👨‍👩‍👧‍👦  🏳️‍🌈  (emoji joined by U+200D)
#   • Standard emoji + optional variation-selector / skin-tone modifier
_EMOJI_SPLIT_RE = re.compile(
    r'(?:'
    r'\U0001F3F4[\U000E0020-\U000E007E]+\U000E007F'  # RGI tag flag (🏴󠁧󠁢󠁥󠁮󠁧󠁿)
    r'|[\U0001F1E0-\U0001F1FF]{2}'                    # regional indicator pair (🇹🇷)
    r'|' + _ZWJ_SEQ +                                 # ZWJ sequence (👨‍👩‍👧‍👦)
    r'|[' + _EMOJI_BASE + '][' + _EMOJI_MODIFIERS + r']*'
    r')',
    flags=re.UNICODE,
)

def has_emoji(text):
    """Return True if text contains emoji characters."""
    return bool(_EMOJI_RE.search(text))

def split_emoji(text):
    """Split text into (is_emoji, fragment) tuples, one emoji per tuple.

    Example:
        'Hello 😀🎉 World' -> [(False,'Hello '), (True,'😀'), (True,'🎉'), (False,' World')]
    """
    result = []
    last = 0
    for m in _EMOJI_SPLIT_RE.finditer(text):
        start, end = m.span()
        if start > last:
            result.append((False, text[last:start]))
        result.append((True, m.group()))
        last = end
    if last < len(text):
        result.append((False, text[last:]))
    return result


# ---------------------------------------------------------------------------
# Unknown-emoji handler
# ---------------------------------------------------------------------------

def _might_be_unknown_emoji(char):
    """Return True if *char* could be an unrecognized emoji worth trying to render.

    Uses unicodedata.category() to exclude every known text-script category
    (letters, digits, common punctuation, combining marks that belong to
    scripts) so that Arabic, Latin, CJK, Hebrew, etc. are never affected.
    Only characters in or above the misc-symbols zone that are NOT letters
    or digits pass through.
    """
    cp = ord(char)
    # Below the arrows/misc-symbols zone — plain text, leave as-is
    if cp < 0x2194:
        return False
    cat = unicodedata.category(char)
    # Letter categories (Lo, Ll, Lu, …) → text, not emoji
    if cat[0] == 'L':
        return False
    # Digit / numeric → text
    if cat[0] == 'N':
        return False
    # Control / format / surrogate / unassigned → skip silently
    # (TAG chars U+E0020–E007F are already consumed by the main regex)
    if cat[0] == 'C':
        return False
    # Separator (space-like) → keep as text
    if cat[0] == 'Z':
        return False
    # Everything else (Symbol So/Sm/Sk, Punctuation Po/Ps/Pe, Mark Mn/Mc)
    # at a high enough code point is a candidate for emoji rendering.
    return True


def _handle_unknown_emoji(text, font_size, valign):
    """Second-pass scanner for plain-text fragments that may contain emoji
    characters not caught by the main _EMOJI_SPLIT_RE (e.g. emoji added in
    newer Unicode versions, or unusual symbol characters).

    Returns a list of ``(is_img, content)`` pairs:
      - ``is_img=True``  → *content* is a ready-made ``<img …/>`` tag string.
      - ``is_img=False`` → *content* is a raw text chunk (caller must XML-escape).

    Behaviour for each candidate character:
      • PIL can render it  → emit as ``<img>`` tag.
      • PIL cannot render → character is **silently dropped** (avoids tofu /
        garbled glyphs showing up in the PDF).
    """
    parts = []
    buf = ''
    for char in text:
        if _might_be_unknown_emoji(char):
            render_size = max(64, font_size * 4)
            path = render_emoji_png(char, size=render_size)
            if path:
                if buf:
                    parts.append((False, buf))
                    buf = ''
                display_size = int(font_size * 1.2)
                parts.append((True,
                    f'<img src="{path}" width="{display_size}" '
                    f'height="{display_size}" valign="{valign}"/>'
                ))
            # else: PIL can't render → silently drop the character
        else:
            buf += char
    if buf:
        parts.append((False, buf))
    return parts


# Cache rendered emoji PNGs to avoid re-rendering the same emoji
_emoji_cache = {}

def _find_emoji_font():
    """Find a suitable emoji font on the system."""
    candidates = [
        '/System/Library/Fonts/Apple Color Emoji.ttc',           # macOS
        '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',     # Linux
        '/usr/share/fonts/noto-emoji/NotoColorEmoji.ttf',
        'C:/Windows/Fonts/seguiemj.ttf',                         # Windows
        '/usr/share/fonts/google-noto-emoji/NotoColorEmoji.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

_EMOJI_FONT_PATH = _find_emoji_font()


def render_emoji_png(emoji_char, size=64):
    """Render an emoji character to a PNG temp file, return the file path.

    Returns None if rendering is not possible.
    """
    cache_key = (emoji_char, size)
    if cache_key in _emoji_cache:
        return _emoji_cache[cache_key]

    if _EMOJI_FONT_PATH is None:
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    try:
        font = ImageFont.truetype(_EMOJI_FONT_PATH, size)
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), emoji_char, font=font, embedded_color=True)

        # Trim to bounding box and add small padding
        bbox = img.getbbox()
        if bbox is None:
            return None
        pad = max(2, size // 16)
        bbox = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad),
            min(img.height, bbox[3] + pad),
        )
        img = img.crop(bbox)

        # Convert RGBA to RGB with white background for JPEG compat,
        # but keep RGBA and save as PNG so transparency works in PDF.
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        img.save(tmp.name, 'PNG')
        tmp.close()

        _emoji_cache[cache_key] = tmp.name
        return tmp.name
    except Exception:
        return None


def text_to_rl_markup(text, font_size=12, valign='middle', rtl=False):
    """Convert a text string containing emojis into a ReportLab Paragraph
    markup string where each emoji is replaced by an <img> tag.

    The img width/height are set proportionally to font_size.
    Returns the original text unchanged if no emojis are found or rendering fails.

    rtl=True: reverse word order within each text segment so that ReportLab's
    word-merge step produces the correct visual order for RTL paragraphs.
    Without this, two-word Arabic segments (e.g. 'كيف حالك') after an image
    merge in logical order and read backwards after the [::-1] line reversal.
    """
    if not has_emoji(text):
        return text

    parts = split_emoji(text)
    result = []
    for is_emoji, fragment in parts:
        if not is_emoji:
            if rtl and fragment.strip():
                # Pre-reverse word order so the line-building merge happens in
                # correct visual order (ReportLab merges words left-to-right,
                # but RTL reversal only operates at the word level, not within
                # a merged word).
                # Process line-by-line to preserve \n separators — a plain
                # fragment.split() would eat every newline and collapse all
                # three paragraphs into one reversed word blob.
                lines = fragment.split('\n')
                reversed_lines = []
                for line in lines:
                    if line.strip():
                        leading = line[:len(line) - len(line.lstrip())]
                        trailing = line[len(line.rstrip()):]
                        words = line.split()
                        line = leading + ' '.join(reversed(words)) + trailing
                    reversed_lines.append(line)
                fragment = '\n'.join(reversed_lines)

            # Second pass: catch any unknown emoji that slipped through the
            # main regex (new Unicode emoji, unusual symbol sequences, etc.)
            sub_parts = _handle_unknown_emoji(fragment, font_size, valign)
            for is_img, content in sub_parts:
                if is_img:
                    result.append(content)
                else:
                    # Escape XML special characters in plain-text chunks
                    result.append(content
                                  .replace('&', '&amp;')
                                  .replace('<', '&lt;')
                                  .replace('>', '&gt;'))
        else:
            render_size = max(64, font_size * 4)
            path = render_emoji_png(fragment, size=render_size)
            if path:
                # Display at font_size × 1.2 to align nicely with text
                display_size = int(font_size * 1.2)
                result.append(
                    f'<img src="{path}" width="{display_size}" '
                    f'height="{display_size}" valign="{valign}"/>'
                )
            # else: known emoji that PIL cannot render → silently drop.
            # Previously fell through as raw characters, producing tofu/garbage.

    return ''.join(result)
