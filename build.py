#!/usr/bin/env python3
"""Pipeline lengkap: judul + narasi -> video 60 detik (720x1280, 30fps) + QA.

  python3 build.py --title "Judul" --narration "kalimat1. kalimat2. ..." --out video.mp4
  python3 build.py --story story.json --out video.mp4 [--preview] [--voice voiceover.mp3]
"""
import argparse, json, os, subprocess, sys, shutil, math
HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0: sys.exit(f"GAGAL: {' '.join(map(str, cmd))[:140]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story"); ap.add_argument("--title"); ap.add_argument("--narration")
    ap.add_argument("--out", required=True); ap.add_argument("--work")
    ap.add_argument("--voice"); ap.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
    ap.add_argument("--preview", action="store_true", help="hanya 12 detik pertama (cek cepat)")
    a = ap.parse_args()
    work = a.work or os.path.splitext(os.path.abspath(a.out))[0] + "_work"
    os.makedirs(work, exist_ok=True)
    tl_path = os.path.join(work, "timeline.json")
    cmd = [sys.executable, os.path.join(HERE, "director.py"), "--out", tl_path]
    cmd += ["--story", a.story] if a.story else ["--title", a.title, "--narration", a.narration]
    run(cmd)
    tl = json.load(open(tl_path, encoding="utf-8"))
    if tl["warnings"] and not os.environ.get("ALLOW_WARN"):
        sys.exit("Berhenti karena peringatan narasi (set ALLOW_WARN=1 untuk lanjut): " + " | ".join(tl["warnings"]))
    total = int(round(tl["duration"] * tl["fps"]))
    last = min(total, 360) if a.preview else total
    # render paralel
    per = math.ceil(last / a.workers); procs, parts = [], []
    for k in range(a.workers):
        s, e = k * per, min(last, (k + 1) * per)
        if s >= e: continue
        part = os.path.join(work, f"part{k}.mp4"); parts.append(part)
        env = dict(os.environ, NODE_PATH=subprocess.check_output(["npm", "root", "-g"], text=True).strip())
        procs.append(subprocess.Popen(["node", os.path.join(HERE, "render.js"), tl_path, str(s), str(e), part, os.path.join(work, f"layout{k}.json")], env=env))
    codes = [p.wait() for p in procs]
    if any(codes): sys.exit(f"render gagal (kode {codes})")
    with open(os.path.join(work, "list.txt"), "w") as f:
        for p in parts: f.write(f"file '{p}'\n")
    silent = os.path.join(work, "silent.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(work, "list.txt"), "-c", "copy", silent])
    # audio
    wav = os.path.join(work, "audio.wav")
    run([sys.executable, os.path.join(HERE, "sfx.py"), tl_path, wav] + ([a.voice] if a.voice else []))
    run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", str(last / tl["fps"]), "-shortest", "-movflags", "+faststart", a.out])
    print("video ->", a.out)
    if not a.preview:
        run([sys.executable, os.path.join(HERE, "qa.py"), a.out, tl_path, work])


if __name__ == "__main__":
    main()
