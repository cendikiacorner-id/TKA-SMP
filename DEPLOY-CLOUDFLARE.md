# ☁️ Deploy TKA Cerdas dengan Cloudflare

Dokumen ini menjelaskan **cara memakai Cloudflare** untuk aplikasi TKA Cerdas beserta
batasannya. Baca bagian **Ringkasan** dulu.

---

## Ringkasan: Cloudflare bisa, tapi bukan sebagai tempat menjalankan aplikasi

| Layanan Cloudflare | Status | Keterangan |
| ------------------ | ------ | ---------- |
| **Cloudflare Tunnel** (`cloudflared`) | ✅ **Disarankan** | Aplikasi tetap berjalan di komputer/server sekolah. Cloudflare membuat alamat `https://...` yang bisa diakses dari mana saja, **tanpa IP publik & tanpa port forwarding**. Cocok untuk sekolah dengan internet biasa/CGNAT. |
| **Cloudflare DNS + Proxy (orange cloud)** | ✅ Bisa | Taruh aplikasi di VPS, arahkan domain lewat Cloudflare. Dapat HTTPS gratis, cache, dan perlindungan DDoS. |
| **Cloudflare Access (Zero Trust)** | ✅ Pelengkap | Mengunci aplikasi di balik login Google/email OTP. Gratis sampai 50 pengguna. |
| **Cloudflare Pages** | ❌ Tidak | Pages hanya menyajikan berkas statis. TKA Cerdas butuh server Python untuk login, menyimpan jawaban, menilai, dan membuat PDF. |
| **Cloudflare Workers** | ❌ Tidak apa adanya | Worker bukan runtime Python, tanpa disk permanen, dan tidak bisa memakai SQLite berbasis berkas. Perlu **tulis ulang total** ke JavaScript + D1. |

> **Kesimpulan:** Cloudflare dipakai sebagai **pintu depan (HTTPS + domain + keamanan)**.
> Mesin aplikasinya tetap Python di komputer/VPS/hosting Python.

---

## Pilihan A — Cloudflare Tunnel (gratis, disarankan untuk sekolah)

Cocok bila Anda punya komputer yang bisa menyala selama jam ujian
(PC lab, laptop bekas, Raspberry Pi, atau server sekolah).

### Alur

```
Siswa/Guru (internet)
        │  https://tka.sekolah.sch.id
        ▼
   Cloudflare (HTTPS, DDoS, Access)
        │  tunnel terenkripsi keluar
        ▼
cloudflared  ──►  python server.py  (di komputer sekolah, port 8000)
```

Tidak perlu membuka port di router, tidak perlu IP publik.

### Langkah 1 — Siapkan aplikasi di komputer sekolah

```bash
cd TKA-SMP
TKA_SEED_DEMO=0 \
TKA_ADMIN_EMAIL=guru@sekolah.sch.id \
TKA_ADMIN_PASSWORD='KataSandiKuat123' \
GURU_CODE='KodeRahasiaSekolah' \
TKA_DB_DIR=/srv/tka-data \
python3 server.py
```

Pastikan bisa dibuka di komputer itu: `http://localhost:8000`.

> **Windows (Command Prompt):**
> ```
> set TKA_SEED_DEMO=0
> set TKA_ADMIN_EMAIL=guru@sekolah.sch.id
> set TKA_ADMIN_PASSWORD=KataSandiKuat123
> set GURU_CODE=KodeRahasiaSekolah
> python server.py
> ```

### Langkah 2 — Pasang `cloudflared`

- **Windows:** unduh `cloudflared-windows-amd64.exe` dari halaman unduhan Cloudflare,
  ganti nama menjadi `cloudflared.exe`.
- **Linux (Debian/Ubuntu):** `sudo apt install cloudflared` (atau pasang berkas `.deb`)
- **macOS:** `brew install cloudflared`

Halaman unduhan resmi:
`https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/`

### Langkah 3 — Coba cepat (tanpa domain, 2 menit)

```bash
cloudflared tunnel --url http://localhost:8000
```

Terminal menampilkan alamat acak seperti `https://kata-acak.trycloudflare.com`.
Buka di HP — aplikasi langsung online dengan HTTPS. Alamat ini **sementara**
(berubah setiap kali dijalankan), hanya untuk uji coba.

### Langkah 4 — Tunnel permanen dengan domain sendiri

Prasyarat: domain sudah didaftarkan di Cloudflare (nameserver mengarah ke Cloudflare).

```bash
cloudflared tunnel login                 # pilih zona domain di browser
cloudflared tunnel create tka-cerdas     # menghasilkan UUID tunnel
cloudflared tunnel route dns tka-cerdas tka.sekolah.sch.id
```

Buat `~/.cloudflared/config.yml`
(**Windows:** `C:\Users\NAMA\.cloudflared\config.yml`):

```yaml
tunnel: <UUID-DARI-LANGKAH-CREATE>
credentials-file: /home/user/.cloudflared/<UUID>.json   # sesuaikan path
ingress:
  - hostname: tka.sekolah.sch.id
    service: http://localhost:8000
  - service: http_status:404        # wajib ada sebagai penutup
```

Jalankan:

```bash
cloudflared tunnel run tka-cerdas
```

Buka `https://tka.sekolah.sch.id` — selesai. 🎉

### Langkah 5 — Jalankan otomatis saat komputer menyala

**Linux (systemd):**
```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```

**Windows:** Command Prompt **sebagai Administrator**
```cmd
cloudflared.exe service install
```
Lalu *Services* → **Cloudflared** → *Startup type: Automatic*.

Aplikasi Python juga perlu jalan otomatis: buat `start-tka.bat` berisi
`python server.py`, lalu masukkan ke *Task Scheduler* (Windows).

---

## Pilihan B — VPS + Cloudflare Proxy (orange cloud)

Cocok bila aplikasi harus online 24 jam tanpa bergantung komputer sekolah.

1. Sewa VPS kecil (1 vCPU / 1 GB RAM cukup).
2. Pasang Docker, lalu:
   ```bash
   git clone https://github.com/cendikiacorner-id/TKA-SMP.git
   cd TKA-SMP
   docker build -t tka-cerdas .
   docker run -d --name tka --restart unless-stopped \
     -p 8000:8000 -v tka-data:/data \
     -e TKA_SEED_DEMO=0 \
     -e TKA_ADMIN_EMAIL=guru@sekolah.sch.id \
     -e TKA_ADMIN_PASSWORD='KataSandiKuat123' \
     -e GURU_CODE='KodeRahasiaSekolah' \
     tka-cerdas
   ```
3. Cloudflare → **DNS** → tambah:
   **Type** `A` · **Name** `tka` · **IPv4** `IP-VPS` · **Proxy status: Proxied (oranye)**
4. **SSL/TLS → Overview** → **Full (strict)** (pasang sertifikat di VPS, mis. Caddy).
5. **Rules → Cache Rules** → **Bypass cache** untuk `/api/*`
   (respons API tidak boleh di-cache).

---

## 🔒 Mengunci akses dengan Cloudflare Access (opsional, gratis ≤50 pengguna)

Berguna agar halaman guru tidak dibuka sembarang orang:

1. Cloudflare Dashboard → **Zero Trust** → **Access → Applications → Add an application**
2. Pilih **Self-hosted**, isi domain `tka.sekolah.sch.id`
3. Kebijakan: **Allow** jika `Email` berakhiran `@sekolah.sch.id` (atau daftar email)
4. Simpan.

Catatan: TKA Cerdas adalah aplikasi satu halaman (SPA). Access mudah dipakai untuk
**seluruh aplikasi**; membatasi hanya menu guru butuh penyesuaian di sisi aplikasi.

---

## ⚠️ Hal yang perlu diperhatikan

| Hal | Penjelasan |
| --- | ---------- |
| **Komputer harus menyala** | Pada Tunnel, bila komputer mati/tertidur, alamat tidak bisa diakses. Matikan mode sleep saat jam ujian. |
| **Internet sekolah** | Jawaban siswa **tersimpan otomatis** tiap soal, jadi koneksi putus sebentar tidak menghilangkan pekerjaan. |
| **Jangan aktifkan "Under Attack Mode"** | Bisa memblokir siswa saat ujian. |
| **Cache** | Jangan cache `/api/*`. Berkas statis boleh. |
| **Batas unggahan** | Cloudflare gratis membatasi 100 MB; unggahan soal maksimal 5 MB — aman. |
| **Basis data** | `tka.db` tetap di komputer/VPS. **Rutin unduh backup** dari menu Pengaturan. |
| **Quick Tunnel** | Hanya untuk uji coba; alamatnya berubah. Ujian sungguhan pakai tunnel permanen. |

---

## Kalau benar-benar ingin sepenuhnya di Cloudflare (Workers + D1)

Secara teknis mungkin, tetapi **bukan sekadar deploy — perlu penulisan ulang**:

| Komponen sekarang | Pengganti di Workers |
| ----------------- | -------------------- |
| `server.py` (http.server) | Worker JavaScript/TypeScript (`fetch` handler) |
| `sqlite3` berbasis berkas | **D1** (SQLite terkelola via binding) |
| Unggah multipart & impor Excel/Word | Parser JS (`xlsx`, `mammoth`) |
| Pembuatan PDF (`pdf.py`) | Library PDF JS (`pdf-lib`) |
| Tanda tangan RSA Sheets | Web Crypto API |
| Sinkronisasi latar belakang (thread) | `ctx.waitUntil()` |

Perkiraan: beberapa hari kerja. **Untuk kebutuhan sekolah, Tunnel atau VPS jauh
lebih hemat waktu.**

---

## Rekomendasi akhir

| Kondisi Anda | Pilihan terbaik |
| ------------ | --------------- |
| Punya PC/server sekolah yang bisa menyala saat ujian | **Cloudflare Tunnel** (gratis) |
| Ingin online 24 jam tanpa bergantung komputer sekolah | **VPS + Cloudflare Proxy** |
| Hanya ingin coba cepat | `cloudflared tunnel --url http://localhost:8000` |
| Butuh sepenuhnya serverless | Tulis ulang ke Workers + D1 (proyek terpisah) |
