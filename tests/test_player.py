"""PlayerEngine behaviour: actual-colour reporting, coloured peak strobe, loading."""
from backend import modes as M
from backend import music, player
from conftest import FakeController, make_timeline, cmd_code, run

WHITE_STROBE_MODE = 80   # 'Strobe White'


def build(catalog, **cfg):
    fc = FakeController()
    eng = music.MusicEngine(fc, catalog)
    eng.cfg.update(cfg)
    pl = player.PlayerEngine(fc, eng)
    return fc, pl


def drive_ticks(pl, seconds=4.0, step=0.12):
    async def go():
        t = 0.0
        while t < seconds:
            await pl.tick(round(t, 2), True)
            t += step
    run(go())


def test_drive_uses_color_capable_family_and_matches_color(catalog, num2name):
    # RD music in 'drive' mood -> should pick a colour-capable family at RD
    fc, pl = build(catalog, auto_family=True, peak_strobe=True, beats_per_switch=4)
    pl.load({"id": "x", "duration": 8}, make_timeline(moods=2, colors=M.FREQ_COLORS.index("RD")))
    drive_ticks(pl)
    modes_sent = fc.cmds(0x03)
    assert modes_sent, "expected at least one effect-mode command"
    names = [num2name[p[3]] for p in modes_sent]
    assert all("RD" in n for n in names), f"all modes should be red: {names}"
    assert pl.cur_family in ("Run", "Trailing", "Curtain", "Swab")
    assert pl.color_code == "RD"            # reported colour matches the light


def test_peak_emits_colored_strobe_not_white_mode(catalog):
    # RD music in 'peak' mood -> coloured solid-colour strobe, never the white Strobe mode
    fc, pl = build(catalog, auto_family=True, peak_strobe=True)
    pl.load({"id": "x", "duration": 8}, make_timeline(moods=3, colors=M.FREQ_COLORS.index("RD")))
    drive_ticks(pl)
    colors = fc.cmds(0x07)
    assert colors, "peak should emit solid-colour (strobe) commands"
    # the 'on' flashes are red (255,48,48); 'off' flashes are black
    lit = [(p[3], p[4], p[5]) for p in colors if (p[3], p[4], p[5]) != (0, 0, 0)]
    assert lit, "strobe should have lit (non-black) frames"
    assert all(r > g and r > b for r, g, b in lit), f"strobe should be red: {lit}"
    assert WHITE_STROBE_MODE not in [p[3] for p in fc.cmds(0x03)]


def test_peak_strobe_can_be_disabled(catalog):
    fc, pl = build(catalog, auto_family=True, peak_strobe=False)
    pl.load({"id": "x", "duration": 8}, make_timeline(moods=3, colors=M.FREQ_COLORS.index("BU")))
    drive_ticks(pl)
    # with strobe off, peaks fall back to a colour-capable effect mode (no solid-colour spam)
    assert fc.cmds(0x03), "should still drive an effect mode when strobe is off"


def test_state_reports_actual_and_music_color(catalog):
    fc, pl = build(catalog, auto_family=True, peak_strobe=True, beats_per_switch=4)
    pl.load({"id": "x", "duration": 8}, make_timeline(moods=2, colors=M.FREQ_COLORS.index("GN")))
    drive_ticks(pl)
    st = pl.state()
    assert st["music_color"] == "GN"
    assert st["color"] == "GN"              # colour-capable family -> they agree


def test_loading_pulse_runs_and_stops(catalog):
    fc, pl = build(catalog)

    async def go():
        pl.start_loading()
        import asyncio
        await asyncio.sleep(0.35)           # let it emit a few frames
        sent_during = len(fc.sends)
        pl.stop_loading()
        await asyncio.sleep(0.05)
        return sent_during, len(fc.sends)

    during, after_stop = run(go())
    assert during > 0, "loading pulse should send commands"
    # power(0x04) on + colour/brightness pulses
    assert any(cmd_code(p) == 0x04 for p in fc.sends)
    assert any(cmd_code(p) in (0x01, 0x07) for p in fc.sends)


def test_seek_does_not_burst_switches(catalog):
    fc, pl = build(catalog, auto_family=True, beats_per_switch=4)
    pl.load({"id": "x", "duration": 30}, make_timeline(moods=2, colors=0, n=300))

    async def go():
        await pl.tick(1.0, True)
        await pl.tick(20.0, True)           # big jump = scrub
    run(go())
    # after a scrub we shouldn't have fired a huge burst of mode changes
    assert len(fc.cmds(0x03)) <= 2
