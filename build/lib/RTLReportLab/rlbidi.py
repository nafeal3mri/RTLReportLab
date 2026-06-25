"""
rlbidi - RTL/BiDi support for ReportLab using python-bidi and arabic-reshaper.

Provides log2vis() compatible with ReportLab's internal bidi interface.
"""
import unicodedata

try:
    from bidi.algorithm import (
        get_empty_storage, get_base_level, get_embedding_levels,
        explicit_embed_and_overrides, resolve_weak_types,
        resolve_neutral_types, resolve_implicit_levels,
        reorder_resolved_levels, apply_mirroring, PARAGRAPH_LEVELS,
    )
    try:
        from bidi.algorithm import _embedding_direction
    except ImportError:                       # pragma: no cover - version drift
        def _embedding_direction(level):
            return 'L' if (level % 2) == 0 else 'R'
    _bidi_available = True
except ImportError:
    _bidi_available = False

try:
    import arabic_reshaper as _arabic_reshaper
    _reshaper_available = True
except ImportError:
    _reshaper_available = False

# Unicode ranges that benefit from Arabic reshaping
_ARABIC_RANGES = (
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    (0x08A0, 0x08FF),   # Arabic Extended-A
)

def _contains_arabic(text):
    for ch in text:
        cp = ord(ch)
        for lo, hi in _ARABIC_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def _reshape_arabic(text):
    """Apply Arabic letter reshaping if text contains Arabic characters.

    arabic_reshaper can raise (e.g. ``IndexError``) on some emoji / combining
    sequences; fall back to the unreshaped text rather than letting the whole
    PDF build crash.
    """
    if _reshaper_available and _contains_arabic(text):
        try:
            return _arabic_reshaper.reshape(text)
        except Exception:
            return text
    return text


def _remove_directional_marks(text):
    """Remove Unicode directional control characters (LRM, RLM, LRE, RLE, etc.)."""
    _marks = frozenset('‎‏‪‫‬‭‮⁦⁧⁨⁩')
    return ''.join(ch for ch in text if ch not in _marks)


def log2vis(text, base_direction='RTL', clean=True, positions_V_to_L=None):
    """Convert logical-order text to visual-order text.

    Args:
        text:              Input text in logical order.
        base_direction:    'RTL' or 'LTR' (default 'RTL').
        clean:             If True, strip Unicode directional marks from output.
        positions_V_to_L:  If a list is provided, it will be filled with
                           indices mapping visual position → logical position.

    Returns:
        Text in visual display order (with Arabic reshaping applied).
    """
    if not _bidi_available:
        raise ImportError('python-bidi is not installed; pip install python-bidi')

    if not text:
        if positions_V_to_L is not None:
            positions_V_to_L.extend([])
        return text

    reshaped = _reshape_arabic(text)

    # python-bidi 0.6.x does not implement the Unicode 6.3+ isolate algorithm
    # (RLI U+2067, LRI U+2066, FSI U+2068, PDI U+2069).  Those characters are
    # invisible control marks that survive explicit_embed_and_overrides with
    # their original type, then hit an assertion in resolve_implicit_levels:
    #   "RLI not allowed here"
    # Strip them from the INPUT before the algorithm runs; they are also
    # stripped from the output by the existing `clean` pass below.
    reshaped = _remove_directional_marks(reshaped)

    # Run the BiDi algorithm step by step so we can track positions
    storage = get_empty_storage()
    if base_direction and base_direction.upper() == 'RTL':
        storage['base_level'] = 1
        storage['base_dir'] = 'R'
    elif base_direction and base_direction.upper() == 'LTR':
        storage['base_level'] = 0
        storage['base_dir'] = 'L'
    else:
        base_level = get_base_level(reshaped)
        storage['base_level'] = base_level
        storage['base_dir'] = ('L', 'R')[base_level]

    get_embedding_levels(reshaped, storage, False, False)
    explicit_embed_and_overrides(storage, False)
    resolve_weak_types(storage, False)
    resolve_neutral_types(storage, False)

    # python-bidi only guarantees the types L, R, EN, AN survive into
    # resolve_implicit_levels.  In practice a few inputs slip a still-neutral or
    # format/boundary type (B, S, WS, ON, BN, NSM, isolate types, …) through the
    # weak/neutral passes — e.g. an emoji <img> placeholder, a paragraph that was
    # split mid-run, or characters this bidi build mishandles — and the next step
    # aborts with `AssertionError: <type> not allowed here`.  Coerce any such
    # straggler to its embedding direction (the UBA N2 fallback) so the algorithm
    # can never assert, whatever the input or library version.
    _ALLOWED = ('L', 'R', 'EN', 'AN')
    for _ch in storage['chars']:
        if _ch['type'] not in _ALLOWED:
            _ch['type'] = _embedding_direction(_ch['level'])

    resolve_implicit_levels(storage, False)

    # Inject original indices before reordering
    for i, ch_dict in enumerate(storage['chars']):
        ch_dict['_idx'] = i

    reorder_resolved_levels(storage, False)
    apply_mirroring(storage, False)

    chars = storage['chars']
    display = ''.join(c['ch'] for c in chars)

    if positions_V_to_L is not None:
        positions_V_to_L.extend(c['_idx'] for c in chars)

    if clean:
        display = _remove_directional_marks(display)
        # If we cleaned chars, rebuild V2L without those positions
        if positions_V_to_L is not None:
            _marks = frozenset('‎‏‪‫‬‭‮⁦⁧⁨⁩')
            cleaned_v2l = [c['_idx'] for c in chars if c['ch'] not in _marks]
            del positions_V_to_L[:]
            positions_V_to_L.extend(cleaned_v2l)

    return display
