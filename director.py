#!/usr/bin/env python3
"""Director: judul + narasi  ->  timeline.json (60 detik, 720x1280, 30fps).

Semua keputusan visual (set, kamera, karakter, pose, counter HUD, transisi, cue SFX)
dibuat di sini secara deterministik, jadi video dengan input sama selalu identik.
"""
import json, math, re, sys, hashlib, argparse

W, H, FPS = 720, 1280, 30
DURATION = 60.0
INTRO_MIN, OUTRO_DUR = 4.4, 5.0
MIN_SCENE, MAX_SCENE = 2.0, 6.6
CPS = 14.0  # kecepatan baca nyaman (karakter/detik)

# ---------------------------------------------------------------- kamus kata kunci
KW = {
    "street": "jalan trotoar mobil motor lampu kota malam tabrak sirene ambulans macet lari berjalan aspal lalu lintas simpang rem klakson".split(),
    "room": "rumah kamar ibu ayah bapak keluarga meja kue ulang tahun dapur makan kursi tidur adik lilin kakak nenek kakek pulang".split(),
    "phone": "telepon panggilan pesan hp ponsel chat menelepon dering layar notifikasi suara kabar".split(),
    "space": "bintang atom semesta galaksi langit kosmos debu waktu selamanya abadi alam".split(),
    "field": "cahaya terang kabut pagi fajar surga damai akhirnya sunyi hening kenangan pergi senja".split(),
}
IMPACT = "tiba-tiba tabrak menerobos kecelakaan kaget terkejut jatuh brak meledak mendadak".split()
SHOCK = IMPACT + "panik takut teriak".split()
CRY = "menangis tangis air mata sedih kehilangan rindu menyesal maaf duka".split()
SMILE = "bahagia senang tersenyum hangat pelukan tawa gembira bangga".split()
LIE = "tergeletak terbaring tertidur meninggal mati sekarat".split()
WALK = "berjalan melangkah lari menyeberang pulang pergi".split()
CPR = "rjp resusitasi menolong penolong petugas".split()
FLAT = "mendatar berhenti padam hilang henti".split()
BRIGHT = "cahaya terang bintang akhirnya damai surga fajar".split()
EMO_WORDS = ("meninggal kehilangan mati terakhir selamanya rindu maaf cinta sayang menangis hilang sepi "
             "sunyi bintang cahaya pulang ibu ayah sekarat berdetak nyala menyala mendatar terlambat "
             "kenangan peluk pelukan janji tangis air mata hidup waktu").split()
STOP = set("yang dan di ke dari untuk pada dengan itu ini kamu aku kita mereka saja juga masih sudah akan bisa "
           "tapi atau karena jika kalau saat lalu lagi lebih sangat tidak ada adalah sebuah seorang".split())

PROTAG = dict(type="man", skin="#d9a273", shirt="#e9e6df", pants="#2b2f45", hair="#2a1c14", collar="#cfcac0")
MOTHER = dict(type="woman", skin="#e2b48c", shirt="#b23b55", pants="#5a2230", hair="#2a1c14", hijab="#c24a63")
KID = dict(type="kid", skin="#d6a07a", shirt="#3fae5a", pants="#2b3a55", hair="#1e140f")
ELDER = dict(type="elder", skin="#d8b394", shirt="#b9b0a4", pants="#4a4038", hair="#c9c9c9", glasses=True, sleeveLong=True)
MEDIC = dict(type="man", skin="#8a5a3c", shirt="#e8742a", pants="#1b1b22", hair="#15100c", stripe=True, sleeveLong=True)
SILS = [dict(type="man", sil=True, skin="#000", shirt="#000", pants="#000"), dict(type="woman", sil=True, skin="#000", shirt="#000", pants="#000", hijab="#000"),
        dict(type="kid", sil=True, skin="#000", shirt="#000", pants="#000"), dict(type="man", sil=True, skin="#000", shirt="#000", pants="#000")]


def has(text, words):
    t = text.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\w*", t) for w in words)


def char(base, **kw):
    d = dict(base); d.update(kw); return d


def tokens(text):
    return re.findall(r"[A-Za-zÀ-ÿ0-9'’\-]+", text.lower())


# ---------------------------------------------------------------- parsing narasi
def split_narration(raw):
    lines = [l.strip() for l in re.split(r"\n+", raw.strip()) if l.strip()]
    out = []
    for l in lines:
        m = re.match(r"^\[(.+?)\]\s*(.*)$", l)
        tag = None
        if m:
            tag, l = m.group(1), m.group(2)
        parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-Ý“\"'0-9])", l) if p.strip()]
        for i, p in enumerate(parts):
            if len(p) > 120:  # pecah di koma
                cs = [c.strip() for c in re.split(r"(?<=,)\s+", p)]
                buf = ""
                for c in cs:
                    if buf and len(buf) + len(c) > 70:
                        out.append((buf, tag if not out or tag is None else None)); buf = c
                    else:
                        buf = (buf + " " + c).strip()
                if buf: out.append((buf, tag))
            else:
                out.append((p, tag if i == 0 else None))
    return out


def words_with_hl(text, hl_color, auto=True):
    """Kembalikan list {w, hl}. *kata* = sorot manual. Tanpa marker -> sorot otomatis."""
    manual = re.findall(r"\*([^*]+)\*", text)
    clean = text.replace("*", "")
    toks = clean.split()
    res = [{"w": w, "hl": None} for w in toks]
    if manual:
        targets = [m.strip().lower() for m in manual]
        flat = " ".join(t.lower() for t in toks)
        for tgt in targets:
            tw = tgt.split()
            for i in range(len(toks) - len(tw) + 1):
                seg = [re.sub(r"[^\w'’\-]", "", x.lower()) for x in toks[i:i + len(tw)]]
                if seg == [re.sub(r"[^\w'’\-]", "", x) for x in tw]:
                    for j in range(len(tw)): res[i + j]["hl"] = hl_color
                    break
    elif auto and toks:
        best, bi = -1, None
        for i, w in enumerate(toks):
            c = re.sub(r"[^\w'’\-]", "", w.lower())
            if not c or c in STOP: continue
            score = (10 if any(c.startswith(e) for e in EMO_WORDS) else 0) + len(c) * 0.1 + (0.5 if i == len(toks) - 1 else 0)
            if score > best: best, bi = score, i
        if bi is not None: res[bi]["hl"] = hl_color
    return clean, res


# ---------------------------------------------------------------- counter ladder
def fmt_counter(sec):
    """-> (mode, v0, unit, text)"""
    if sec < 3600:
        return "time", sec, "MENIT"
    if sec < 86400:
        return "time", sec, "JAM"
    days = sec / 86400
    if days < 365:
        return "int", int(days), "HARI"
    return "int", int(days / 365), "TAHUN"


def ladder(n, start=5.0, end=20 * 365 * 86400.0):
    if n <= 1: return [start]
    return [math.exp(math.log(start) + (math.log(end) - math.log(start)) * i / (n - 1)) for i in range(n)]


def parse_tag(tag):
    m = re.match(r"^(.+?)\s+(DETIK|MENIT|JAM|HARI|BULAN|TAHUN|BPM)$", tag.strip(), re.I)
    return (m.group(1), m.group(2).upper()) if m else None


# ---------------------------------------------------------------- director
def direct(title, narration, opts=None):
    opts = opts or {}
    watermark = opts.get("watermark", "animasindo")
    prefix = opts.get("prefix", "SEJAK")
    raw = split_narration(narration)
    if len(raw) < 4:
        raise SystemExit("Narasi terlalu pendek: butuh minimal 4 kalimat/baris agar jadi video 60 detik.")

    hook_text, hook_tag = raw[0]
    rest = raw[1:]
    kicker = None
    if rest and rest[-1][0].rstrip().endswith("?") and len(rest) >= 3:
        kicker = rest[-1][0]; rest = rest[:-1]
    if opts.get("cta"): kicker = opts["cta"]

    # ---- alokasi waktu
    hook_dur = max(INTRO_MIN, len(hook_text) / CPS + 1.6)
    outro_dur = OUTRO_DUR if (kicker or opts.get("loop_hook", True)) else 3.0
    avail = DURATION - hook_dur - outro_dur
    durs = [max(MIN_SCENE, min(MAX_SCENE, len(t) / CPS + 1.0)) for t, _ in rest]
    warn = []
    for _ in range(40):
        tot = sum(durs)
        if abs(tot - avail) < 0.01: break
        free = [i for i, d in enumerate(durs) if (tot < avail and d < MAX_SCENE) or (tot > avail and d > 1.5)]
        if not free: break
        k = avail / tot
        for i in free: durs[i] = max(1.5, min(MAX_SCENE, durs[i] * (1 + (k - 1) * 0.9)))
    tot = sum(durs)
    if tot > avail + 0.05:
        warn.append(f"Narasi terlalu panjang: butuh {tot:.1f}s tapi tersedia {avail:.1f}s. Persingkat narasi (maks. ± {int(avail*CPS*0.9)} karakter di luar kalimat pembuka).")
    if tot < avail - 0.05:  # terlalu pendek -> perpanjang hook/outro/ratakan
        extra = avail - tot
        hook_dur += extra * 0.3; outro_dur += extra * 0.2
        durs = [d + extra * 0.5 / max(1, len(durs)) for d in durs]
        tot = sum(durs)
        gap = DURATION - hook_dur - outro_dur - tot
        outro_dur += gap
        if extra > 12: warn.append(f"Narasi pendek (kurang {extra:.0f}s). Tambah kalimat agar adegan lebih padat.")
    # normalisasi akhir agar total persis 60.0
    scale = (DURATION - hook_dur - outro_dur) / sum(durs)
    durs = [d * scale for d in durs]

    cast = {"protag": PROTAG, "mother": MOTHER, "kid": KID, "elder": ELDER, "medic": MEDIC}
    scenes = []
    t = 0.0
    n_body = len(rest)
    secs = ladder(n_body, start=opts.get("counter_start", 5.0))

    # ---- hook scene
    hclean, hwords = words_with_hl(hook_text, "red")
    hud_intro = opts.get("intro")
    if hud_intro:
        hud = dict(mode="int", v0=hud_intro["from"], v1=hud_intro["to"], unit=hud_intro.get("unit", "BPM"), label=hud_intro["label"].upper())
    else:
        hud = dict(mode="time", v0=0, rate=1.0, unit="MENIT", label=(prefix + " " + title).upper())
    scenes.append(dict(kind="hook", t0=0.0, t1=hook_dur, set="street", shot="drive", text=hclean, words=hwords,
                       chars=[], cars=[dict(x=-2.4, z=-34, vz=5.5, color="#8a8f98"), dict(x=2.4, z=-70, vz=-4.0, color="#7a1f2a")],
                       hud=hud, tin="dip", fill=0.3, shake=0.035, tint=1.0, sfxset="street"))
    t = hook_dur

    # ---- body scenes
    prev_set, impact_seen, crack_on, shot_i = "street", False, False, 0
    cyc_sets = ["street", "room", "phone", "field", "space"]
    SHOTS = ["wide", "close", "low", "medium", "orbit", "close", "pull", "side", "medium"]
    for i, ((text, tag), d) in enumerate(zip(rest, durs)):
        clean, words = words_with_hl(text, "gold")
        low = clean.lower()
        scores = {s: sum(1 for w in ws if re.search(r"\b" + w, low)) for s, ws in KW.items()}
        best = max(scores, key=lambda k: scores[k])
        st = best if scores[best] > 0 else prev_set
        if st == prev_set and scores[best] == 0 and i % 3 == 2:
            st = cyc_sets[(cyc_sets.index(prev_set) + 1) % 4]
        if i == n_body - 1 and scores[best] == 0 and n_body > 6: st = "space"
        impact = has(low, IMPACT)
        if impact: st = "street"; impact_seen = True; crack_on = True
        if st in ("room", "space", "field") and crack_on and not has(low, ["jalan", "malam"]): crack_on = False if st != "field" else crack_on
        if st == "room" or st == "space": crack_on = False

        pose = "idle"; emo = "neutral"
        if has(low, SHOCK): pose, emo = "shock", "shock"
        elif has(low, CPR): pose, emo = "cpr", "neutral"
        elif has(low, LIE) and st in ("street", "field"): pose = "lie"
        elif has(low, CRY): pose, emo = "cry", "cry"
        elif has(low, SMILE): pose, emo = "smile", "smile"
        elif has(low, WALK): pose = "walk"
        if emo == "neutral" and has(low, ["sedih", "kehilangan", "sepi", "sunyi"]): emo = "sad"

        chars = []
        who = "protag"
        if has(low, ["ibu", "bunda", "mama", "emak"]): who = "mother"
        elif has(low, ["adik", "anak"]): who = "kid"
        elif has(low, ["nenek", "kakek", "tua", "renta", "lansia"]): who = "elder"
        if st == "street":
            if pose == "cpr":
                chars = [char(cast["protag"], x=0, z=0, yaw=0.5, pose="lie", emotion="neutral"),
                         char(cast["medic"], x=1.5, z=0.5, yaw=-1.9, pose="cpr", emotion="neutral")]
                chars[0]["x"] = 0; chars = [chars[1], chars[0]] if False else chars
                chars = [chars[0], chars[1]]
            elif pose == "lie":
                chars = [char(cast["protag"], x=0, z=0.4, yaw=0.35, pose="lie", emotion="sad")]
            else:
                base = cast[who]
                if pose == "walk":
                    chars = [char(base, x=0.6, z=2.0, yaw=math.pi if i % 2 else 0.2, vz=-1.3 if i % 2 else 0.0, pose="walk", emotion=emo)]
                    if i % 2 == 0: chars[0].update(vz=1.2, z=-5.0, yaw=0.0)
                else:
                    chars = [char(base, x=0, z=0, yaw=0.25, pose=pose, emotion=emo)]
        elif st == "room":
            if who == "kid": chars = [char(cast["kid"], x=0.2, z=-2.0, yaw=0, pose=pose if pose != "idle" else "smile", emotion=emo if emo != "neutral" else "smile"), char(cast["mother"], x=-1.4, z=-2.1, yaw=0.1, pose="smile", emotion="smile")]
            elif who == "elder": chars = [char(cast["elder"], x=0, z=-2.0, yaw=0, pose=pose, emotion=emo)]
            elif who == "mother": chars = [char(cast["mother"], x=-0.3, z=-2.1, yaw=0, pose=pose if pose != "idle" else "smile", emotion=emo if emo != "neutral" else "smile"), char(cast["kid"], x=1.5, z=-2.0, yaw=-0.2, pose="smile", emotion="smile"), char(cast["protag"], x=-2.3, z=-2.0, yaw=0.3, pose="idle", emotion="sad")]
            else: chars = [char(cast["protag"], x=-0.3, z=-2.1, yaw=0.1, pose=pose, emotion=emo), char(cast["mother"], x=1.5, z=-2.1, yaw=-0.2, pose="smile", emotion="smile")]
        elif st == "field":
            chars = [dict(c, x=x, z=-16 - j * 0.8, yaw=0, pose="stand", emotion="neutral") for j, (c, x) in enumerate(zip(SILS, [-3.2, -1.1, 1.0, 3.1]))]
        elif st == "phone":
            chars = []
        else:
            chars = []

        # kamera
        if st == "phone": shot = "top" if i % 2 == 0 else "tilt"
        elif st == "space": shot = "float"
        elif st == "field": shot = "pull" if i % 2 == 0 else "wide"
        else:
            shot = SHOTS[shot_i % len(SHOTS)]; shot_i += 1
            if pose == "lie": shot = "low" if shot not in ("low", "wide") else shot
            if pose == "cpr": shot = "side" if shot not in ("side", "low", "wide") else shot
            if st == "room" and shot in ("low", "pull") and len(chars) > 1: shot = "medium"
            if st == "room" and len(chars) > 1 and shot == "close": shot = "medium"
        if st == "phone": chars = []

        # counter
        sec = secs[i]
        if tag and parse_tag(tag):
            v, unit = parse_tag(tag)
            hud = dict(mode="fixed", text=v, unit=unit, label="")
        else:
            mode, v0, unit = fmt_counter(sec)
            hud = dict(mode=mode, v0=v0, v1=v0, rate=1.0 if mode == "time" and unit == "MENIT" else 0.0, unit=unit, label="")

        tin = "flash" if impact else ("dip" if i % 2 == 0 or st != prev_set else "dip")
        sc = dict(kind="body", t0=t, t1=t + d, set=st, shot=shot, text=clean, words=words, chars=chars, hud=hud, tin=tin,
                  impact=impact, crack=bool(crack_on and st in ("street", "phone", "field")), crack_start=0.0 if impact else 0.0,
                  fill=0.55 if st in ("street", "phone") else 0.3, shake=0.02 if st != "street" else 0.03, tint=1.0, sfxset=st,
                  flags=dict(shock=bool(has(low, SHOCK)), flat=bool(has(low, FLAT)), bright=bool(has(low, BRIGHT)), cry=pose == "cry"))
        if st == "street" and impact:
            sc["cars"] = [dict(x=-14, z=-2, vz=0, vx=26, color="#7a1f2a")]
        elif st == "street" and i % 2 == 0:
            sc["cars"] = [dict(x=2.4, z=-40, vz=7.0, color="#2a3a52")]
        scenes.append(sc)
        prev_set = st
        t += d

    # ---- outro
    last_scene = scenes[-1]
    oc, ow = words_with_hl(hook_text, "red")
    outro = dict(kind="outro", t0=t, t1=DURATION, set="space", shot="float", text=oc, words=ow, chars=[], hud=None, tin="dip", fill=0.2,
                 shake=0.01, tint=1.0, sfxset="space", crack=False)
    if kicker:
        kc, kw = words_with_hl(kicker, "gold", auto=True)
        outro["words2"] = [dict(w=x["w"], hl=None) for x in kw]
        # kalimat penutup berwarna emas seluruhnya (CSS #sub2) -> tanpa sorot khusus
        outro["kicker_delay"] = 1.3; outro["kicker_top"] = 790; outro["text2"] = kc
    scenes.append(outro)
    # tutup transisi keluar scene sebelum outro
    scenes[-2]["tout"] = "dip"
    scenes[0]["hud_fadeout"] = False

    # ---- pastikan transisi flash tidak di scene pertama; durasi akhir persis
    scenes[-1]["t1"] = DURATION
    for a, b in zip(scenes, scenes[1:]): b["t0"] = a["t1"]

    tl = dict(w=W, h=H, fps=FPS, duration=DURATION, title=title, watermark=watermark, phoneCaller=opts.get("phone_caller", "Ibu"),
              scenes=scenes, warnings=warn, bpm=bool(hud_intro and hud_intro.get("unit", "BPM") == "BPM"))
    tl["sfx"] = build_sfx(tl)
    return tl


# ---------------------------------------------------------------- SFX cues
def build_sfx(tl):
    cues, bed = [], []
    S = tl["scenes"]
    for i, sc in enumerate(S):
        t0, t1 = sc["t0"], sc["t1"]
        flags = sc.get("flags", {})
        side = -1 if i % 2 == 0 else 1
        if i > 0:
            cues.append(dict(t=max(0, t0 - 0.28), type="whoosh", dur=0.75, pan=side, gain=0.85 if sc.get("impact") else 0.55))
        if sc["kind"] != "outro":
            cues.append(dict(t=t0 + 0.06, type="click", gain=0.55))
            cues.append(dict(t=t0 + 0.3, type="tick", gain=0.35))
        if sc.get("impact"):
            cues.append(dict(t=max(0, t0 - 1.1), type="riser", dur=1.1, gain=0.8))
            cues.append(dict(t=t0, type="boom", gain=1.0)); cues.append(dict(t=t0 + 0.05, type="ring", dur=1.6, gain=0.4))
        if flags.get("flat"): cues.append(dict(t=t0 + 0.4, type="flatline", dur=min(1.6, t1 - t0 - 0.6), gain=0.3))
        if flags.get("bright") or sc["set"] == "field": cues.append(dict(t=t0 + 0.2, type="chime", gain=0.5))
        if sc["set"] == "space" and sc["kind"] == "body": cues.append(dict(t=t0 + 0.1, type="shimmer", dur=min(2.5, t1 - t0), gain=0.5))
        if sc["set"] == "phone":
            for k in range(3):
                tt = t0 + 0.45 + k * 1.15
                if tt < t1 - 0.4: cues.append(dict(t=tt, type="ring_phone", gain=0.5))
        if flags.get("cry"): cues.append(dict(t=t0 + 0.2, type="sub_swell", dur=min(3.0, t1 - t0), gain=0.5))
        if sc["kind"] == "outro":
            cues.append(dict(t=t0 - 0.05, type="boom", gain=0.8))
            cues.append(dict(t=t0 + 1.3 + 0.2, type="tick", gain=0.35))
            cues.append(dict(t=t0 + 0.55, type="chime", gain=0.35))
        bed.append(dict(set=sc["sfxset"], t0=t0, t1=t1))
    # heartbeat di hook
    h = S[0]
    if tl.get("bpm") or True:
        hud = h["hud"]
        bpm0, bpm1 = (hud["v0"], hud["v1"]) if hud["mode"] == "int" else (78, 130)
        t = 0.15
        while t < h["t1"] - 0.2:
            frac = t / h["t1"]; bpm = bpm0 + (bpm1 - bpm0) * frac
            cues.append(dict(t=t, type="heartbeat", gain=0.75 + 0.2 * frac))
            t += 60.0 / bpm
    cues.sort(key=lambda c: c["t"])
    return dict(cues=cues, bed=bed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story"); ap.add_argument("--title"); ap.add_argument("--narration"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    opts = {}
    if a.story:
        s = json.load(open(a.story, encoding="utf-8"))
        title, narr = s["title"], s["narration"]
        if isinstance(narr, list): narr = "\n".join(narr)
        opts = {k: v for k, v in s.items() if k not in ("title", "narration")}
    else:
        title, narr = a.title, a.narration
    tl = direct(title, narr, opts)
    json.dump(tl, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for w in tl["warnings"]: print("PERINGATAN:", w, file=sys.stderr)
    print(f"timeline: {len(tl['scenes'])} scene -> {a.out}")
    for s in tl["scenes"]:
        print(f"  {s['t0']:5.1f}-{s['t1']:5.1f} {s['kind']:5s} {s['set']:6s} {s['shot']:6s} | {s['text'][:60]}")


if __name__ == "__main__":
    main()
