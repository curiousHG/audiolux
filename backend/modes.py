"""Effect-mode catalog (extracted from the app's `dmx03_model` resource array)
and classification into families + Forward/Backward pairs."""
import collections
import json
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODES_FILE = os.path.join(_HERE, "modes_dmx03.json")

# Most specific family names first so "Curtain Swab" wins over "Curtain"/"Swab".
FAMILIES = ["Curtain Swab", "Follow Spot", "Horse Race", "Trailing", "Streaming",
            "Flutter", "Curtain", "Dreaming", "Strobe", "Swab", "Run", "Flow", "Hop"]

# Redundant duplicates dropped from the catalog (see docs/MODES.md).
DROP_FAMILIES = {"Swab", "Follow Spot"}

# Forward variant is broken on the strip — always send Backward.
FORCE_BACKWARD = {"Horse Race"}

DYNAMIC_FAMILIES = {"Run", "Trailing", "Curtain", "Flow", "Streaming", "Flutter", "Hop"}


def load_modes(path: str = _MODES_FILE):
    """Load the raw effect-mode list from the JSON catalog file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify(modes):
    """Group modes by family, pairing each effect's two variants by mode NUMBER
    (lower = forward/open, higher = backward/close). We pair by number rather than
    the text label because the app's data mislabels some 'Backward' entries as
    'Forward' (e.g. 197 & 198 both say 'Forward Swab CN')."""
    order, groups_accum = [], {}
    for mode_obj in modes:
        mode_num, name = mode_obj["n"], mode_obj["name"]
        if name.strip().upper() == "AUTO":
            fam, base, is_open_close = "Auto", "AUTO", False
        else:
            base, is_open_close = name, False
            for p in ("Forward ", "Backward ", "Open ", "Close "):
                if name.startswith(p):
                    base, is_open_close = name[len(p):], p in ("Open ", "Close ")
                    break
            # The 1-22 rainbow-gradient block (and anything unmatched) is the Dreaming family.
            fam = next((f for f in FAMILIES if f in base), "Dreaming")
        key = (fam, base)
        if key not in groups_accum:
            groups_accum[key] = {"fam": fam, "base": base, "nums": [], "oc": False}
            order.append(key)
        groups_accum[key]["nums"].append(mode_num)
        groups_accum[key]["oc"] = groups_accum[key]["oc"] or is_open_close

    groups = collections.OrderedDict()
    for key in order:
        entry = groups_accum[key]
        nums = sorted(set(entry["nums"]))
        effect = {"name": entry["base"]}
        if len(nums) == 1:
            effect["single"] = nums[0]
        elif entry["oc"]:
            effect["open"], effect["close"] = nums[0], nums[1]
        else:
            effect["fwd"], effect["bwd"] = nums[0], nums[1]
        groups.setdefault(entry["fam"], []).append(effect)
    return [{"family": fam, "effects": effs} for fam, effs in groups.items()
            if fam not in DROP_FAMILIES]


def dynamic_pool(grouped, families=None):
    """Forward mode numbers of the dynamic families — a curated pool for beat-driven
    mode switching."""
    families = families or DYNAMIC_FAMILIES
    pool = []
    for g in grouped:
        if g["family"] in families:
            for e in g["effects"]:
                if "fwd" in e:
                    pool.append(e["fwd"])
    return pool or [95]


SINGLE_COLORS = ["RD", "YE", "GN", "CN", "BU", "VT", "WH"]
# Frequency -> colour (bass..treble): bass/kick = red, hi-hats/air = white.
FREQ_COLORS = ["RD", "VT", "BU", "GN", "YE", "WH"]
COLOR_HEX = {"RD": "#ff3030", "YE": "#ffe000", "GN": "#33ff33", "CN": "#00e0ff",
             "BU": "#3060ff", "VT": "#a000ff", "WH": "#ffffff", "7 Colors": "#ff48b0"}


def build_family_catalog(grouped):
    """{family: {color_code: {fwd/bwd/open/close/single}}} — lets the engine pick a
    specific colour variant within a family (colour chosen from the audio frequency)."""
    cat = collections.OrderedDict()
    for g in grouped:
        fam = g["family"]
        if fam in ("Auto",):
            continue
        colors = collections.OrderedDict()
        for e in g["effects"]:
            base = e["name"]
            color = base[len(fam):].strip() if base.startswith(fam) else base
            colors[color or base] = {k: e[k] for k in
                                     ("fwd", "bwd", "open", "close", "single") if k in e}
        cat[fam] = colors
    return cat


# Music mood -> preferred families. Only colour-capable families (Run/Trailing/
# Curtain) are listed so the music's colour is always honoured.
MOOD_NAMES = ["calm", "groove", "drive", "peak"]
MOOD_FAMILIES = {
    0: ["Trailing", "Curtain", "Run"],
    1: ["Curtain", "Trailing", "Run"],
    2: ["Run", "Curtain", "Trailing"],
    3: ["Run", "Curtain", "Trailing"],
}


def mood_family(catalog, mood, color_code=None):
    """Best available family for a mood — the first preferred family that exists
    AND can render the requested colour (so the light matches the music)."""
    prefs = MOOD_FAMILIES.get(mood, [])
    if color_code:
        for f in prefs:
            if f in catalog and color_code in catalog[f]:
                return f
    for f in prefs:
        if f in catalog:
            return f
    return next((f for f in catalog if f != "Auto"), None)


def label_color(label):
    """Map a catalog variant label to a display colour code, or None when the
    variant has no single colour (e.g. a family-name label)."""
    if label in COLOR_HEX:
        return label
    if label and label.strip().lower() == "white":
        return "WH"
    return None


def resolve_mode(catalog, fam, color_code, forward=True, use_direction=True):
    """Return (mode_number, variant_label) for a colour in `fam`, honouring
    direction. `variant_label` is the colour ACTUALLY used (may differ from the
    request when the family lacks it) — so callers can report the true colour."""
    colors = catalog.get(fam, {})
    if color_code in colors:
        label = color_code
    elif "7 Colors" in colors:
        label = "7 Colors"
    else:
        label = next(iter(colors), None)
    entry = colors.get(label) if label is not None else None
    if not entry:
        return None, None
    fwd = forward or not use_direction
    if fam in FORCE_BACKWARD:
        fwd = False
    if "fwd" in entry or "bwd" in entry:
        num = (entry.get("fwd") if fwd else entry.get("bwd")) or entry.get("fwd") or entry.get("bwd")
    elif "open" in entry or "close" in entry:
        num = (entry.get("open") if fwd else entry.get("close")) or entry.get("open") or entry.get("close")
    else:
        num = entry.get("single")
    return num, label


def pick_mode(catalog, fam, color_code, forward=True, use_direction=True):
    """Mode number for a colour variant in `fam` (see resolve_mode)."""
    return resolve_mode(catalog, fam, color_code, forward, use_direction)[0]


def selectable_families(catalog):
    """All families offered for music (except Auto). `color_react` flags those with a
    full single-colour set, where the frequency->colour mapping fully applies; others
    fall back to their '7 Colors'/combo variants."""
    out = []
    for fam, colors in catalog.items():
        if fam == "Auto":
            continue
        single_count = sum(1 for c in SINGLE_COLORS if c in colors)
        out.append({"family": fam, "colors": [c for c in SINGLE_COLORS if c in colors],
                    "single": single_count, "color_react": single_count >= 4})
    out.sort(key=lambda x: -x["single"])
    return out
