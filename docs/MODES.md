# LEDDMX-03 effect modes — what each one actually does

Ground-truth notes from observing the physical strip, reconciled against the raw
`modes_dmx03.json` catalog (211 entries). This is the reference the engine's
family selection is built on — if the strip behaves differently from what's here,
fix this file first, then the code.

Direction: most effects have a **Forward** (lower mode number) and **Backward**
(higher number) variant. A few use **Open/Close** instead. The strip indexes
right→left, so "Backward" usually reads as right-to-left.

Colour notation below: `R G B Y C P/V W` = Red, Green, Blue, Yellow, Cyan,
Violet/Purple, White.

---

## Families, by real behaviour

### Dreaming family — `1–22`
A flowing band of colours travelling along the strip. The whole `1–22` block is
this one family; the variants change *which colours are present* and whether the
edges are **hard** or **blended**. In every variant **the colour named in the
label is the one OMITTED**, not the one shown:
- **`1–2` Dreaming** — full rainbow, **blended** (colours melt together, no edges).
- **`3–4` 7 Colors** — all seven colours, **hard boundaries**:
  `RRRRR GGGGG BBBBB YYYYY CCCCC PPPPP WWWWW`, crisp edges, travelling together.
- **`5–6` RD/GN/BU**, **`7–8` YE/CN/VT** — **hard boundaries** too, but with the
  named colours **omitted** (so the remaining colours form the bands).
- **`9–22` 6 Colors RD…WH** — one colour dropped (the suffix names the **omitted**
  colour), and these are **blended** / well-merged like `1–2`, *no* hard edges.

So: `3–8` = hard-edged bands, `1–2` & `9–22` = smooth blends. Combo/gradient only
(no single-colour variants), so not used in the colour-reactive music auto-pool.

### Trailing — `23–38`
**Fading comet trails** of a single colour — a bright head with a tail that fades
out behind it. Smooth, calm, breathing. Full single-colour set (RD…WH).
→ **colour-reactive**

### Streaming — `39–56`
**Connected solid bands flowing** with no gaps between them, e.g.
Streaming RD/GN = `RRRRRRRGGGGGGGRRRRRRRGGGGGGG` scrolling. Combo colours only
(pairs/triples + BK/WH); no single-colour variants.

### Curtain — three distinct behaviours
- **`57–62` Curtain 7 Colors / RGB / YCV** — strip is **fully filled**; a new
  colour sweeps in from one side and **replaces** the previous fill, in order,
  by direction. ⚠️ **Identical to Follow Spot (63–68)** → one of them is dropped.
- **`153–168` Curtain "7 COLOR" + singles RD…WH** — multiple colours **following
  each other but separated**: `R  G  B  Y  C  P  W  R …`. This block carries the
  full single-colour set. → **colour-reactive**
- **`169–174` Curtain … ON YE/CN/VT** — the 7 colours running **on a coloured
  background** ("ON YE" = on yellow).

### Follow Spot — `63–68`
**Same effect as the first Curtain block** (fill + replace by direction).
→ **redundant, dropped.**

### Flutter — `69–76`
A **short repeating pattern moving** as a unit, e.g. Flutter RGB = `RGBRGBRGB…`
sliding left or right by direction. Combo colours only.

### Hop — `77–80`
The **whole strip is one solid colour at a time** and **jumps** between colours
(full R → full G → full B …) around its palette. **Speed controls the jump rate.**
Palettes: 7 Colors (77) / RGB (78) / YCV (79) — and **White (80)**, i.e. the device
"Strobe White", which is just a Hop between **white and dark**. The engine treats
these as one family: pick the palette that matches the moment's colours, use White
when it's broadband/colourless.

### Strobe White — `80`
Whole strip **white ↔ dark** flashing — the **white member of the Hop family**.
(The music engine's coloured "peak strobe" is the software equivalent done in the
strip's *colour* channel, so it can flash in the music's colour rather than white.)

### Horse Race — `81–94`
**Accumulating fill**: a piece travels down the strip and **collects at the far
end**; the next piece comes and **stops behind** the previous one; when the strip
is full the colour changes and it repeats. ⚠️ **Only the Backward variant works**
(`82` etc., right→left). The Forward variant (`81`) does *not* hold the piece — it
slides back. → **engine forces Backward for this family.** Partial colour set
(YE/CN/VT/WH singles + combos).

### Run — `95–122`
**Single-colour block chasing** across the strip (the classic runner). Full
single-colour set (RD…WH) plus pairs. The workhorse colour effect.
→ **colour-reactive**

### Flow — `123–136`, `175–182`
**Chunks of colours moving together with gaps/spaces** between them, e.g.
Flow RD/GN/RD = `GRRG  GRRG`; Flow RGBY = `RGBY  RGBY` with spaces. Combo colours.

### Run … ON … — `137–152`
Run, but the runner travels **on a coloured background** (e.g. "Run RD ON WH" =
red runner over a white strip).

### Swab — `183–202`
**Identical to Run.** → **redundant, dropped.** (Its 197–202 entries are even
mislabeled — all say "Forward".)

### Curtain Swab — `203–210`
Open/Close curtain combined with a swab wipe. Kept (distinct combo, niche).

### AUTO — `255`
The strip's own built-in auto programme. Not used by the engine.

---

## Curation: what the engine uses

**Removed from the catalog entirely** (so they no longer appear in the Effects
dropdown or get auto-selected):
- **Swab** — duplicate of Run.
- **Follow Spot** — duplicate of the first Curtain block.

**Special handling**
- **Horse Race** → always sent as the **Backward** variant (Forward is broken).

**Music auto-pool (Smart mode)** — when a single colour dominates, only
**colour-reactive** families (which own the full single-colour set) are used, so
the light honours the frequency→colour mapping. Three distinct looks:

| Family | Look | Mood lean |
|---|---|---|
| **Trailing** | fading comet | calm / sustained |
| **Curtain** | colour sweep / fill | groove / build |
| **Run** | colour chase | drive / peak |

**Peaks → coloured strobe (software).** A peak (mood 3) becomes a **software colour
strobe**: the player flashes the **live music colour and dark**, alternating every
tick — a true strobe with an off-phase between flashes (the on-device Hop can't go
dark between colours, which is why we don't use it here). Each flash is sent
*critical* so the on-frame can't be dropped, and **no speed commands** go out during
a strobe, keeping us well under the strip's command rate. Everything that isn't a
peak uses the colour-reactive pool above (Run / Curtain / Trailing). Combo-only
families (Streaming, Flow, Flutter, Hop) stay manual-only.

frequency → colour (bass→treble): `RD VT BU GN YE WH`.
