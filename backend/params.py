"""Runtime-tunable algorithm parameters, surfaced to the UI (sliders + the
"how it works" explainer).

Each param is a `Param` record carrying its own UI metadata, so the frontend can
render it generically — add one here and a slider appears automatically.
`reanalyse=True` params change the OFFLINE analysis, so editing one re-runs analysis
on the loaded track; runtime params take effect on the next tick.
"""
from dataclasses import asdict, dataclass


@dataclass
class Param:
    """One tunable algorithm parameter plus the metadata the UI renders it with."""
    value: float
    min: float
    max: float
    step: float
    reanalyse: bool          # True -> editing re-runs the offline analysis
    group: str
    label: str
    desc: str


PARAMS: dict[str, Param] = {
    "db_floor": Param(-45.0, -70, -25, 1, True, "Loudness → Brightness", "dB floor",
                      "RMS this many dB below the track's loud (95th-pct) level maps to 0% brightness"),

    "spec_gamma": Param(0.85, 0.4, 1.4, 0.05, True, "Spectrum → Colour", "spectrum gamma",
                        "display curve for the whitened spectrum (lower = punchier highs)"),
    "white_deemph": Param(0.78, 0.4, 1.0, 0.02, True, "Spectrum → Colour", "white de-emphasis",
                          "down-weight the top (white) band so cymbals/air don't force white"),
    "colour_silence": Param(0.06, 0.0, 0.3, 0.01, True, "Spectrum → Colour", "silence hold",
                            "below this brightness the colour holds its last value"),

    "mood_peak_e": Param(0.75, 0.4, 1.0, 0.02, True, "Energy → Mood", "peak loudness",
                         "loudness above this AND percussive ⇒ peak (coloured strobe)"),
    "mood_peak_p": Param(0.45, 0.1, 0.9, 0.02, True, "Energy → Mood", "peak percussiveness",
                         "HPSS percussive fraction required for a peak"),
    "mood_drive_e": Param(0.52, 0.2, 0.9, 0.02, True, "Energy → Mood", "drive loudness",
                          "loudness above this ⇒ drive"),
    "mood_groove_e": Param(0.28, 0.1, 0.7, 0.02, True, "Energy → Mood", "groove loudness",
                           "loudness above this ⇒ groove (else calm)"),

    "dir_build": Param(1.05, 1.0, 1.3, 0.01, True, "Build/Release → Direction", "build ratio",
                       "brightness above its slow average × this ⇒ forward"),
    "dir_release": Param(0.95, 0.7, 1.0, 0.01, True, "Build/Release → Direction", "release ratio",
                         "brightness below its slow average × this ⇒ backward"),

    "speed_bpm_lo": Param(60.0, 40, 120, 1, False, "Tempo → Speed", "min-speed BPM",
                          "trailing BPM at/below this sits at the bottom of the speed range"),
    "speed_span": Param(120.0, 40, 180, 5, False, "Tempo → Speed", "BPM span",
                        "BPM range above min mapped up across the speed range"),
}


def get(name: str) -> float:
    """Return the current value of a param by name."""
    return PARAMS[name].value


def set_value(name: str, v) -> bool:
    """Set a param's value (coerced to float); returns False for unknown names."""
    if name in PARAMS:
        PARAMS[name].value = float(v)
        return True
    return False


def as_dict() -> dict:
    """Serialise every param (value + metadata) to plain dicts for the JSON API."""
    return {name: asdict(param) for name, param in PARAMS.items()}
