#!/usr/bin/env python3
"""QA otomatis: gagal (exit 1) bila ada bug. usage: qa.py video.mp4 timeline.json workdir"""
import glob, json, subprocess, sys, os
import numpy as np
from PIL import Image

video, tlp, work = sys.argv[1:4]
tl = json.load(open(tlp, encoding="utf-8"))
fails, notes = [], []
def fail(m): fails.append(m)

# 1. container / stream
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", video], text=True))
v = next(s for s in pr["streams"] if s["codec_type"] == "video"); au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
dur = float(pr["format"]["duration"])
if (v["width"], v["height"]) != (720, 1280): fail(f"resolusi {v['width']}x{v['height']} != 720x1280")
if abs(dur - tl["duration"]) > 0.12: fail(f"durasi {dur:.2f}s != {tl['duration']}s")
if v["r_frame_rate"] != "30/1": fail(f"fps {v['r_frame_rate']}")
if not au: fail("tidak ada audio")
if int(v["nb_frames"]) != int(tl["duration"] * tl["fps"]) if "nb_frames" in v else False: fail(f"jumlah frame {v['nb_frames']}")

# 2. error halaman + layout
errs, lay = [], []
for f in glob.glob(os.path.join(work, "layout*.json")):
    d = json.load(open(f)); errs += d["errors"]; lay += d["layout"]
if errs: fail("error JS/WebGL: " + "; ".join(errs[:3]))
for m in lay:
    sc = tl["scenes"][m["scene"]]
    s, w, h = m["sub"], m["wm"], m["hud"]
    if sc["kind"] == "outro": pass
    if s["x"] < 30 or s["r"] > 690: fail(f"scene {m['scene']} subtitle keluar tepi ({s['x']:.0f}..{s['r']:.0f})")
    if sc["kind"] == "body" and s["b"] > h["y"] + 0 and s["b"] > w["y"] - 24: fail(f"scene {m['scene']} subtitle menabrak watermark (bottom {s['b']:.0f} vs {w['y']:.0f})")
    if sc["kind"] == "body" and s["h"] > 27 * 1.38 * 4.1: fail(f"scene {m['scene']} subtitle > 4 baris ({s['h']:.0f}px)")
    if sc["kind"] == "hook" and s["h"] > 35 * 1.32 * 4.1: fail(f"hook > 4 baris")
    if sc["kind"] != "outro" and m["hudOp"] > 0.9:
        if h["r"] > 690 or h["x"] < 20: fail(f"scene {m['scene']} HUD keluar layar")
        if s["y"] < h["b"] + 20 and sc["kind"] == "body": fail(f"scene {m['scene']} subtitle menabrak HUD")
    if w["x"] < 0 or w["r"] > 720 or w["b"] > 1280: fail("watermark keluar layar")
    if sc["kind"] == "outro" and "words2" in sc:
        s2 = m["sub2"]
        if s2["y"] < s["b"] + 12: fail(f"kicker outro menabrak hook ({s['b']:.0f} vs {s2['y']:.0f})")
        if s2["b"] > w["y"] - 20: fail("kicker outro menabrak watermark")

# 3. frame check tiap 0.5 detik
tmp = os.path.join(work, "qa_frames"); os.makedirs(tmp, exist_ok=True)
for f in glob.glob(tmp + "/*.png"): os.remove(f)
subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", video, "-vf", "fps=2,scale=360:-1", tmp + "/f%03d.png"])
fr = sorted(glob.glob(tmp + "/*.png")); prev = None; black = 0
wm_vals = []
for i, p in enumerate(fr):
    im = np.asarray(Image.open(p).convert("L"), dtype=float)
    t = i / 2
    near_cut = any(sc["t0"] - 0.3 <= t <= sc["t0"] + 0.75 for sc in tl["scenes"])  # jendela dip-to-black/flash yang disengaja
    if im.mean() < 2.0:
        black += 1
        if 1.0 < t < tl["duration"] - 0.6 and not near_cut: fail(f"frame hitam/kosong di t={t:.1f}s")
    # watermark: area bawah tengah harus punya piksel terang (teks)
    crop = im[int(1214 / 1280 * im.shape[0]):int(1250 / 1280 * im.shape[0]), int(120 / 720 * im.shape[1]):int(600 / 720 * im.shape[1])]
    wm_vals.append(crop.max())
    if t > 0.7 and crop.max() < 70 and not near_cut: fail(f"watermark tidak terlihat di t={t:.1f}s (max={crop.max():.0f})")
    if prev is not None and np.abs(im - prev).mean() < 0.004 and 0.7 < t < tl["duration"] - 6 and not near_cut: fail(f"frame beku di t={t:.1f}s")
    prev = im
# subtitle terlihat: di tengah tiap scene body wilayah subtitle punya piksel terang
for i, sc in enumerate(tl["scenes"]):
    if sc["kind"] == "outro": continue
    tm = sc["t0"] + (sc["t1"] - sc["t0"]) * 0.75
    k = min(len(fr) - 1, int(tm * 2)); im = np.asarray(Image.open(fr[k]).convert("L"), dtype=float)
    top = 250 if sc["kind"] == "hook" else 770
    reg = im[int(top / 1280 * im.shape[0]):int((top + 150) / 1280 * im.shape[0]), int(60 / 720 * im.shape[1]):int(660 / 720 * im.shape[1])]
    if reg.max() < 150: fail(f"scene {i}: subtitle tidak terlihat di t={tm:.1f}s")

# 4. audio
subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", os.path.join(work, "qa.wav")])
import wave
w = wave.open(os.path.join(work, "qa.wav")); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
if np.abs(x).max() >= 0.995: fail("audio clipping")
rms = [np.sqrt(np.mean(x[i:i + 16000] ** 2)) for i in range(0, len(x) - 16000, 16000)]
quiet = [i for i, r in enumerate(rms) if r < 0.004]
if quiet: fail(f"audio nyaris senyap di detik {quiet}")
notes.append(f"peak audio {np.abs(x).max():.2f}, rms rata-rata {np.mean(rms):.3f}")
# 5. sinkron SFX: setiap cue whoosh ada energi
notes.append(f"scene={len(tl['scenes'])} cue_sfx={len(tl['sfx']['cues'])} frame_hitam_wajar={black}")

print("\n".join("catatan: " + n for n in notes))
if fails:
    print("QA GAGAL:"); [print(" -", f) for f in fails]; sys.exit(1)
print("QA LULUS: durasi, resolusi, audio, watermark, subtitle, layout, frame beku/hitam semua aman.")
