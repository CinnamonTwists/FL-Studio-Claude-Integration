"""Reference-track pipeline: fetch (URL or file) -> optional stems -> analysis,
plus A/B comparison of a rendered mix against a reference.

Heavy/optional dependencies, imported lazily:
  librosa, soundfile, scipy, numpy  -- the [audio] extra (required)
  pyloudnorm                         -- LUFS (optional; falls back to RMS)
  yt-dlp + ffmpeg (+ node)           -- URL download (optional)
  demucs (+ torch, CUDA if present)  -- stem separation (optional)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]   # Krumhansl
_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
BANDS = {"sub <60": (20, 60), "bass 60-250": (60, 250), "low-mid 250-800": (250, 800),
         "mid 800-2.5k": (800, 2500), "hi-mid 2.5-6k": (2500, 6000), "air 6k+": (6000, 20000)}
SR = 22050


def default_root() -> Path:
    return Path(os.environ.get("FLSTUDIO_MCP_REFERENCE_DIR", Path.home() / "FL References"))


def _slug(s: str) -> str:
    return re.sub(r"[^\w\- ]+", "", s).strip()[:80] or "reference"


# -- fetching --------------------------------------------------------------------

def _ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    hits = sorted(base.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe")) if base.exists() else []
    return str(hits[-1]) if hits else None


def _ensure_pot_server() -> str:
    """Start the bgutil PO-token server (YouTube 403 workaround) if it's installed
    and not already listening on 127.0.0.1:4416."""
    try:
        with socket.create_connection(("127.0.0.1", 4416), timeout=0.5):
            return "running"
    except OSError:
        pass
    home = Path(os.environ.get("FLSTUDIO_MCP_BGUTIL_HOME",
                               Path.home() / "Projects" / "bgutil-ytdlp-pot-provider"))
    main_js = home / "server" / "build" / "main.js"
    node = shutil.which("node")
    if not (main_js.exists() and node):
        return "not installed"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([node, str(main_js)], creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.25)
        try:
            with socket.create_connection(("127.0.0.1", 4416), timeout=0.5):
                return "started"
        except OSError:
            continue
    return "failed to start"


def fetch(source: str, root: Path | None = None) -> dict:
    """Return {"wav": path, "title": str, "dir": path}. ``source`` is a file path
    or an http(s) URL (downloaded as WAV with yt-dlp)."""
    root = Path(root or default_root())
    if not re.match(r"https?://", source):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(source)
        d = root / _slug(p.stem)
        d.mkdir(parents=True, exist_ok=True)
        return {"wav": str(p), "title": p.stem, "dir": str(d)}

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise RuntimeError("yt-dlp is not installed: pip install yt-dlp") from None
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg not found (winget install Gyan.FFmpeg)")
    pot = _ensure_pot_server()
    meta = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--skip-download",
                           "--js-runtimes", "node", "--print", "%(title)s", source],
                          capture_output=True, text=True, timeout=120)
    title = (meta.stdout.strip().splitlines() or ["reference"])[-1]
    d = root / _slug(title)
    d.mkdir(parents=True, exist_ok=True)
    wav = d / "reference.wav"
    if not wav.exists():
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--js-runtimes", "node",
                            "--ffmpeg-location", str(Path(ff).parent), "-x", "--audio-format", "wav",
                            "-o", str(d / "reference.%(ext)s"), source],
                           capture_output=True, text=True, timeout=900)
        if not wav.exists():
            tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
            raise RuntimeError("download failed (PO-token server: %s): %s" % (pot, " | ".join(tail)))
    (d / "source.txt").write_text("%s\n%s\n" % (title, source), encoding="utf-8")
    return {"wav": str(wav), "title": title, "dir": str(d), "pot_server": pot}


def separate(wav: str, out_dir: str) -> dict | None:
    """Demucs htdemucs stems (drums/bass/other/vocals); None if demucs is missing."""
    try:
        import demucs  # noqa: F401
        import torch
    except ImportError:
        return None
    stem_dir = Path(out_dir) / "stems" / "htdemucs" / Path(wav).stem
    if not (stem_dir / "other.wav").exists():
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "-d", dev,
                        "-o", str(Path(out_dir) / "stems"), wav],
                       capture_output=True, text=True, timeout=1800, check=True)
    return {s: str(stem_dir / f"{s}.wav") for s in ("drums", "bass", "other", "vocals")}


# -- analysis --------------------------------------------------------------------

def _tempo_candidates(y, sr):
    import numpy as np
    import librosa
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    tg = librosa.feature.tempogram(onset_envelope=oenv, sr=sr)
    freqs = librosa.tempo_frequencies(tg.shape[0], sr=sr)
    prof = tg.mean(axis=1)
    ok = (freqs > 60) & (freqs < 200)
    seen, out = [], []
    for i in np.argsort(prof[ok])[::-1]:
        bpm = float(freqs[ok][i])
        if all(abs(bpm - s) > 3 for s in seen):
            seen.append(bpm)
            out.append({"bpm": round(bpm, 1), "strength": round(float(prof[ok][i]), 3)})
        if len(out) == 4:
            break
    return out, oenv


def _keys(chroma_mean):
    import numpy as np
    scores = []
    for i in range(12):
        scores.append((float(np.corrcoef(np.roll(_MAJ, i), chroma_mean)[0, 1]), f"{NOTES[i]} major"))
        scores.append((float(np.corrcoef(np.roll(_MIN, i), chroma_mean)[0, 1]), f"{NOTES[i]} minor"))
    scores.sort(reverse=True)
    return [{"key": k, "r": round(r, 3)} for r, k in scores[:4]]


def _chords_per_bar(y, sr, beats, bpb=4):
    import numpy as np
    import librosa
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
    T, names = [], []
    for i in range(12):
        for q, iv in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            v = np.zeros(12)
            v[[(i + x) % 12 for x in iv]] = 1
            T.append(v / np.linalg.norm(v))
            names.append(NOTES[i] + q)
    T = np.array(T)
    bars = beats[::bpb]
    out = []
    for a, b in zip(bars[:-1], bars[1:], strict=False):
        c = chroma[:, a:b].mean(axis=1)
        out.append("N" if c.sum() < 1e-6 else names[int(np.argmax(T @ (c / (np.linalg.norm(c) + 1e-9))))])
    return out


def _bass_roots(y, sr, beats, bpb=4):
    import numpy as np
    import librosa
    f0, voiced, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C1"), fmax=librosa.note_to_hz("C4"),
                                 sr=sr, frame_length=4096, hop_length=512)
    bars = beats[::bpb]
    out = []
    for a, b in zip(bars[:-1], bars[1:], strict=False):
        seg = f0[a:b][voiced[a:b]]
        out.append("-" if len(seg) < 3 else
                   NOTES[np.bincount(np.round(librosa.hz_to_midi(seg)).astype(int) % 12).argmax()])
    return out


def _bar_energy(y, sr, bar_times):
    import numpy as np
    import librosa
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    out = []
    for a, b in zip(bar_times[:-1], bar_times[1:], strict=False):
        m = (t >= a) & (t < b)
        out.append(round(float(20 * np.log10(rms[m].mean() + 1e-9)), 1) if m.any() else -90.0)
    return out


def _sections(energy, min_bars=4):
    """Label contiguous bar runs as low/mid/high energy (rough song map)."""
    import numpy as np
    e = np.convolve(np.array(energy), np.ones(3) / 3, mode="same")
    hi, lo = e.max() - 3.0, np.median(e) - 4.0
    labels = ["high" if v >= hi else "low" if v <= lo else "mid" for v in e]
    runs = []
    for i, lab in enumerate(labels):
        if runs and runs[-1][0] == lab:
            runs[-1][2] = i
        else:
            runs.append([lab, i, i])
    merged = []
    for r in runs:                      # absorb runs shorter than min_bars into the previous run
        if merged and r[2] - r[1] + 1 < min_bars:
            merged[-1][2] = r[2]
        else:
            merged.append(r)
    return [{"energy": lab, "bars": f"{a + 1}-{b + 1}"} for lab, a, b in merged]


def _common_loop(chords, size=4):
    seqs = Counter(tuple(chords[i:i + size]) for i in range(0, max(0, len(chords) - size + 1)))
    seqs = {k: v for k, v in seqs.items() if "N" not in k and len(set(k)) > 1}
    if not seqs:
        return None
    loop, n = max(seqs.items(), key=lambda kv: kv[1])
    return {"loop": " - ".join(loop), "occurrences": n}


def _drum_grid(path, bar_times, b0, b1):
    import numpy as np
    import librosa
    import scipy.signal as sg
    y, sr = librosa.load(path, sr=SR, mono=True)
    out = {}
    for name, (lo, hi) in {"kick": (30, 120), "snare": (180, 2500), "hats": (6000, 10000)}.items():
        x = sg.sosfilt(sg.butter(4, [lo, hi], btype="band", fs=sr, output="sos"), y)
        env = librosa.onset.onset_strength(y=x, sr=sr, hop_length=256)
        times = librosa.frames_to_time(librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=256,
                                                                  delta=0.15), sr=sr, hop_length=256)
        hist = np.zeros(16)
        for b in range(b0, min(b1, len(bar_times) - 1)):
            a, e = bar_times[b], bar_times[b + 1]
            for t in times[(times >= a) & (times < e)]:
                hist[int(round((t - a) / (e - a) * 16)) % 16] += 1
        hist /= max(1, b1 - b0)
        out[name] = [i + 1 for i, v in enumerate(hist) if v >= 0.5]   # 16th steps hit in >=50% of bars
    return out


def tonal_balance(y, sr):
    import numpy as np
    import librosa
    S = np.abs(librosa.stft(y, n_fft=4096)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=4096)
    tot = S.sum()
    return {k: round(float(10 * np.log10(S[(f >= a) & (f < b)].sum() / tot + 1e-12)), 1)
            for k, (a, b) in BANDS.items()}


def analyze(wav: str, stems: dict | None = None, bpm: float | None = None) -> dict:
    import numpy as np
    import librosa
    y, sr = librosa.load(wav, sr=SR, mono=True)
    cands, oenv = _tempo_candidates(y, sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr,
                                           start_bpm=bpm or cands[0]["bpm"], tightness=400)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    bar_times = [round(float(t), 3) for t in beat_times[::4]]
    yh = librosa.load(stems["other"], sr=SR, mono=True)[0] if stems else librosa.effects.harmonic(y)
    chroma_mean = librosa.feature.chroma_cqt(y=yh, sr=sr).mean(axis=1)
    chords = _chords_per_bar(yh, sr, beats)
    energy = _bar_energy(y, sr, bar_times)
    loud = int(np.argmax(np.convolve(energy, np.ones(8), mode="valid")))   # loudest 8-bar window
    res = {
        "duration_sec": round(len(y) / sr, 1),
        "tempo_candidates": cands,
        "beat_grid_bpm": round(float(np.atleast_1d(tempo)[0]), 1),
        "key_candidates": _keys(chroma_mean),
        "pitch_class_profile": {NOTES[i]: round(float(v), 2) for i, v in enumerate(chroma_mean / chroma_mean.max())},
        "chord_loop": _common_loop(chords),
        "chords_per_bar": chords,
        "sections": _sections(energy),
        "loudest_8_bars": f"{loud + 1}-{loud + 8}",
        "bar_energy_db": energy,
        "bar_start_times": bar_times,
        "tonal_balance_db_rel": tonal_balance(y, sr),
        "stems": stems,
    }
    if stems:
        yb = librosa.load(stems["bass"], sr=SR, mono=True)[0]
        res["bass_roots_per_bar"] = _bass_roots(yb, sr, beats)
        res["drum_grid_loudest_section"] = _drum_grid(stems["drums"], bar_times, loud, loud + 8)
    return res


def summarize(res: dict) -> dict:
    """Compact view for an LLM: drop the long per-bar arrays, keep the musical facts."""
    keep = {k: v for k, v in res.items()
            if k not in ("chords_per_bar", "bar_energy_db", "bar_start_times", "bass_roots_per_bar", "stems")}
    keep["chords_per_bar"] = " ".join(res.get("chords_per_bar", []))
    if "bass_roots_per_bar" in res:
        keep["bass_roots_per_bar"] = " ".join(res["bass_roots_per_bar"])
    return keep


def analyze_reference(source: str, stems: bool = True, out_dir: str | None = None, bpm: float | None = None) -> dict:
    f = fetch(source, Path(out_dir) if out_dir else None)
    st = separate(f["wav"], f["dir"]) if stems else None
    res = analyze(f["wav"], st, bpm)
    path = Path(f["dir"]) / "analysis.json"
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    out = summarize(res)
    out.update({"title": f["title"], "wav": f["wav"], "analysis_json": str(path),
                "stems_dir": str(Path(st["other"]).parent) if st else None,
                "stem_separation": "demucs htdemucs" if st else "skipped (demucs not installed or stems=False)"})
    return out


# -- A/B comparison --------------------------------------------------------------

def _loudest_window(y, sr, seconds):
    import numpy as np
    hop = int(sr * 0.5)
    mono = y.mean(axis=1)
    e = np.array([np.mean(mono[i:i + hop] ** 2) for i in range(0, len(mono) - hop, hop)])
    w = max(1, int(seconds / 0.5))
    if len(e) <= w:
        return 0.0, len(mono) / sr
    i = int(np.argmax(np.convolve(e, np.ones(w), mode="valid")))
    return i * 0.5, i * 0.5 + seconds


def _metrics(y, sr):
    import numpy as np
    import librosa
    mono = y.mean(axis=1)
    try:
        import pyloudnorm as pyln
        lufs = round(float(pyln.Meter(sr).integrated_loudness(y)), 1)
    except ImportError:
        lufs = None
    peak = 20 * np.log10(np.abs(y).max() + 1e-12)
    rms = 20 * np.log10(np.sqrt((mono ** 2).mean()) + 1e-12)
    mid, side = (y[:, 0] + y[:, -1]) / 2, (y[:, 0] - y[:, -1]) / 2
    width = 20 * np.log10(np.sqrt((side ** 2).mean()) / (np.sqrt((mid ** 2).mean()) + 1e-12) + 1e-12)
    m32 = mono.astype("float32")
    S = np.abs(librosa.stft(m32, n_fft=4096))
    return {"lufs": lufs, "peak_dbfs": round(float(peak), 1), "crest_db": round(float(peak - rms), 1),
            "side_mid_db": round(float(width), 1),
            "centroid_hz": int(librosa.feature.spectral_centroid(S=S, sr=sr).mean()),
            "bands_db_rel": tonal_balance(m32, sr)}


def compare(mix: str, reference: str, mix_range=None, ref_range=None, window_sec: float = 20.0) -> dict:
    import soundfile as sf
    out = {}
    for key, path, rng in (("mix", mix, mix_range), ("reference", reference, ref_range)):
        y, sr = sf.read(path, always_2d=True)
        a, b = rng if rng else _loudest_window(y, sr, window_sec)
        out[key] = dict(_metrics(y[int(a * sr):int(b * sr)], sr), section_sec=[round(a, 1), round(b, 1)])
    m, r = out["mix"], out["reference"]
    diff = {k: (round(m[k] - r[k], 1) if m[k] is not None and r[k] is not None else None)
            for k in ("lufs", "peak_dbfs", "crest_db", "side_mid_db", "centroid_hz")}
    diff["bands_db_rel"] = {k: round(m["bands_db_rel"][k] - r["bands_db_rel"][k], 1) for k in BANDS}
    hints = []
    if diff["lufs"] is not None and diff["lufs"] < -3:
        hints.append("Mix is %.1f LU quieter: drive the master limiter/maximizer harder." % -diff["lufs"])
    if diff["side_mid_db"] < -2:
        hints.append("Mix is narrower: widen pads/chords (negative stereo separation = wider).")
    for band, d in diff["bands_db_rel"].items():
        if abs(d) >= 2:
            hints.append("%s is %+.1f dB vs reference." % (band, d))
    return {"mix": m, "reference": r, "diff_mix_minus_ref": diff, "hints": hints}
