"""Precompute the full-song MODE PLAN from a timeline + the current config.

The plan is a list of time segments — each either an on-device effect-mode segment
(family + mode + colour) or a coloured-strobe segment (peaks). A strobe flashes the
live music colour and dark in software; everything else is a single mode the strip
animates itself. The player FOLLOWS this plan, so what the UI draws is exactly what
gets sent, and seeking is a jump to the covering segment.
"""
from backend import modes as M


def plan_key(timeline, cfg, active_families):
    """A hashable signature — rebuild the plan only when one of these changes."""
    return (id(timeline), bool(cfg.get("auto_family")), bool(cfg.get("peak_strobe", True)),
            int(cfg.get("beats_per_switch", 4)), bool(cfg.get("use_direction", True)),
            bool(cfg.get("switch_modes", True)), tuple(active_families))


def build_plan(catalog, timeline, cfg, active_families):
    """Build the full-song mode plan (segments + direction markers) from a timeline."""
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

    # switch boundaries match the live director: at beats[bps-1], beats[2*bps-1], …
    switch_times = [beats[k] for k in range(bps - 1, len(beats), bps)] if beats else []
    boundaries = [0.0] + switch_times + [dur]

    segments, fam_idx = [], -1
    for i in range(len(boundaries) - 1):
        t0, t1 = boundaries[i], boundaries[i + 1]
        if t1 - t0 < 1e-3:
            continue
        frame_idx = frame(t0)
        music_color = M.FREQ_COLORS[colors[frame_idx]]
        mood = int(moods[frame_idx]) if frame_idx < len(moods) else 0
        fwd = bool(dirs[frame_idx]) if frame_idx < len(dirs) else True
        segment = {"t0": round(t0, 2), "t1": round(t1, 2), "mood": mood, "color": music_color}

        if auto and strobe_on and mood == 3:
            segments.append({**segment, "kind": "strobe", "family": "Colour Strobe", "mode": None})
            continue
        if auto:
            # rotate the mood's families so each gets airtime, not all on Run
            prefs = [f for f in M.MOOD_FAMILIES.get(mood, []) if f in catalog] \
                or [f for f in [M.mood_family(catalog, mood, music_color)] if f]
            if not prefs:
                continue
            fam_idx = (fam_idx + 1) % len(prefs)
            fam = prefs[fam_idx]
        else:
            if not fams:
                continue
            fam_idx = (fam_idx + 1) % len(fams)
            fam = fams[fam_idx]
        if not fam:
            continue
        num, label = M.resolve_mode(catalog, fam, music_color, fwd, use_dir)
        if not num:
            continue
        segments.append({**segment, "kind": "mode", "family": fam, "mode": num,
                         "color": M.label_color(label) or music_color, "fwd": bool(fwd or not use_dir)})

    # direction markers — where committed direction flips (mode segments only)
    dir_marks, last_fwd = [], None
    for s in segments:
        if s["kind"] != "mode":
            continue
        if last_fwd is not None and s["fwd"] != last_fwd:
            dir_marks.append({"t": s["t0"], "fwd": s["fwd"]})
        last_fwd = s["fwd"]

    # y-axis order: catalog families that appear, Colour Strobe lane last
    fam_order = [f for f in catalog if any(s["family"] == f for s in segments)]
    if any(s["family"] == "Colour Strobe" for s in segments):
        fam_order.append("Colour Strobe")
    return {"duration": dur, "bpm": timeline.get("bpm", 0),
            "segments": segments, "families": fam_order, "dir_marks": dir_marks}
