# 🎓 TKA Cerdas — Aplikasi Asesmen Literasi & Numerasi SMP

Aplikasi web untuk menyelenggarakan **Tes Kemampuan Akademik (TKA) jenjang SMP**:
siswa mengerjakan ujian online, **nilai keluar otomatis seketika**, guru melihat
**analisis hasil per siswa dan per butir soal**, dan semua rekap bisa **disalin otomatis
ke Google Sheets**.

Dibangun **tanpa dependensi eksternal** — hanya Python standard library + SQLite.
Tidak perlu `pip install` atau `npm install`. Cukup **Python 3.10+**.

---

## 🚀 Cara menjalankan

```bash
cd tka-cerdas
python3 server.py
```

Buka **http://localhost:8000**. Ganti port bila perlu: `PORT=3000 python3 server.py`.

> **Mau langsung online?** Repo ini sudah siap untuk GitHub — lihat **[DEPLOY.md](DEPLOY.md)**
> untuk langkah push ke GitHub, deploy ke Render/Railway/Docker, dan daftar periksa keamanan.

## 🔑 Akun demo

| Peran | Email | Password |
| ----- | ----- | -------- |
| **Guru** | `guru@tka.id` | `guru123` |
| **Siswa** | `siswa@tka.id` | `siswa123` |

Di halaman login ada tombol pintas **Siswa** / **Guru**. Selain itu tersedia 6 siswa
contoh (Aisyah, Bagas, Citra, Dimas, Eka, Fajar — password `siswa123`) yang hasil
ujiannya sudah terisi agar halaman analisis guru langsung berisi data.

Kode akses pendaftaran guru: **`GURU2026`** (bisa diubah di server melalui variabel
lingkungan `GURU_CODE`).

---

## ✨ Fitur

### Untuk siswa
- **Login** dengan akun sendiri (data tiap siswa terpisah)
- **3 paket ujian** bawaan: Hari 1 Matematika & Numerasi, Hari 2 Bahasa Indonesia &
  Literasi Membaca, dan Simulasi Gabungan — total **26 soal** lengkap dengan kunci & pembahasan
- **Timer otomatis** dengan pengumpulan otomatis saat waktu habis
- **Simpan otomatis** setiap jawaban (jika koneksi putus, jawaban tetap tersimpan)
- **Navigasi soal**, tanda soal sudah dijawab, lanjutkan ujian yang tertinggal
- **Nilai keluar seketika** + pembahasan tiap soal untuk belajar
- Bertahan saat halaman di-refresh (sesi & jawaban aman)

### Untuk guru
- **Analisis hasil**: rata-rata, nilai tertinggi/terendah, persentase tuntas (KKM bisa diatur)
- **Distribusi nilai** (0–59, 60–69, 70–79, 80–89, 90–100) dalam grafik
- **Peringkat peserta**; klik nama → lihat jawaban & pembahasan siswa tersebut
- **Analisis butir soal**: persentase benar tiap soal, **klasifikasi otomatis
  mudah/sedang/sulit**, dan **sebaran pilihan jawaban** (mendeteksi pengecoh yang menipu)
- **Bank soal**: seluruh soal, kunci, dan pembahasan
- **Pengaturan**: KKM, nama sekolah, integrasi Google Sheets, unduh CSV, unduh backup

### 📥 Impor soal dari Excel / Word *(baru)*
- Unggah **.xlsx, .docx, .csv, atau .txt** — tanpa perlu aplikasi tambahan
- **Pratinjau dulu** sebelum masuk: jumlah soal, kategori, tingkat, dan kunci ditampilkan
- Kunci jawaban boleh ditulis **huruf (A–E)** atau **nomor (1–5)**
- Baris yang bermasalah **tidak dibatalkan semua** — dilaporkan satu per satu, baris valid tetap masuk
- Tersedia **template Excel** dan **template Word/TXT** yang bisa langsung diunduh dari aplikasi

Kolom yang dikenali: `no, tipe, kategori, tingkat, stimulus, pertanyaan, a, b, c, d, e, kunci, pembahasan, toleransi`.
Tipe `pg` = pilihan ganda (dinilai otomatis), `isian` = jawaban angka (dinilai otomatis dengan toleransi).

### 🗓️ Jadwal ujian & 🔑 token kelas *(baru)*
- Guru menetapkan **rentang waktu** (mulai–selesai) untuk sebuah paket, bisa **per kelas** atau **semua kelas**
- Siswa **hanya bisa memulai** pada rentang itu; di luar rentang muncul pesan yang jelas
- **Token** 6 karakter dibuat otomatis (bisa juga ditentukan sendiri) dan **dapat dibuat ulang** kapan saja
- Jika ujian berjalan melewati waktu selesai jadwal, waktu pengerjaan **otomatis dipotong**
- Kartu paket di beranda siswa menampilkan status jadwal (Sedang berlangsung / Belum mulai / Sudah berakhir)

### 👥 Kelas *(baru)*
- Buat kelas (IX-A, IX-B, …), pindahkan siswa langsung dari tabel
- Analisis hasil bisa **difilter per kelas**, dan rekap PDF dicetak per kelas

### 📄 Laporan PDF *(baru)*
- **PDF per siswa** — identitas, nilai, status tuntas, penguasaan per kategori, rincian jawaban tiap soal
- **PDF rekap kelas** — statistik, distribusi nilai, peringkat, analisis butir soal, dan **catatan butir sulit untuk guru**
- **PDF rekap kehadiran** — siapa yang sudah/belum mengerjakan (lengkap dengan CSV-nya)
- PDF dibuat sendiri oleh aplikasi (tanpa layanan luar), memakai **nama sekolah** dari Pengaturan sebagai kop

### Google Sheets
- Setiap kali siswa mengumpulkan, hasilnya **dikirim otomatis** ke spreadsheet Anda
  (berjalan di latar belakang — siswa tidak menunggu)
- Tombol **"Sinkronkan sekarang"** untuk mengirim ulang semua hasil yang belum terkirim
- Tab tujuan dibuat dan diberi header **otomatis**
- **Riwayat sinkronisasi** tercatat di halaman Pengaturan

---

## ☁️ Menyambungkan Google Sheets (±5 menit, sekali saja)

> **Mengapa perlu langkah ini?** Google mewajibkan setiap aplikasi punya "identitas"
> (service account) sebelum boleh menulis ke spreadsheet Anda. Ini pengaturan satu kali.

### Langkah 1 — Buat project & aktifkan API
1. Buka **[console.cloud.google.com](https://console.cloud.google.com)** → login dengan akun Google Anda
2. Klik **Select a project** → **New Project** → beri nama (mis. `TKA Cerdas`) → **Create**
3. Buka menu **APIs & Services → Library** → cari **Google Sheets API** → klik **Enable**

### Langkah 2 — Buat service account & unduh kuncinya
4. Menu **APIs & Services → Credentials** → **Create Credentials** → **Service account**
5. Beri nama (mis. `tka-sheets`) → **Create and Continue** → **Done**
6. Klik service account yang baru dibuat → tab **Keys** → **Add Key → Create new key**
7. Pilih **JSON** → **Create** → file `.json` otomatis terunduh.
   **Simpan file ini baik-baik — jangan dibagikan ke siapa pun.**
8. Di halaman service account, **salin emailnya** (bentuknya
   `tka-sheets@nama-proyek.iam.gserviceaccount.com`)

### Langkah 3 — Buat spreadsheet & beri akses
9. Buat Google Sheet baru (mis. "Rekap TKA SMP") di [sheets.google.com](https://sheets.google.com)
10. Klik **Share/Bagikan** → tempel **email service account** tadi →
    pilih **Editor** → **Send/Kirim**
    *(tanpa langkah ini Anda akan mendapat error HTTP 403)*
11. Salin **ID spreadsheet** dari alamat URL-nya:
    `docs.google.com/spreadsheets/d/`**`1AbCdEfGh...ID-INI`**`/edit`

### Langkah 4 — Tempel ke aplikasi
12. Masuk sebagai **guru** → menu **Pengaturan**
13. Isi **ID Google Sheet**, nama tab (mis. `Hasil`), dan **tempel seluruh isi file JSON**
    ke kotak "JSON service account"
14. Klik **Tes koneksi** — bila berhasil, judul spreadsheet Anda akan muncul di notifikasi 🎉
15. Klik **Simpan & aktifkan**. Selesai!

Setelah itu, setiap siswa mengumpulkan ujian, barisnya otomatis muncul di sheet.

**Kolom yang dikirim:** Waktu Kumpul, Nama Siswa, Email, Paket, Mapel, Skor, Benar,
Total, Nilai Literasi (%), Nilai Numerasi (%), Durasi (menit), Attempt ID.

> **Catatan keamanan:** kunci JSON disimpan di `tka.db` dan **tidak pernah
> dikirim balik ke browser**. Pada aplikasi yang sudah daring, gunakan HTTPS.
> Bila ingin menghentikan integrasi, hapus akses service account dari spreadsheet.

---

## 🗂️ Struktur proyek

```
tka-cerdas/
├── server.py        # Backend: HTTP server, API, mesin ujian, penilaian, analisis
├── gsheets.py       # Integrasi Google Sheets (JWT RS256 murni Python)
├── office.py        # Pembaca .xlsx / .docx / .csv / .txt (impor soal)
├── pdf.py           # Mesin pembuat PDF murni Python (tanpa library)
├── reports.py       # Tata letak laporan PDF (siswa, kelas, kehadiran)
├── seed_soal.py     # Bank soal bawaan (26 soal + kunci + pembahasan)
├── tka.db           # Database SQLite (dibuat otomatis)
├── public/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── qa/              # Skrip pengujian + tangkapan layar
├── Dockerfile       # Menjalankan di Docker / VPS
├── render.yaml      # Blueprint deploy Render.com
├── Procfile         # Untuk Railway/Heroku-like
├── .env.example     # Contoh variabel lingkungan
├── .gitignore       # Mencegah data & rahasia ikut ter-commit
├── DEPLOY.md        # Panduan deploy ke GitHub + hosting
├── LICENSE          # MIT
└── README.md
```

## ⚙️ Variabel lingkungan (produksi)

| Variabel | Bawaan | Keterangan |
| -------- | ------ | ---------- |
| `PORT` | `8000` | Port server |
| `TKA_SEED_DEMO` | `1` | **Set `0` di produksi** — tanpa akun & data demo |
| `TKA_ADMIN_EMAIL` | `guru@tka.id` | Akun guru pertama |
| `TKA_ADMIN_PASSWORD` | `guru123` | **Wajib diganti** saat publik |
| `GURU_CODE` | `GURU2026` | Kode pendaftaran guru |
| `TKA_KKM` | `70` | Batas ketuntasan awal |
| `TKA_DB_DIR` | folder aplikasi | Lokasi `tka.db` (pakai volume saat Docker) |

> ⚠️ **Sebelum dipakai siswa sungguhan**, jalankan dengan `TKA_SEED_DEMO=0` dan ganti
> `TKA_ADMIN_PASSWORD` serta `GURU_CODE`. Akun demo (`guru123`/`siswa123`) hanya untuk
> mencoba aplikasi, **bukan** untuk produksi.

## 🔐 Keamanan yang sudah diterapkan

| Aspek | Penerapan |
| ----- | --------- |
| Password | PBKDF2-SHA256, 200.000 iterasi, salt unik per pengguna |
| Sesi | Token acak 256-bit, dihapus saat logout |
| **Kunci jawaban** | **Tidak pernah dikirim ke browser saat ujian berlangsung** — hanya muncul setelah dikumpulkan |
| Kepemilikan ujian | Siswa lain tidak bisa membuka, menjawab, atau mengumpulkan ujian orang lain (diuji) |
| Pembatasan peran | Endpoint analisis, bank soal, backup, dan pengaturan hanya untuk guru |
| Waktu ujian | Dihitung di server (bukan di browser), + toleransi 90 detik |
| Input | Validasi panjang, format email, batas ukuran body 512 KB |
| Berkas statis | Proteksi path traversal |
| Backup | Hash password **tidak** ikut diekspor |

## ✅ Hasil pengujian (semua dijalankan, bukan klaim)

| Rangkaian uji | Hasil |
| ------------- | ----- |
| Tanda tangan RS256 vs OpenSSL | **4/4 lulus** — PKCS#1 & PKCS#8 diverifikasi "Verified OK" |
| Unit integrasi Google Sheets | **9/9 lulus** |
| API aplikasi (peran, kebocoran kunci, penilaian, analisis) | **23/23 lulus** |
| Sinkronisasi Sheets dari aplikasi sungguhan | **12/12 lulus** |
| End-to-end browser (Chromium) | **23/23 lulus**, 0 error konsol |
| **API fitur baru** (impor, jadwal, token, PDF) | **36/36 lulus** |
| **Regresi fitur lama** setelah penambahan fitur | **15/15 lulus** |
| **E2E browser fitur baru** | **26/26 lulus**, 0 error konsol |

Menjalankan ulang pengujian:

```bash
python3 qa/test_rsa.py         # verifikasi RSA vs OpenSSL
python3 qa/test_sheets.py      # unit test klien Sheets (server Google tiruan)
python3 qa/test_sync_live.py   # alur Sheets end-to-end
pip install playwright && playwright install chromium
python3 qa/e2e.py              # uji browser (alur dasar)
python3 qa/test_fitur.py       # uji API fitur baru
python3 qa/e2e_fitur.py        # uji browser fitur baru
```

> Catatan: `qa/mock_google.py` adalah **server tiruan** Google untuk pengujian.
> Aplikasi memakai endpoint Google yang sebenarnya (`oauth2.googleapis.com`,
> `sheets.googleapis.com`) saat dijalankan normal.

## 🔌 Ringkasan API

| Method | Endpoint | Akses |
| ------ | -------- | ----- |
| POST | `/api/register` | publik (guru perlu kode) |
| POST | `/api/login` · `/api/logout` | publik / login |
| GET | `/api/me` | login |
| GET | `/api/packages` | login |
| POST | `/api/attempts` | siswa (mulai/lanjutkan) |
| GET | `/api/attempts/:id` | pemilik / guru |
| POST | `/api/attempts/:id/answer` | pemilik |
| POST | `/api/attempts/:id/submit` | pemilik |
| GET | `/api/my-results` | login |
| GET | `/api/analytics?package_id=` | guru |
| GET | `/api/analytics/attempt/:id` | guru |
| GET | `/api/questions?package_id=` | guru |
| GET/POST | `/api/settings` · `/api/settings/test-sheets` | guru |
| POST | `/api/sync/backfill` | guru |
| GET | `/api/export.csv` · `/api/backup` | guru |
| GET/POST/DELETE | `/api/classes` · `/api/classes/assign` | guru (lihat: semua) |
| GET | `/api/students` | guru |
| GET/POST/DELETE | `/api/schedules` · `/api/schedules/:id/token` | guru (lihat: semua) |
| POST | `/api/import/questions` (multipart) | guru |
| GET | `/api/report/student/:id` | pemilik / guru |
| GET | `/api/report/class` · `/api/report/attendance` | guru |
| GET | `/api/attendance.csv` · `/api/template.xlsx` · `/api/template.txt` | guru |

## 💡 Ide pengembangan lanjutan

- **Mode acak soal** untuk mengurangi kerja sama antar siswa
- **Analisis daya beda & validitas butir** (seperti aplikasi analisis butir soal klasik)
- **Impor soal bergambar** (saat ini teks saja; gambar perlu penyimpanan berkas)
- **Ujian susulan** otomatis untuk siswa yang tidak hadir
- **Lupa password** via email
- **Grafik tren antarbulan** dan perbandingan antarkelas

---

Dibuat untuk memudahkan asesmen di sekolah — selamat mengajar! 🍎
