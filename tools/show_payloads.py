"""Print (without sending) the byte payloads for colors, power, and modes."""

def color_frame(r, g, b):
    # 7B FF 07 <G> <R> <B> 00 FF BF   (controller is GRB order)
    return bytes([0x7B, 0xFF, 0x07, g, r, b, 0x00, 0xFF, 0xBF])

def power_frame(on):
    return bytes([0x7B, 0xFF, 0x04, 0x01 if on else 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xBF])

def mode_frame(mode, speed=0x20, bright=0xFF):
    return bytes([0x7B, 0xFF, 0x03, mode, speed, bright, 0x00, 0xFF, 0xBF])

COLORS = {
    "RED":     (255, 0, 0),
    "GREEN":   (0, 255, 0),
    "BLUE":    (0, 0, 255),
    "WHITE":   (255, 255, 255),
    "YELLOW":  (255, 255, 0),
    "CYAN":    (0, 255, 255),
    "MAGENTA": (255, 0, 255),
    "ORANGE":  (255, 90, 0),
    "DIM RED (25%)":  (64, 0, 0),
    "HALF RED (50%)": (128, 0, 0),
}

print("COLOR (cmd 0x07)      RGB              ->  payload            [7B FF 07 G R B 00 FF BF]")
print("-" * 92)
for name, (r, g, b) in COLORS.items():
    f = color_frame(r, g, b)
    print(f"{name:<20} ({r:3},{g:3},{b:3})   ->  {f.hex()}   G={g:02x} R={r:02x} B={b:02x}")

print("\nPOWER (cmd 0x04)")
print(f"  ON   -> {power_frame(True).hex()}")
print(f"  OFF  -> {power_frame(False).hex()}")

print("\nMODE/EFFECT (cmd 0x03)  [7B FF 03 <mode> <speed> <bright> 00 FF BF]")
for m in (1, 2, 3, 4):
    print(f"  mode {m} -> {mode_frame(m).hex()}")
