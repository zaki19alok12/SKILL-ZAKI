#!/usr/bin/env python3
"""Sintesis efek suara + ambience dari timeline.json -> audio.wav (stereo 44.1k, 60 detik)."""
import json, sys, wave
import numpy as np
from scipy import signal

SR = 44100


def env_exp(n, tau): return np.exp(-np.arange(n) / (tau * SR))


def lp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "low", fs=SR, output="sos"), x)
def hp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x)
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def noise(n, rng): return rng.standard_normal(n)


def whoosh(dur, rng):
    n = int(dur * SR); x = noise(n, rng)
    out = np.zeros(n); blocks = 16; bl = n // blocks
    for i in range(blocks):  # sapuan band-pass naik lalu turun
        f = 300 * (2 ** (4.2 * np.sin(np.pi * (i + .5) / blocks)))
        seg = x[i * bl:(i + 1) * bl]
        out[i * bl:(i + 1) * bl] = bp(seg, max(120, f * .6), min(16000, f * 1.6), 2)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return out * e * 1.6


def click(rng):
    n = int(.045 * SR); t = np.arange(n) / SR
    x = noise(n, rng) * env_exp(n, .0018) * .7 + np.sin(2 * np.pi * 2300 * t) * env_exp(n, .004) * .6
    return hp(x, 700)


def tick(rng):
    n = int(.03 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1450 * t) * env_exp(n, .003) * .5 + noise(n, rng) * env_exp(n, .001) * .15)


def heartbeat():
    def thump(f0, d, a):
        n = int(d * SR); t = np.arange(n) / SR; f = f0 * (1 + .6 * np.exp(-t * 30))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, d / 4) * a
    n = int(.5 * SR); x = np.zeros(n)
    a = thump(62, .22, 1.0); x[:len(a)] += a
    b = thump(52, .2, .65); s = int(.17 * SR); x[s:s + len(b)] += b
    return lp(x, 260)


def boom(rng):
    n = int(2.4 * SR); t = np.arange(n) / SR
    f = 38 + 90 * np.exp(-t * 7)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, .55)
    x += lp(noise(n, rng), 600) * env_exp(n, .12) * .8
    return np.tanh(x * 1.6) * .9


def riser(dur, rng):
    n = int(dur * SR); t = np.arange(n) / SR; k = t / dur
    nz = noise(n, rng); out = np.zeros(n); blocks = 24; bl = n // blocks
    for i in range(blocks):
        f = 400 * 2 ** (4 * i / blocks)
        out[i * bl:(i + 1) * bl] = lp(nz[i * bl:(i + 1) * bl], min(15000, f), 2)
    tone = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (2.3 * k)) / SR)
    return (out * .9 + tone * .35) * (k ** 2.2)


def ring(dur):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 5100 * t) * .5 + np.sin(2 * np.pi * 5230 * t) * .3) * env_exp(n, dur / 3) * .35


def flatline(dur):
    n = int(max(.3, dur) * SR); t = np.arange(n) / SR
    e = np.minimum(1, t / .02) * np.minimum(1, (t[-1] - t) / .05)
    return np.sin(2 * np.pi * 1000 * t) * e * .5


def chime():
    n = int(3.2 * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for f, a in [(880, 1), (1318, .5), (1760, .35), (2637, .2)]:
        x += np.sin(2 * np.pi * f * t) * a * np.exp(-t * (1.4 + f / 2500))
    return x * .35


def shimmer(dur, rng):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for i in range(16):
        f = rng.uniform(1500, 6000); s = rng.uniform(0, dur * .8); a = rng.uniform(.15, .5)
        m = int(.6 * SR); seg = np.sin(2 * np.pi * f * np.arange(m) / SR) * env_exp(m, .12) * a
        e = min(n, int(s * SR) + m); x[int(s * SR):e] += seg[:e - int(s * SR)]
    return x * .25


def sub_swell(dur):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * 48 * t) * np.sin(np.pi * t / t[-1]) ** 2 * .6


def ring_phone():
    n = int(.9 * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for s in (0, .22):
        m = int(.16 * SR); tt = np.arange(m) / SR
        seg = (np.sin(2 * np.pi * 880 * tt) + np.sin(2 * np.pi * 1040 * tt)) * .35 * np.minimum(1, tt / .005) * np.minimum(1, (tt[-1] - tt) / .01)
        x[int(s * SR):int(s * SR) + m] += seg
    return x * .55


def reverb(x, rng, rt=1.6, mix=.22):
    n = int(rt * SR); ir = noise(n, rng) * env_exp(n, rt / 4.5); ir = lp(ir, 5000)
    ir /= np.abs(ir).sum() ** .5 * 4
    return x * (1 - mix) + signal.fftconvolve(x, ir)[:len(x)] * mix * 6


def bed(kind, dur, rng):
    n = int(dur * SR); t = np.arange(n) / SR
    base = np.zeros(n)
    for f, a in [(55, .5), (82.4, .35), (110.0, .2)]:
        base += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * a * (1 + .15 * np.sin(2 * np.pi * .13 * t + f))
    base += np.sin(2 * np.pi * 65.4 * t) * .2
    if kind == "street":
        base += lp(noise(n, rng), 220) * .55 * (1 + .4 * np.sin(2 * np.pi * .21 * t))
        base += bp(noise(n, rng), 900, 2500) * .02
    elif kind == "room":
        base *= .8
        base += lp(noise(n, rng), 160) * .25
        tk = np.zeros(n)  # jam dinding
        for s in np.arange(.3, dur, 1.0):
            i = int(s * SR); m = min(int(.01 * SR), n - i)
            if m > 0: tk[i:i + m] += np.sin(2 * np.pi * 1800 * np.arange(m) / SR) * env_exp(m, .002) * .06
        base += tk
    elif kind == "phone":
        base += hp(lp(noise(n, rng), 3000), 1500) * .01 + np.sin(2 * np.pi * 120 * t) * .05
    elif kind == "field":
        base += bp(noise(n, rng), 200, 900) * .12 * (1 + .6 * np.sin(2 * np.pi * .17 * t))
    elif kind == "space":
        for f in (220, 329.6, 440):
            base += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * .06 * (1 + .5 * np.sin(2 * np.pi * .09 * t + f))
        base += bp(noise(n, rng), 300, 1200) * .04
    return base


def place(buf, x, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= buf.shape[1]: return
    m = min(len(x), buf.shape[1] - max(i, 0)); s0 = 0
    if i < 0: s0 = -i; i = 0; m = min(len(x) - s0, buf.shape[1])
    seg = x[s0:s0 + m] * gain
    l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + m] += seg * l; buf[1, i:i + m] += seg * r


def main(tl_path, out_path, voice=None):
    tl = json.load(open(tl_path, encoding="utf-8"))
    dur = tl["duration"]; N = int(dur * SR)
    rng = np.random.default_rng(2024)
    music = np.zeros((2, N)); fx = np.zeros((2, N))
    # ambience bed per scene dengan crossfade
    for b in tl["sfx"]["bed"]:
        t0, t1 = max(0, b["t0"] - .5), min(dur, b["t1"] + .5)
        x = bed(b["set"], t1 - t0, rng); n = len(x)
        f = min(int(.5 * SR), n // 2); e = np.ones(n); e[:f] = np.linspace(0, 1, f); e[-f:] = np.linspace(1, 0, f)
        i = int(t0 * SR); m = min(n, N - i)
        music[0, i:i + m] += x[:m] * e[:m] * .5; music[1, i:i + m] += x[:m] * e[:m] * .5
    music = np.stack([reverb(music[0], rng, 2.2, .18), reverb(music[1], rng, 2.4, .18)]) * .55
    for c in tl["sfx"]["cues"]:
        ty, t, g = c["type"], c["t"], c.get("gain", 1.0)
        if ty == "whoosh": place(fx, whoosh(c["dur"], rng), t, g * .8, c.get("pan", 0))
        elif ty == "click": place(fx, click(rng), t, g * .55, 0)
        elif ty == "tick": place(fx, tick(rng), t, g * .5, .2)
        elif ty == "heartbeat": place(fx, heartbeat(), t, g * 1.1, 0)
        elif ty == "boom": place(fx, boom(rng), t, g * .9, 0)
        elif ty == "riser": place(fx, riser(c["dur"], rng), t, g * .55, 0)
        elif ty == "ring": place(fx, ring(c["dur"]), t, g * .35, 0)
        elif ty == "flatline": place(fx, flatline(c["dur"]), t, g * .35, 0)
        elif ty == "chime": place(fx, reverb(chime(), rng, 2.0, .3), t, g * .55, 0)
        elif ty == "shimmer": place(fx, shimmer(c["dur"], rng), t, g * .6, 0)
        elif ty == "sub_swell": place(fx, sub_swell(c["dur"]), t, g * .55, 0)
        elif ty == "ring_phone": place(fx, ring_phone(), t, g * .6, 0)
    mix = music + fx
    if voice:  # voice-over opsional
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", voice, "-ac", "1", "-ar", str(SR), "/tmp/_voice.wav"], check=True)
        w = wave.open("/tmp/_voice.wav"); v = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
        v = v[:N]; duck = np.ones(N)
        env = np.convolve(np.abs(v), np.ones(int(.15 * SR)) / int(.15 * SR), "same")
        duck = 1 - .55 * np.clip(env * 8, 0, 1)
        mix = mix * duck + np.stack([v, v]) * .9
    # fade in/out + soft-limit + normalisasi ke -1.5 dBFS
    fi, fo = int(.15 * SR), int(.9 * SR)
    mix[:, :fi] *= np.linspace(0, 1, fi); mix[:, -fo:] *= np.linspace(1, 0, fo)
    mix = np.tanh(mix * 1.1)
    mix *= 10 ** (-1.5 / 20) / (np.abs(mix).max() + 1e-9)
    pcm = (mix.T * 32767).astype(np.int16)
    w = wave.open(out_path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes()); w.close()
    print(f"audio -> {out_path}  peak={np.abs(mix).max():.3f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
