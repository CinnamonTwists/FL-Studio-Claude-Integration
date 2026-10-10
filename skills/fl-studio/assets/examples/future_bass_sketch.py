"""Example song generator: an original future-bass sketch in E major / C# minor,
92 BPM, 48 bars (Intro / Verse / Build / Drop / Outro), written as a song spec
for scripts/write_song.py. Made in the spirit of a melodic-dubstep reference
(key, tempo, energy arc, 3-3-2 drop stabs) without copying its melody.

Channel layout it expects (Default template + 5 FLEX clones):
 0 Kick  1 Clap  2 HiHat  3 Snare  4 Sub (FLEX: Olbaid Bass Utopia / Deep Sense)
 5 Piano (Essential Pianos / Steinway D)  6 Supersaw (Black Octopus Pandora / Supersaw Nation)
 7 Pluck (Mobile Synth Pluck / Synpluck Glass)  8 Pad (Essential Strings / All Strings Slow)
 9 Growl (Olbaid Bass Utopia / Growling Machine)

usage: python future_bass_sketch.py --out song.json   then   python ../../scripts/write_song.py song.json
(Use --out, not shell redirection: Windows PowerShell 5.1 redirects as UTF-16.)
Patterns worth copying: voice-led chord dicts, prog() for bar/chord iteration,
step-grid rhythms in 16ths, velocity ramps for builds, a half-bar gap before the drop.
"""
import json
import sys

S = 1 / 16  # sixteenth note, in bars

# Chords (voice-led, G#3..A4) and bass roots (octave 1-2)
CH = {"C#m": [56, 61, 64, 68], "A": [57, 61, 64, 69], "E": [56, 59, 64, 68],
      "B": [54, 59, 63, 66], "G#m": [56, 59, 63, 68]}
ROOT = {"C#m": 37, "A": 33, "E": 40, "B": 35, "G#m": 32}
VERSE = ["C#m", "A", "E", "B"]      # vi IV I V
DROP = ["A", "B", "G#m", "C#m"]     # IV V iii vi

INTRO, VERSE_AT, BUILD, DROP_AT, OUTRO, END = 0, 8, 16, 24, 40, 48


def n(p, t, l, v=0.8):
    return {"pitch": int(p), "time_bars": round(t, 5), "length_bars": round(l, 5), "velocity": round(min(1, max(0.05, v)), 3)}


def prog(start, bars, loop):
    return [(start + i, loop[i % 4]) for i in range(bars)]


# ---- parts -------------------------------------------------------------------

def piano():
    out = []
    for b, c in prog(INTRO, 8, VERSE):                      # intro: half-note chords + low root
        for h in (0, 0.5):
            out += [n(p, b + h, 0.48, 0.55 if h else 0.68) for p in CH[c]]
        out.append(n(ROOT[c] + 12, b, 0.95, 0.6))
    for b, c in prog(VERSE_AT, 8, VERSE):                   # verse: 8th-note arpeggio
        tones = CH[c] + [CH[c][1] + 12]
        order = [0, 2, 1, 3, 4, 3, 2, 1]
        for i, k in enumerate(order):
            out.append(n(tones[k], b + i * 2 * S, 2 * S * 0.95, 0.5 + 0.1 * (i % 2 == 0)))
        out.append(n(ROOT[c] + 12, b, 0.95, 0.5))
    for b, c in prog(OUTRO, 8, DROP):                       # outro: whole-note chords, fading
        fade = 0.7 - 0.05 * (b - OUTRO)
        out += [n(p, b, 0.98, fade) for p in CH[c]]
        out.append(n(ROOT[c] + 12, b, 0.98, fade))
    out += [n(p, END - 1, 1.0, 0.45) for p in CH["C#m"]]     # final held C#m (overlaps last bar)
    return out


def pad():
    out = []
    for b, c in prog(INTRO, 16, VERSE):
        out += [n(p + 12, b, 1.0, 0.45) for p in CH[c][1:]]
    for b, c in prog(BUILD, 8, DROP):                       # swell through the build
        out += [n(p + 12, b, 1.0, 0.45 + 0.05 * (b - BUILD)) for p in CH[c][1:]]
    for b, c in prog(DROP_AT, 16, DROP):
        out += [n(p + 12, b, 1.0, 0.35) for p in CH[c][1:]]
    for b, c in prog(OUTRO, 8, DROP):
        out += [n(p + 12, b, 1.0, 0.5 - 0.04 * (b - OUTRO)) for p in CH[c][1:]]
    return out


def supersaw():
    out = []
    for b, c in prog(BUILD, 8, DROP):                       # build: sustained, rising
        if b == BUILD + 7:
            out += [n(p + 12, b, 0.5, 0.95) for p in CH[c]]   # cut at half-bar for the gap
        else:
            out += [n(p + 12, b, 1.0, 0.5 + 0.06 * (b - BUILD)) for p in CH[c]]
    stabs = [(0, 3, 1.0), (3, 3, 0.75), (6, 2, 0.95), (9, 2, 0.7), (12, 3, 1.0)]  # 3-3-2 bounce
    for b, c in prog(DROP_AT, 16, DROP):
        for step, ln, v in stabs:
            out += [n(p + 12, b + step * S, ln * S * 0.9, v) for p in CH[c]]
    return out


VERSE_MEL = [  # (bar, step, len_steps, pitch)
    (0, 0, 2, 68), (0, 4, 2, 73), (0, 8, 4, 76), (0, 12, 2, 75), (0, 14, 2, 73),
    (1, 0, 4, 73), (1, 6, 2, 71), (1, 8, 4, 69), (1, 12, 4, 64),
    (2, 0, 2, 68), (2, 2, 2, 71), (2, 4, 6, 76), (2, 10, 2, 75), (2, 12, 4, 71),
    (3, 0, 6, 75), (3, 6, 2, 73), (3, 8, 8, 71)]
DROP_MEL = [
    (0, 0, 3, 73), (0, 3, 3, 71), (0, 6, 2, 73), (0, 8, 4, 76), (0, 12, 2, 73), (0, 14, 2, 71),
    (1, 0, 3, 75), (1, 3, 3, 73), (1, 6, 2, 71), (1, 8, 6, 71), (1, 14, 2, 69),
    (2, 0, 3, 71), (2, 3, 3, 68), (2, 6, 2, 71), (2, 8, 4, 75), (2, 12, 2, 76), (2, 14, 2, 75),
    (3, 0, 8, 73), (3, 8, 2, 68), (3, 10, 2, 71), (3, 12, 4, 73)]
DROP_MEL_B_END = [(3, 0, 6, 73), (3, 6, 2, 75), (3, 8, 4, 76), (3, 12, 4, 80)]  # lift into repeat


def pluck():
    out = []
    for rep in range(2):
        for bar, st, ln, p in VERSE_MEL:
            out.append(n(p, VERSE_AT + rep * 4 + bar + st * S, ln * S * 0.95, 0.6 + 0.05 * rep))
    for rep in range(4):
        mel = DROP_MEL if rep % 2 == 0 else [m for m in DROP_MEL if m[0] < 3] + DROP_MEL_B_END
        for bar, st, ln, p in mel:
            out.append(n(p + 12 * (rep >= 2), DROP_AT + rep * 4 + bar + st * S, ln * S * 0.95,
                         0.85 if st in (0, 8) else 0.7))
    for rep in range(2):                                     # outro: verse line, softer
        for bar, st, ln, p in VERSE_MEL:
            out.append(n(p, OUTRO + rep * 4 + bar + st * S, ln * S * 0.95, 0.45 - 0.1 * rep))
    return out


def sub():
    out = []
    for b, c in prog(VERSE_AT, 8, VERSE):
        out.append(n(ROOT[c], b, 0.95, 0.75))
    for b, c in prog(BUILD, 7, DROP):
        out.append(n(ROOT[c], b, 0.95, 0.7))
    for b, c in prog(DROP_AT, 16, DROP):
        out += [n(ROOT[c], b, 0.36, 0.95), n(ROOT[c], b + 6 * S, 0.62, 0.9)]
    return out


def growl():
    out = []
    for b, c in prog(DROP_AT, 16, DROP):
        if (b - DROP_AT) % 2 == 1:                           # answer phrase on every 2nd bar
            out += [n(ROOT[c] + 12, b + 9 * S, 2 * S, 0.9), n(ROOT[c] + 24, b + 14 * S, 2 * S, 0.85)]
    return out


def kick():
    out = []
    for b in range(VERSE_AT + 4, BUILD):
        out += [n(60, b, S, 0.85), n(60, b + 10 * S, S, 0.7)]
    for b in range(BUILD, BUILD + 6):                        # four-on-the-floor build
        out += [n(60, b + q / 4, S, 0.75 + 0.03 * (b - BUILD)) for q in range(4)]
    for b in range(DROP_AT, OUTRO):
        out += [n(60, b, S, 1.0), n(60, b + 7 * S, S, 0.85), n(60, b + 10 * S, S, 0.9)]
    return out


def clap():
    out = []
    for b in range(VERSE_AT + 4, BUILD):
        out += [n(60, b + 0.25, S, 0.7), n(60, b + 0.75, S, 0.7)]
    for b in range(DROP_AT, OUTRO):
        out += [n(60, b + 0.25, S, 0.95), n(60, b + 0.75, S, 0.95)]
    return out


def hats():
    out = []
    for b in range(VERSE_AT, BUILD):
        out += [n(60, b + i * 2 * S, S, 0.45 if i % 2 else 0.3) for i in range(8)]
    for b in range(DROP_AT, OUTRO):
        out += [n(60, b + i * S, S, (0.8 if i % 4 == 2 else 0.45) + (0.1 if i % 2 == 0 else 0)) for i in range(16)]
    return out


def snare():
    out = []
    for b in range(BUILD, BUILD + 8):                        # accelerating roll + ramp
        k = b - BUILD
        if k == 7:
            div = 16
            span = 0.5                                       # stop at half-bar (pre-drop gap)
        else:
            div, span = (4, 1) if k < 2 else (8, 1) if k < 4 else (16, 1) if k < 6 else (16, 1)
        steps = int(div * span)
        for i in range(steps):
            out.append(n(60, b + i / div, 1 / div * 0.9, 0.35 + 0.08 * k + 0.02 * i / max(1, steps)))
    for b in range(DROP_AT, OUTRO):                          # layered with the clap on the backbeat
        out += [n(60, b + 0.25, S, 0.8), n(60, b + 0.75, S, 0.8)]
        if (b - DROP_AT) % 4 == 3:
            out += [n(60, b + (12 + i) * S, S, 0.5 + 0.1 * i) for i in range(4)]  # fill
    return out


PARTS = {"kick": (0, kick), "clap": (1, clap), "hats": (2, hats), "snare": (3, snare),
         "sub": (4, sub), "piano": (5, piano), "supersaw": (6, supersaw), "pluck": (7, pluck),
         "pad": (8, pad), "growl": (9, growl)}
MARKERS = [(1, "Intro"), (9, "Verse"), (17, "Build"), (25, "Drop"), (41, "Outro")]

if __name__ == "__main__":
    spec = {"tempo": 92, "markers": MARKERS,
            "parts": [{"name": k, "channel": ch, "notes": fn()} for k, (ch, fn) in PARTS.items()]}
    if "--out" in sys.argv:
        with open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8") as f:
            json.dump(spec, f)
    else:
        print(json.dumps(spec))
