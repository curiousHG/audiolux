"""The precomputed mode plan the timeline view draws and the player follows."""
from backend import modes as M
from backend import planner
from conftest import make_timeline


def cfg(**kw):
    base = {"auto_family": True, "peak_strobe": True, "beats_per_switch": 4,
            "use_direction": True, "switch_modes": True}
    base.update(kw)
    return base


def test_segments_are_contiguous_and_cover_song(catalog):
    tl = make_timeline(moods=2, colors=M.FREQ_COLORS.index("RD"), n=200)  # 20s
    plan = planner.build_plan(catalog, tl, cfg(), ["Run"])
    segs = plan["segments"]
    assert segs[0]["t0"] == 0.0
    assert abs(segs[-1]["t1"] - tl["duration"]) < 0.5
    for a, b in zip(segs, segs[1:]):
        assert b["t0"] == a["t1"], "segments must be contiguous"


def test_peak_makes_colored_strobe_segments(catalog):
    tl = make_timeline(moods=3, colors=M.FREQ_COLORS.index("RD"), n=160)
    plan = planner.build_plan(catalog, tl, cfg(), ["Run"])
    kinds = {s["kind"] for s in plan["segments"]}
    assert kinds == {"strobe"}
    assert "Colour Strobe" in plan["families"]
    # strobe disabled -> falls back to colour-capable mode segments, no white Strobe
    plan2 = planner.build_plan(catalog, tl, cfg(peak_strobe=False), ["Run"])
    assert all(s["kind"] == "mode" for s in plan2["segments"])
    assert "Strobe" not in plan2["families"]


def test_mode_segments_match_color(catalog, num2name):
    tl = make_timeline(moods=2, colors=M.FREQ_COLORS.index("GN"), n=160)
    plan = planner.build_plan(catalog, tl, cfg(), ["Run"])
    for s in plan["segments"]:
        if s["kind"] == "mode":
            assert s["color"] == "GN"
            assert "GN" in num2name[s["mode"]]


def test_beats_per_switch_changes_segment_count(catalog):
    tl = make_timeline(moods=2, colors=0, n=240)
    few = planner.build_plan(catalog, tl, cfg(beats_per_switch=8), ["Run"])
    many = planner.build_plan(catalog, tl, cfg(beats_per_switch=2), ["Run"])
    assert len(many["segments"]) > len(few["segments"])


def test_plan_key_changes_with_config(catalog):
    tl = make_timeline(moods=2, colors=0, n=80)
    k1 = planner.plan_key(tl, cfg(), ["Run"])
    k2 = planner.plan_key(tl, cfg(beats_per_switch=8), ["Run"])
    k3 = planner.plan_key(tl, cfg(), ["Trailing"])
    assert k1 != k2 and k1 != k3
