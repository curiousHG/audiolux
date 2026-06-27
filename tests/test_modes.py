"""Colour <-> mode/family logic — the core of the 'red music, white light' bug."""
from backend import modes as M

COLOR_CAPABLE = ["Run", "Trailing", "Curtain"]   # Swab dropped (duplicate of Run)


def test_color_capable_families_have_full_color_set(catalog):
    for fam in COLOR_CAPABLE:
        colors = catalog[fam]
        for c in ("RD", "GN", "BU", "YE", "WH"):
            assert c in colors, f"{fam} should have colour {c}"


def test_strobe_is_white_only(catalog):
    # documents the catalog reality that caused the bug
    assert list(catalog["Strobe"].keys()) == ["White"]


def test_mood_families_exist_and_are_color_capable(catalog):
    for mood, prefs in M.MOOD_FAMILIES.items():
        present = [f for f in prefs if f in catalog]
        assert present, f"mood {mood} has no family in the catalog"
        # at least the top preference must be able to render a colour
        top = present[0]
        assert any(c in catalog[top] for c in M.SINGLE_COLORS), f"{top} is not colour-capable"


def test_mood_family_honors_requested_color(catalog):
    # the regression test: for every mood + every single colour, the chosen family
    # must actually contain that colour (so the light matches the music)
    for mood in range(4):
        for color in M.SINGLE_COLORS:
            fam = M.mood_family(catalog, mood, color)
            assert color in catalog[fam], f"mood {mood} colour {color}: {fam} lacks it"


def test_mood_family_never_picks_white_only_strobe_for_colors(catalog):
    for mood in range(4):
        for color in ("RD", "GN", "BU", "VT"):
            assert M.mood_family(catalog, mood, color) != "Strobe"


def test_resolve_mode_returns_matching_color(catalog, num2name):
    for fam in COLOR_CAPABLE:
        for color in ("RD", "GN", "BU", "YE"):
            num, label = M.resolve_mode(catalog, fam, color, forward=True)
            assert num is not None
            assert label == color
            assert color in num2name[num], f"{num2name[num]} should be a {color} mode"


def test_resolve_mode_reports_fallback_label(catalog):
    # a family without the colour falls back, and tells us what it actually used
    num, label = M.resolve_mode(catalog, "Strobe", "RD", forward=True)
    assert num is not None
    assert label == "White"                 # honest about the real colour
    assert M.label_color(label) == "WH"


def test_label_color_mapping():
    assert M.label_color("RD") == "RD"
    assert M.label_color("White") == "WH"
    assert M.label_color("7 Colors") == "7 Colors"
    assert M.label_color("Dreaming") is None


def test_pick_mode_matches_resolve(catalog):
    for fam in COLOR_CAPABLE:
        assert M.pick_mode(catalog, fam, "RD") == M.resolve_mode(catalog, fam, "RD")[0]
