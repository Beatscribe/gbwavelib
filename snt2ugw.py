import html
import struct
import sys
from pathlib import Path


def u32(v):
    return struct.pack("<I", v)


def u8(v):
    return struct.pack("<B", v)


def ss(s):
    b = s.encode("latin1")
    return bytes([len(b)]) + b + bytes(255 - len(b))


def rows_block(rows):
    out = bytearray()
    for note, jump, eff, param in rows:
        out += u32(note)
        out += u32(0)
        out += u32(jump)
        out += u32(eff)
        out += u8(param)
    return bytes(out)


EMPTY_ROWS = [(90, 0, 0, 0)] * 64

DUTY_NAMES = [
    "Duty 12.5%", "Duty 25%", "Duty 50%", "Duty 75%",
    "Duty 12.5% plink", "Duty 25% plink", "Duty 50% plink", "Duty 75% plink",
    "", "", "", "", "", "", "",
]

WAVE_NAMES = [
    "cycle!", "Square wave 25%", "Square wave 50%", "Square wave 75%",
    "Sawtooth wave", "Triangle wave", "Sine wave", "Toothy",
    "Triangle Toothy", "Pointy", "Strange", "", "", "", "",
]


def duty_instr(name, duty, sweep_chg=0):
    return (
        u32(0) + ss(name)
        + u32(0) + u8(0)
        + u8(15) + u32(1) + u8(sweep_chg) + u32(0) + u32(1) + u32(0)
        + u8(duty) + u32(1) + u32(0) + u32(0)
        + u8(0) + rows_block(EMPTY_ROWS)
    )


def wave_instr(name, wave_index, sub_en=0, rows=None):
    if rows is None:
        rows = EMPTY_ROWS
    return (
        u32(1) + ss(name)
        + u32(0) + u8(0)
        + u8(0) + u32(0) + u8(0) + u32(0) + u32(0) + u32(0)
        + u8(0) + u32(1) + u32(wave_index) + u32(0)
        + u8(sub_en) + rows_block(rows)
    )


def noise_instr():
    return (
        u32(2) + ss("")
        + u32(0) + u8(0)
        + u8(15) + u32(1) + u8(0) + u32(0) + u32(0) + u32(0)
        + u8(0) + u32(0) + u32(0) + u32(0)
        + u8(0) + rows_block(EMPTY_ROWS)
    )


def cycle_rows(waves):
    rows = list(EMPTY_ROWS)
    row = 1
    for w in range(1, 16):
        if all(n == 0 for n in waves[w]):
            continue
        param = w if w <= 9 else w + 6
        rows[row] = (90, 0, 9, param)
        row += 1
    rows[24] = (90, 22, 0, 0)
    return rows


def build_uge(waves):
    out = bytearray()
    out += u32(6)
    out += ss("")
    out += ss("")
    out += ss("")

    for i, name in enumerate(DUTY_NAMES):
        if i < 4:
            duty = i
        elif i < 8:
            duty = i - 4
        else:
            duty = 2
        out += duty_instr(name, duty, sweep_chg=1 if 4 <= i < 8 else 0)

    out += wave_instr("cycle!", 0, sub_en=1, rows=cycle_rows(waves))
    for i, name in enumerate(WAVE_NAMES[1:]):
        out += wave_instr(name, i + 1)

    for _ in range(15):
        out += noise_instr()

    for wave in waves:
        for nibble in wave:
            out += u8(nibble)

    out += u32(7)
    out += u8(0)
    out += u32(0)
    out += u32(4)
    for p in range(4):
        out += u32(p)
        for r in range(64):
            out += u32(90)
            out += u32(0)
            out += u32(0)
            out += u32(0)
            out += u8(0)

    for ch in range(4):
        out += u32(2)
        out += u32(ch)
        out += u32(0)

    for _ in range(16):
        out += u32(0)

    return bytes(out)


def nibbles(data):
    return [n for b in data for n in (b >> 4, b & 0x0F)]


def convert(filename):
    path = Path(filename)
    data = path.read_bytes()
    if len(data) % 16 != 0:
        raise ValueError(f"{filename}: file length {len(data)} is not a multiple of 16 bytes")
    stem = path.stem
    num_rows = len(data) // 16
    out_dir = None
    if num_rows > 1:
        out_dir = path.with_name(stem)
        out_dir.mkdir(exist_ok=True)
    waves = []
    for i in range(0, len(data), 16):
        row = data[i:i + 16]
        out = bytearray()
        for b in row:
            out.append(b >> 4)
            out.append(b & 0x0F)
        name = f"{stem}-{i // 16 + 1}.ugw"
        if out_dir is not None:
            out_path = out_dir / name
        else:
            out_path = path.with_name(name)
        out_path.write_bytes(out)
        waves.append(nibbles(row))
    if out_dir is not None:
        (out_dir / f"{stem}.uge").write_bytes(build_uge(waves))
    update_html(path.parent)

def update_html(directory):
    directory = Path(directory)
    parts = []
    for f in sorted(directory.glob("*.snt")):
        data = f.read_bytes()
        waves = []
        for i in range(0, len(data), 16):
            row = data[i:i + 16]
            waves.append("".join(f"{b >> 4:x}{b & 0x0f:x}" for b in row))
        parts.append(f"<details><summary>{html.escape(f.name)}</summary>\n<p>{'<br>'.join(waves)}</p>\n</details>")
    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>wavelib</title>
<style>
body {{ font-family: monospace; margin: 1rem; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: .2rem; }}
details {{ margin-bottom: .5rem; border: 1px solid #ccc; border-radius: 4px; padding: .4rem; }}
summary {{ cursor: pointer; font-weight: bold; }}
p {{ margin: .4rem 0 0; word-break: break-all; }}
</style>
</head>
<body>
<h1>LSDJ Cycle Patches</h1>
{chr(10).join(parts)}
</body>
</html>
"""
    (directory / "wavelib.html").write_text(out)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <file>")
        sys.exit(1)
    for arg in sys.argv[1:]:
        convert(arg)
