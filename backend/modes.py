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

# Families that look good reacting to music (dynamic, moving effects).
DYNAMIC_FAMILIES = {"Run", "Flow", "Trailing", "Streaming", "Dreaming", "Horse Race", "Hop"}


def load_modes(path: str = _MODES_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify(modes):
    """Group modes by family, pairing each effect's two variants by mode NUMBER
    (lower = forward/open, higher = backward/close). We pair by number rather than
    the text label because the app's data mislabels some 'Backward' entries as
    'Forward' (e.g. 197 & 198 both say 'Forward Swab CN')."""
    order, acc = [], {}
    for m in modes:
        n, name = m["n"], m["name"]
        if name.strip().upper() == "AUTO":
            fam, base, oc = "Auto", "AUTO", False
        else:
            base, oc = name, False
            for p in ("Forward ", "Backward ", "Open ", "Close "):
                if name.startswith(p):
                    base, oc = name[len(p):], p in ("Open ", "Close ")
                    break
            fam = next((f for f in FAMILIES if f in base), "Basic")
        key = (fam, base)
        if key not in acc:
            acc[key] = {"fam": fam, "base": base, "nums": [], "oc": False}
            order.append(key)
        acc[key]["nums"].append(n)
        acc[key]["oc"] = acc[key]["oc"] or oc

    groups = collections.OrderedDict()
    for key in order:
        d = acc[key]
        nums = sorted(set(d["nums"]))
        eff = {"name": d["base"]}
        if len(nums) == 1:
            eff["single"] = nums[0]
        elif d["oc"]:
            eff["open"], eff["close"] = nums[0], nums[1]
        else:
            eff["fwd"], eff["bwd"] = nums[0], nums[1]
        groups.setdefault(d["fam"], []).append(eff)
    return [{"family": fam, "effects": effs} for fam, effs in groups.items()]


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


# Single colour codes used in effect names.
SINGLE_COLORS = ["RD", "YE", "GN", "CN", "BU", "VT", "WH"]
# Frequency -> colour (bass..treble). Following the standard lighting convention:
# low/bass = warm & deep (red, violet, blue), high/treble = bright & energetic
# (green, yellow, white).  bass/kick -> red, hi-hats/air -> white.
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


def pick_mode(catalog, fam, color_code, forward=True, use_direction=True):
    """Mode number for a colour variant in `fam`, honouring direction.
    Falls back to the family's '7 Colors'/first variant when the exact colour or a
    fwd/bwd half is missing. Shared by the mic engine and the track player."""
    colors = catalog.get(fam, {})
    entry = (colors.get(color_code) or colors.get("7 Colors")
             or (next(iter(colors.values())) if colors else None))
    if not entry:
        return None
    fwd = forward or not use_direction
    if "fwd" in entry or "bwd" in entry:
        return (entry.get("fwd") if fwd else entry.get("bwd")) or entry.get("fwd") or entry.get("bwd")
    if "open" in entry or "close" in entry:
        return (entry.get("open") if fwd else entry.get("close")) or entry.get("open") or entry.get("close")
    return entry.get("single")


def selectable_families(catalog):
    """All families offered for music (except Auto). `color_react` flags those with a
    full single-colour set, where the frequency->colour mapping fully applies; others
    fall back to their '7 Colors'/combo variants."""
    out = []
    for fam, colors in catalog.items():
        if fam == "Auto":
            continue
        n = sum(1 for c in SINGLE_COLORS if c in colors)
        out.append({"family": fam, "colors": [c for c in SINGLE_COLORS if c in colors],
                    "single": n, "color_react": n >= 4})
    out.sort(key=lambda x: -x["single"])
    return out
