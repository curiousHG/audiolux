"""Precompute the full-song MODE PLAN from a timeline + the current config.

The plan is a list of time segments — each either an effect-mode segment
(family + mode + colour) or a coloured-strobe segment (peaks). The player FOLLOWS
this plan, so what the UI draws is exactly what gets sent, and seeking is just a
jump to whichever segment covers the new time.
"""
from backend import modes as M


def plan_key(timeline, cfg, active_families):
    """A hashable signature — rebuild the plan only when one of these changes."""
    return (id(timeline), bool(cfg.get("auto_family")), bool(cfg.get("peak_strobe", True)),
            int(cfg.get("beats_per_switch", 4)), bool(cfg.get("use_direction", True)),
            bool(cfg.get("switch_modes", True)), tuple(active_families))


def build_plan(catalog, timeline, cfg, active_families):
    colors = timeline["color"]
    moods = timeline.get("mood") or [0] * len(colors)
    dirs = timeline.get("dir") or [1] * len(colors)
    beats = timeline.get("beats") or []
    dt, dur, n = timeline["dt"], timeline["duration"], len(colors)
    bps = max(1, int(cfg.get("beats_per_switch", 4)))
    auto = bool(cfg.get("auto_family"))
    strobe_on = bool(cfg.get("peak_strobe", True))
    use_dir = bool(cfg.get("use_direction", True))
    fams = [f for f in active_families if f in catalog]

    def frame(t):
        return min(max(int(t / dt), 0), n - 1)

    # switch boundaries: the live director switches when the beat count crosses a
    # multiple of bps, i.e. at beats[bps-1], beats[2*bps-1], …
    sw = [beats[k] for k in range(bps - 1, len(beats), bps)] if beats else []
    boundaries = [0.0] + sw + [dur]

    segments, fam_idx = [], -1
    for i in range(len(boundaries) - 1):
        t0, t1 = boundaries[i], boundaries[i + 1]
        if t1 - t0 < 1e-3:
            continue
        fi = frame(t0)
        mc = M.FREQ_COLORS[colors[fi]]
        mood = int(moods[fi]) if fi < len(moods) else 0
        fwd = bool(dirs[fi]) if fi < len(dirs) else True
        seg = {"t0": round(t0, 2), "t1": round(t1, 2), "mood": mood, "color": mc}

        if auto and strobe_on and mood == 3:
            segments.append({**seg, "kind": "strobe", "family": "Colour Strobe", "mode": None})
            continue
        if auto:
            fam = M.mood_family(catalog, mood, mc)
        else:
            if not fams:
                continue
            fam_idx = (fam_idx + 1) % len(fams)
            fam = fams[fam_idx]
        if not fam:
            continue
        num, label = M.resolve_mode(catalog, fam, mc, fwd, use_dir)
        if not num:
            continue
        segments.append({**seg, "kind": "mode", "family": fam, "mode": num,
                         "color": M.label_color(label) or mc})

    # y-axis order: catalog families that appear, then the Colour Strobe lane last
    fam_order = [f for f in catalog if any(s["family"] == f for s in segments)]
    if any(s["family"] == "Colour Strobe" for s in segments):
        fam_order.append("Colour Strobe")
    return {"duration": dur, "bpm": timeline.get("bpm", 0),
            "segments": segments, "families": fam_order}
