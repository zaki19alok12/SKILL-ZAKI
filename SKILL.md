---
name: animasindo-story-video
description: Buat video cerita vertikal 9:16 berdurasi tepat 60 detik bergaya 3D voxel sinematik (HUD counter waktu, subtitle serif dengan kata sorot, kamera dramatis, SFX whoosh/click/heartbeat) dengan watermark "animasindo". Pengguna cukup memberi JUDUL + NARASI; sisanya dibuat otomatis. Gunakan saat user minta "buat video animasindo", "template video cerita", atau memberi judul+narasi untuk dijadikan video.
---

# Animasindo Story Video (template 60 detik)

Input pengguna hanya **judul** dan **narasi**. Semua hal lain (adegan, kamera, karakter, counter, transisi, SFX, watermark, QA) dikerjakan pipeline di folder skill ini.

## Cara pakai

1. Ambil `title` dan `narration` dari user. Jangan minta hal lain; cukup tanya bila narasi kurang dari 4 kalimat.
2. Cek panjang narasi: kalimat pembuka (hook) + 10–14 kalimat pendek lain, total sekitar 450–650 karakter. Kalimat terakhir yang berupa pertanyaan otomatis menjadi penutup emas di outro. Bila terlalu panjang, persingkat sebelum render (build akan berhenti dengan peringatan).
3. Tulis `story.json`:
   ```json
   {"title": "Pesan Terakhirmu",
    "narration": ["Kalimat hook (pertanyaan/pernyataan kuat).", "Kalimat 2.", "...", "Pertanyaan penutup?"]}
   ```
   - `*kata*` di dalam kalimat = kata yang disorot (hook: merah, lainnya: emas). Tanpa tanda bintang, kata emosional dipilih otomatis.
   - Awalan `[1:20:12 JAM]` di depan kalimat = memaksa isi counter HUD untuk adegan itu (unit: DETIK, MENIT, JAM, HARI, BULAN, TAHUN, BPM).
   - Opsional: `"intro": {"label":"Detak Jantung","from":82,"to":160,"unit":"BPM"}` untuk HUD pembuka berupa angka naik; `"phone_caller":"Ibu"`; `"prefix":"SEJAK"`; `"cta":"teks penutup"`.
4. Render (jalankan dari folder skill; ±7 menit untuk 1800 frame, jalankan di latar belakang lalu pantau log):
   ```bash
   python3 scripts/build.py --story story.json --out /path/video.mp4
   # cek cepat 12 detik pertama:  tambahkan --preview
   # voice-over opsional:        --voice narasi.mp3  (musik otomatis di-duck)
   ```
   Build otomatis menjalankan `qa.py`. **Jangan serahkan video bila QA belum "LULUS".**
5. Cek visual sendiri sebelum kirim: ambil beberapa frame (`node scripts/frames.js timeline.json outdir 2 9 20 33 47 57`) dan lihat. Kirim file dengan SendUserFile.

## Spesifikasi template (jangan diubah antar video)

- 720x1280, 30 fps, H.264 + AAC, **tepat 60,0 detik**.
- Struktur: hook (adegan POV jalan malam, 4–6 dtk, teks putih di atas dengan kata merah) → 10–14 adegan isi → outro bintang 5 dtk (hook diulang + pertanyaan emas) supaya video bisa di-loop.
- HUD kiri atas: label kecil huruf kapital berspasi `SEJAK <JUDUL>`, angka serif besar, unit kecil. Counter naik skala logaritmik dari detik → menit → jam → hari → tahun mengikuti adegan.
- Subtitle: serif italic putih, kata sorot emas `#f2b84b` (hook merah `#e5484d`), muncul kata demi kata (fade + blur), posisi 62% tinggi layar.
- Watermark `animasindo` tetap di bawah tengah selama seluruh video (juga saat transisi).
- Dunia 3D voxel asli buatan sendiri (karakter balok: pria, ibu berhijab, anak, lansia berkacamata, petugas berompi; wajah piksel dengan emosi netral/sedih/kaget/menangis/senyum): set `street` (jalan malam, lampu, mobil), `room` (ruang hangat, kue ulang tahun, lilin), `phone` (layar panggilan "Ibu memanggil"), `field` (kabut putih, siluet), `space` (bintang).
- Kamera: drive (POV), wide, medium, close, low (dutch angle), orbit, pull-out, side, top, tilt, float; handheld shake halus; punch-in + flash putih pada adegan benturan; retakan kaca muncul setelah benturan.
- Transisi: dip-to-black 0,4 dtk, flash di momen kejutan.
- SFX (sintesis, tanpa internet): whoosh tiap pergantian adegan, click + tick tiap HUD/subtitle, heartbeat di hook, riser + boom + dengung telinga saat benturan, nada flatline, chime saat cahaya, dering telepon, shimmer ruang angkasa, ambience per set + pad drone.

## Aturan agar konsisten dan bebas bug

- Satu kali input → satu keluaran deterministik (tidak ada Math.random/Date di engine; semua seed tetap).
- Jangan edit `engine.html`/`director.py` untuk satu video saja. Bila perlu perubahan permanen, ubah template lalu render ulang contoh `examples/story.example.json` dan pastikan QA lulus.
- QA (`scripts/qa.py`) memeriksa: durasi 60 dtk, 720x1280, 30 fps, ada audio, tanpa clipping/senyap, watermark terlihat tiap detik, subtitle terlihat tiap adegan, subtitle tidak keluar layar/tabrak HUD/watermark/maks 4 baris, tidak ada frame hitam atau beku di luar transisi, tidak ada error JS/WebGL.
- Karakter dan dunia adalah desain orisinal. Jangan meminta/menggambar karakter berhak cipta atau meniru game tertentu.

## Batasan

- Lingkungan tanpa internet tidak punya TTS; suara narasi hanya lewat `--voice file`. Tanpa voice, narasi tampil sebagai subtitle + SFX + ambience.
- Butuh: python3 (numpy, scipy, Pillow), node + playwright (Chromium), ffmpeg. Tidak perlu memasang paket apa pun.
- Font memakai yang terpasang (Lora, GFS Baskerville, Inter). Jika ingin Cormorant/Playfair, taruh font di sistem sebelum render.

## Isi folder

`scripts/director.py` (judul+narasi → timeline), `scripts/engine.html` (renderer WebGL + HUD + subtitle), `scripts/render.js`, `scripts/sfx.py`, `scripts/build.py`, `scripts/qa.py`, `scripts/frames.js` (debug frame), `examples/story.example.json`.
