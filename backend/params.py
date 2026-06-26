"""Runtime-tunable algorithm parameters, surfaced to the UI (sliders + the
"how it works" explainer).

Each param carries its own UI metadata so the frontend can render it generically
— add a param here and a slider appears automatically. `reanalyse=True` params
change the OFFLINE analysis, so editing one re-runs analysis on the loaded track;
runtime params take effect on the next tick.
"""

PARAMS = {
    # loudness -> brightness
    "db_floor": {"value": -45.0, "min": -70, "max": -25, "step": 1, "reanalyse": True,
                 "group": "Loudness → Brightness", "label": "dB floor",
                 "desc": "RMS this many dB below the track's loud (95th-pct) level maps to 0% brightness"},

    # spectrum -> colour
    "spec_gamma": {"value": 0.85, "min": 0.4, "max": 1.4, "step": 0.05, "reanalyse": True,
                   "group": "Spectrum → Colour", "label": "spectrum gamma",
                   "desc": "display curve for the whitened spectrum (lower = punchier highs)"},
    "white_deemph": {"value": 0.78, "min": 0.4, "max": 1.0, "step": 0.02, "reanalyse": True,
                     "group": "Spectrum → Colour", "label": "white de-emphasis",
                     "desc": "down-weight the top (white) band so cymbals/air don't force white"},
    "colour_silence": {"value": 0.06, "min": 0.0, "max": 0.3, "step": 0.01, "reanalyse": True,
                       "group": "Spectrum → Colour", "label": "silence hold",
                       "desc": "below this brightness the colour holds its last value"},

    # energy + percussiveness -> mood
    "mood_peak_e": {"value": 0.75, "min": 0.4, "max": 1.0, "step": 0.02, "reanalyse": True,
                    "group": "Energy → Mood", "label": "peak loudness",
                    "desc": "loudness above this AND percussive ⇒ peak (coloured strobe)"},
    "mood_peak_p": {"value": 0.45, "min": 0.1, "max": 0.9, "step": 0.02, "reanalyse": True,
                    "group": "Energy → Mood", "label": "peak percussiveness",
                    "desc": "HPSS percussive fraction required for a peak"},
    "mood_drive_e": {"value": 0.52, "min": 0.2, "max": 0.9, "step": 0.02, "reanalyse": True,
                     "group": "Energy → Mood", "label": "drive loudness",
                     "desc": "loudness above this ⇒ drive"},
    "mood_groove_e": {"value": 0.28, "min": 0.1, "max": 0.7, "step": 0.02, "reanalyse": True,
                      "group": "Energy → Mood", "label": "groove loudness",
                      "desc": "loudness above this ⇒ groove (else calm)"},

    # build/release -> direction
    "dir_build": {"value": 1.05, "min": 1.0, "max": 1.3, "step": 0.01, "reanalyse": True,
                  "group": "Build/Release → Direction", "label": "build ratio",
                  "desc": "brightness above its slow average × this ⇒ forward"},
    "dir_release": {"value": 0.95, "min": 0.7, "max": 1.0, "step": 0.01, "reanalyse": True,
                    "group": "Build/Release → Direction", "label": "release ratio",
                    "desc": "brightness below its slow average × this ⇒ backward"},

    # tempo -> speed (runtime, no re-analysis)
    "speed_bpm_lo": {"value": 70.0, "min": 40, "max": 120, "step": 1, "reanalyse": False,
                     "group": "Tempo → Speed", "label": "min-speed BPM",
                     "desc": "BPM mapped to the lowest animation speed"},
    "speed_span": {"value": 90.0, "min": 30, "max": 160, "step": 5, "reanalyse": False,
                   "group": "Tempo → Speed", "label": "BPM span",
                   "desc": "BPM range above min mapped up to full speed"},
}


def get(name):
    return PARAMS[name]["value"]


def set_value(name, v) -> bool:
    if name in PARAMS:
        PARAMS[name]["value"] = float(v)
        return True
    return False
