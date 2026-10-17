# 🚀 Panduan Deploy TKA Cerdas

Dokumen ini menjelaskan cara menaikkan aplikasi ke GitHub, lalu menjalankannya di internet.

> **Penting dipahami lebih dulu:** GitHub **hanya menyimpan kode**. GitHub Pages hanya bisa
> menyajikan berkas statis (HTML/CSS/JS), sedangkan TKA Cerdas membutuhkan **server Python**
> untuk login, menyimpan jawaban, dan menilai. Jadi setelah kode ada di GitHub, aplikasi
> dijalankan di layanan hosting yang mendukung Python (Render, Railway, Fly.io, atau VPS).
> Semua langkah di bawah **gratis** untuk skala sekolah kecil (Render paket free).

---

## 1. Push ke GitHub

### Cara A — lewat terminal (disarankan)

```bash
# di dalam folder hasil ekstrak ZIP
cd tka-cerdas
git init
git add .
git commit -m "TKA Cerdas: aplikasi asesmen literasi & numerasi SMP"

# buat repo baru (kosong, tanpa README) di github.com, lalu:
git branch -M main
git remote add origin https://github.com/USERNAME/tka-cerdas.git
git push -u origin main
```

### Cara B — lewat web GitHub

1. Buka **github.com → New repository** → beri nama `tka-cerdas` → **Create**
2. Klik **uploading an existing file** → tarik **seluruh isi** folder (bukan file ZIP-nya)
3. Tulis pesan commit → **Commit changes**

> Berkas `.gitignore` sudah disiapkan, sehingga `tka.db` (data siswa), cache Python,
> dan berkas kredensial **tidak akan ikut terunggah**. Ini memang yang diinginkan —
> basis data dibuat otomatis saat server pertama kali dijalankan.

---

## 2. Jalankan di internet

### Pilihan 1 — Render.com (gratis, paling mudah)

1. Daftar di [render.com](https://render.com) memakai akun GitHub
2. **New → Web Service** → pilih repo `tka-cerdas`
3. Isi:
   - **Runtime**: Python 3
   - **Build Command**: *(kosongkan)* — tidak perlu dependensi
   - **Start Command**: `python server.py`
   - **Health Check Path**: `/api/health`
4. Pada **Environment**, tambahkan variabel (lihat tabel di bawah)
5. **Create Web Service** — tunggu ±1 menit, aplikasi dapat alamat `https://nama-anda.onrender.com`

> Catatan paket gratis Render: server "tidur" setelah tidak dipakai dan butuh ±30 detik
> untuk bangun pertama kali. Untuk ujian serentak, gunakan paket berbayar termurah.

Berkas `render.yaml` sudah tersedia bila ingin memakai **Blueprint** (deploy otomatis,
termasuk disk permanen 1 GB untuk basis data).

### Pilihan 2 — Railway / Fly.io

- **Railway**: New Project → Deploy from GitHub repo → tambahkan variabel lingkungan.
  Railway mendeteksi Python otomatis (ada `Procfile`).
- **Fly.io**: `fly launch` di folder proyek (sudah ada `Dockerfile`), lalu
  `fly volumes create data --size 1` dan pasang ke `/data`.

### Pilihan 3 — Docker (VPS sendiri / sekolah)

```bash
docker build -t tka-cerdas .
docker run -d --name tka \
  -p 8000:8000 \
  -v tka-data:/data \
  -e TKA_SEED_DEMO=0 \
  -e TKA_ADMIN_EMAIL=guru@sekolah.sch.id \
  -e TKA_ADMIN_PASSWORD='KataSandiKuat123' \
  -e GURU_CODE='KodeRahasiaSekolah' \
  tka-cerdas
```

Buka `http://IP-SERVER:8000`. Untuk HTTPS, letakkan di belakang **Caddy** atau **Nginx**.

---

## 3. Variabel lingkungan

| Variabel | Wajib? | Contoh | Keterangan |
| -------- | ------ | ------ | ---------- |
| `PORT` | tidak | `8000` | Biasanya diisi otomatis oleh platform |
| `TKA_SEED_DEMO` | **ya (produksi)** | `0` | `0` = tanpa akun & data demo. **Wajib `0` saat publik** |
| `TKA_ADMIN_EMAIL` | ya | `guru@sekolah.sch.id` | Akun guru/admin pertama (dibuat otomatis) |
| `TKA_ADMIN_PASSWORD` | ya | *(kata sandi kuat)* | Ganti dari bawaan `guru123` |
| `TKA_ADMIN_NAME` | tidak | `Bu Siti` | Nama yang ditampilkan |
| `GURU_CODE` | ya | `KodeRahasiaSekolah` | Kode untuk mendaftar sebagai guru |
| `TKA_KKM` | tidak | `70` | Batas ketuntasan awal |
| `TKA_DB_DIR` | tidak | `/data` | Folder penyimpanan `tka.db` (pakai volume) |

> ⚠️ **Jangan pernah** menaruh kunci JSON service account Google di dalam kode atau repo.
> Tempelkan lewat halaman **Pengaturan** di aplikasi — nilainya disimpan di basis data server.

---

## 4. Daftar periksa sebelum dipakai siswa sungguhan

- [ ] `TKA_SEED_DEMO=0` (tidak ada akun demo `guru123` / `siswa123`)
- [ ] `TKA_ADMIN_PASSWORD` dan `GURU_CODE` sudah diganti dengan yang kuat
- [ ] Aplikasi diakses lewat **HTTPS** (wajib, agar token login tidak bisa disadap)
- [ ] Volume/disk permanen terpasang agar `tka.db` tidak hilang saat redeploy
- [ ] **Backup rutin**: Pengaturan → *Unduh backup .json* (jadwalkan mingguan)
- [ ] Nama sekolah diisi agar kop laporan PDF benar
- [ ] Uji satu kali: guru membuat jadwal + token, satu siswa mengerjakan, cek nilai & PDF
- [ ] Google Sheets (opsional) sudah diuji dengan tombol **Tes koneksi**

---

## 5. Catatan penting tentang data

SQLite menyimpan seluruh data pada **satu berkas** (`tka.db`). Konsekuensinya:

- Pada platform dengan penyimpanan sementara (mis. Render free tanpa disk), **data hilang
  setiap kali aplikasi di-deploy ulang**. Pasang disk/volume, atau rutin mengunduh backup.
- Untuk sekolah dengan ratusan siswa yang mengerjakan bersamaan, sebaiknya jalankan di
  VPS dengan disk permanen, atau hubungi pengembang untuk migrasi ke PostgreSQL.

---

## 6. Memperbarui aplikasi

```bash
git add .
git commit -m "Perbaikan: ..."
git push
```

Render/Railway akan melakukan deploy ulang otomatis. Data tetap aman **jika** disk
permanen terpasang.
