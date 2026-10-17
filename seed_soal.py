# -*- coding: utf-8 -*-
"""
Bank soal bawaan TKA Cerdas — jenjang SMP.
Struktur mengikuti format TKA: Hari 1 Matematika & Numerasi,
Hari 2 Bahasa Indonesia & Literasi Membaca, plus satu paket simulasi gabungan.

Tipe soal:
  - "pg"    : pilihan ganda, dinilai otomatis dengan pencocokan kunci
  - "isian" : jawaban angka, dinilai otomatis dengan toleransi (toleransi=0 artinya harus tepat)
"""

PAKET = [
    {
        "kode": "NUM-SMP-01",
        "judul": "Hari 1 — Matematika & Numerasi",
        "mapel": "Matematika",
        "kategori": "numerasi",
        "deskripsi": "Paket latihan numerasi setara TKA SMP hari pertama. 8 soal, 60 menit.",
        "durasi": 60,
        "urutan": 1,
    },
    {
        "kode": "LIT-SMP-01",
        "judul": "Hari 2 — Bahasa Indonesia & Literasi Membaca",
        "mapel": "Bahasa Indonesia",
        "kategori": "literasi",
        "deskripsi": "Paket latihan literasi membaca setara TKA SMP hari kedua. 8 soal, 75 menit.",
        "durasi": 75,
        "urutan": 2,
    },
    {
        "kode": "TRY-SMP-01",
        "judul": "Simulasi Gabungan (Tryout)",
        "mapel": "Gabungan",
        "kategori": "campuran",
        "deskripsi": "Simulasi singkat berisi literasi dan numerasi. 10 soal, 50 menit.",
        "durasi": 50,
        "urutan": 3,
    },
]

# ---------------------------------------------------------------------------
# SOAL — paket 1: Matematika & Numerasi
# ---------------------------------------------------------------------------
TEKS_PLASTIK = """Setiap tahun, jutaan ton plastik berakhir di laut. Plastik tidak mudah terurai; sinar matahari dan gelombang justru memecahnya menjadi serpihan sangat kecil yang disebut mikroplastik. Serpihan ini tidak hilang, melainkan tersebar di air dan masuk ke tubuh ikan, kerang, serta hewan laut lain. Ketika manusia memakan hasil laut tersebut, mikroplastik dapat ikut masuk ke dalam tubuh kita.

Beberapa negara mulai membatasi penggunaan kantong plastik sekali pakai. Namun, kebijakan itu belum cukup jika perilaku masyarakat tidak berubah. Membawa tas belanja sendiri, menolak sedotan plastik, dan memilah sampah adalah langkah kecil yang berdampak besar jika dilakukan bersama-sama. Laut yang sehat bukan hanya tanggung jawab pemerintah, melainkan tanggung jawab kita semua."""

TEKS_SEPATU = """Rani memandang sepatu hitam di depan kelas. Solnya sudah mulai terbuka, tetapi ia tetap memakainya setiap hari. Pagi itu, Bu Inah, guru bahasa Indonesianya, berhenti di samping bangku Rani.

"Sepatumu rusak, Ran," katanya pelan. Rani hanya tersenyum. Ia tahu betul: uang tabungan ibunya harus dipakai untuk obat adiknya.

Sore harinya, Bu Inah menyerahkan sekotak sepatu baru. Rani menggeleng, tetapi Bu Inah berkata, "Anggap saja ini hadiah karena kamu juara menulis." Rani memeluk gurunya tanpa bisa berkata apa-apa."""

TEKS_SARAPAN = """Sarapan sering dianggap sepele, padahal berperan penting bagi pelajar. Setelah delapan jam tidur, tubuh membutuhkan energi untuk berpikir dan beraktivitas. Penelitian menunjukkan bahwa pelajar yang sarapan memiliki konsentrasi lebih baik dibandingkan pelajar yang melewatkannya.

Sarapan tidak harus mahal: nasi, telur, dan buah lokal sudah cukup memenuhi kebutuhan gizi pagi. Yang terpenting adalah membiasakannya setiap hari."""

PAKET_SOAL = {
    "NUM-SMP-01": [
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "mudah",
            "stimulus": "",
            "pertanyaan": "Hasil dari 2/3 + (3/4 × 1/2) adalah ....",
            "opsi": ["5/6", "1 1/24", "1 1/12", "3/4"],
            "kunci": "B",
            "pembahasan": "Kerjakan perkalian lebih dahulu: 3/4 × 1/2 = 3/8. Lalu 2/3 + 3/8 = 16/24 + 9/24 = 25/24 = 1 1/24.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Harga sebuah tas Rp250.000. Toko memberi diskon 20%, lalu pada harga setelah diskon masih ada potongan tambahan 10%. Harga akhir tas tersebut adalah ....",
            "opsi": ["Rp175.000", "Rp180.000", "Rp190.000", "Rp200.000"],
            "kunci": "B",
            "pembahasan": "Setelah diskon 20%: 250.000 × 0,8 = 200.000. Diskon tambahan 10% dihitung dari 200.000: 200.000 × 0,9 = 180.000. Diskon bertingkat tidak dijumlahkan menjadi 30%.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Jika 3x − 7 = 2x + 5, maka nilai x adalah ....",
            "opsi": ["4", "6", "12", "14"],
            "kunci": "C",
            "pembahasan": "3x − 7 = 2x + 5 → 3x − 2x = 5 + 7 → x = 12.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Sebuah segitiga siku-siku memiliki panjang dua sisi tegak 9 cm dan 12 cm. Panjang sisi miringnya adalah ....",
            "opsi": ["13 cm", "14 cm", "15 cm", "21 cm"],
            "kunci": "C",
            "pembahasan": "Teorema Pythagoras: c² = 9² + 12² = 81 + 144 = 225, sehingga c = √225 = 15 cm.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "mudah",
            "stimulus": "",
            "pertanyaan": "Nilai ulangan tujuh siswa adalah 7, 8, 8, 9, 9, 9, 10. Median dari data tersebut adalah ....",
            "opsi": ["8", "8,5", "9", "9,5"],
            "kunci": "C",
            "pembahasan": "Data sudah berurutan dan jumlahnya ganjil (7 data), sehingga median adalah data keempat, yaitu 9.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Sebuah kantong berisi 4 kelereng merah dan 6 kelereng biru. Satu kelereng diambil secara acak. Peluang terambil kelereng merah adalah ....",
            "opsi": ["1/5", "2/5", "3/5", "2/3"],
            "kunci": "B",
            "pembahasan": "Jumlah kelereng = 4 + 6 = 10. Peluang merah = 4/10 = 2/5.",
        },
        {
            "tipe": "isian", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Jarak dua kota pada peta berskala 1 : 500.000 adalah 6 cm. Jarak sebenarnya kedua kota tersebut adalah ... km. (Tulis angka saja, tanpa satuan.)",
            "opsi": [], "kunci": "30", "toleransi": 0.0,
            "pembahasan": "Jarak sebenarnya = 6 cm × 500.000 = 3.000.000 cm = 30 km.",
        },
        {
            "tipe": "isian", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Seorang pedagang membeli barang seharga Rp80.000, lalu menjualnya Rp100.000. Persentase keuntungannya adalah ... %. (Tulis angka saja.)",
            "opsi": [], "kunci": "25", "toleransi": 0.0,
            "pembahasan": "Untung = 100.000 − 80.000 = 20.000. Persentase untung = 20.000/80.000 × 100% = 25%.",
        },
    ],
    # -----------------------------------------------------------------------
    # SOAL — paket 2: Bahasa Indonesia & Literasi Membaca
    # -----------------------------------------------------------------------
    "LIT-SMP-01": [
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_PLASTIK,
            "pertanyaan": "Ide pokok paragraf pertama pada teks tersebut adalah ....",
            "opsi": [
                "Ikan dan kerang mengandung banyak plastik",
                "Plastik di laut terurai menjadi mikroplastik dan dapat masuk ke rantai makanan",
                "Sinar matahari memecah plastik menjadi kantong plastik",
                "Manusia gemar memakan hasil laut",
            ],
            "kunci": "B",
            "pembahasan": "Paragraf pertama menjelaskan proses: plastik di laut dipecah menjadi mikroplastik, masuk ke tubuh hewan laut, lalu dapat masuk ke tubuh manusia. Pilihan A dan C hanya rincian, sedangkan D tidak dibahas.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "mudah",
            "stimulus": TEKS_PLASTIK,
            "pertanyaan": "Makna kata \"mikroplastik\" pada teks tersebut adalah ....",
            "opsi": [
                "Plastik yang mudah terurai oleh air laut",
                "Serpihan plastik berukuran sangat kecil",
                "Hewan laut yang memakan sampah plastik",
                "Limbah pabrik yang berbahan dasar plastik",
            ],
            "kunci": "B",
            "pembahasan": "Teks menyebut plastik \"dipecah menjadi serpihan sangat kecil yang disebut mikroplastik\". Jadi mikroplastik adalah serpihan plastik berukuran sangat kecil.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sulit",
            "stimulus": TEKS_PLASTIK,
            "pertanyaan": "Simpulan yang sesuai dengan isi teks tersebut adalah ....",
            "opsi": [
                "Kebijakan pemerintah sudah cukup untuk mengatasi sampah plastik",
                "Mikroplastik hanya mencemari air laut dan tidak sampai ke manusia",
                "Perubahan perilaku masyarakat diperlukan agar sampah plastik berkurang",
                "Kantong plastik sekali pakai mudah terurai di laut",
            ],
            "kunci": "C",
            "pembahasan": "Teks menegaskan kebijakan saja belum cukup jika perilaku masyarakat tidak berubah. Justru perubahan perilaku (membawa tas sendiri, memilah sampah) yang ditekankan penulis.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_PLASTIK,
            "pertanyaan": "Tujuan penulis dalam teks tersebut adalah ....",
            "opsi": [
                "Menghibur pembaca dengan cerita tentang laut",
                "Mengajak pembaca berperilaku ramah lingkungan",
                "Menjelaskan cara memproduksi kantong plastik",
                "Menceritakan pengalaman pribadi penulis di pantai",
            ],
            "kunci": "B",
            "pembahasan": "Kalimat penutup \"bukan hanya tanggung jawab pemerintah, melainkan tanggung jawab kita semua\" menunjukkan ajakan kepada pembaca untuk berperilaku ramah lingkungan.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_SEPATU,
            "pertanyaan": "Watak Rani berdasarkan cerpen tersebut adalah ....",
            "opsi": ["pembohong", "mudah menyerah", "sabar dan tidak mengeluh", "sombong"],
            "kunci": "C",
            "pembahasan": "Rani tetap memakai sepatu yang solnya terbuka dan hanya tersenyum ketika ditegur. Ia memilih tidak mengeluh karena tahu uang ibunya dibutuhkan untuk obat adiknya.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sulit",
            "stimulus": TEKS_SEPATU,
            "pertanyaan": "Sikap Rani menolak sepatu pemberian Bu Inah menunjukkan bahwa Rani ....",
            "opsi": [
                "tidak menyukai model sepatu itu",
                "malu kepada teman-temannya",
                "tidak ingin merepotkan atau memberatkan orang lain",
                "marah kepada gurunya",
            ],
            "kunci": "C",
            "pembahasan": "Penolakan Rani terjadi karena ia tahu Bu Inah sudah berbaik hati; Rani tidak ingin memberatkan orang lain. Hal ini diperkuat dengan reaksi terakhirnya: memeluk gurunya dengan haru.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_SEPATU,
            "pertanyaan": "Amanat yang paling tepat dari cerpen tersebut adalah ....",
            "opsi": [
                "Rajinlah menabung agar dapat membeli sepatu baru",
                "Kepedulian terhadap sesama dapat meringankan beban orang lain",
                "Guru harus selalu memberi hadiah kepada muridnya",
                "Jangan memakai sepatu yang sudah rusak ke sekolah",
            ],
            "kunci": "B",
            "pembahasan": "Cerpen menampilkan kepedulian Bu Inah yang meringankan beban Rani. Amanat yang paling sesuai adalah kepedulian terhadap sesama.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "mudah",
            "stimulus": "",
            "pertanyaan": "Kalimat berikut yang menggunakan ejaan dengan tepat adalah ....",
            "opsi": [
                "Bu Inah menyerahkan sekotak sepatu baru kepada Rani di kelas.",
                "Bu inah menyerahkan sekotak sepatu baru kepada rani di kelas.",
                "bu Inah menyerahkan sekotak sepatu baru kepada Rani di kelas.",
                "Bu Inah menyerahkan sekotak sepatu baru kepada Rani di Kelas.",
            ],
            "kunci": "A",
            "pembahasan": "Huruf pertama awal kalimat dan nama orang (Bu Inah, Rani) ditulis dengan huruf kapital, sedangkan kata benda umum (kelas) ditulis dengan huruf kecil.",
        },
    ],
    # -----------------------------------------------------------------------
    # SOAL — paket 3: Simulasi gabungan
    # -----------------------------------------------------------------------
    "TRY-SMP-01": [
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "mudah",
            "stimulus": TEKS_SARAPAN,
            "pertanyaan": "Ide pokok teks tersebut adalah ....",
            "opsi": [
                "Sarapan yang mahal lebih bergizi",
                "Sarapan penting bagi pelajar dan cukup dengan makanan sederhana",
                "Pelajar harus tidur delapan jam setiap malam",
                "Penelitian tentang gizi hanya berlaku di kota besar",
            ],
            "kunci": "B",
            "pembahasan": "Teks membahas pentingnya sarapan bagi pelajar sekaligus menegaskan sarapan tidak harus mahal.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_SARAPAN,
            "pertanyaan": "Informasi yang didukung oleh data penelitian dalam teks tersebut adalah ....",
            "opsi": [
                "Pelajar yang sarapan memiliki konsentrasi lebih baik",
                "Nasi dan telur paling mahal di Indonesia",
                "Sarapan hanya perlu dilakukan pada hari ujian",
                "Semua pelajar Indonesia melewatkan sarapan",
            ],
            "kunci": "A",
            "pembahasan": "Teks menyebut penelitian menunjukkan pelajar yang sarapan memiliki konsentrasi lebih baik dibandingkan yang melewatkannya.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": TEKS_SARAPAN,
            "pertanyaan": "Simpulan yang tepat berdasarkan teks tersebut adalah ....",
            "opsi": [
                "Sarapan mahal menjamin prestasi belajar",
                "Makanan sederhana seperti nasi, telur, dan buah dapat memenuhi gizi sarapan",
                "Melewatkan sarapan tidak berpengaruh pada konsentrasi",
                "Hanya buah lokal yang boleh dimakan saat sarapan",
            ],
            "kunci": "B",
            "pembahasan": "Teks menyatakan nasi, telur, dan buah lokal sudah cukup memenuhi kebutuhan gizi pagi.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "mudah",
            "stimulus": TEKS_SARAPAN,
            "pertanyaan": "Kata \"sepele\" pada kalimat pertama bermakna ....",
            "opsi": ["penting", "mahal", "remeh atau tidak penting", "sulit dilakukan"],
            "kunci": "C",
            "pembahasan": "Konstruksi \"sering dianggap sepele, padahal berperan penting\" menunjukkan bahwa sepele bermakna remeh atau tidak penting.",
        },
        {
            "tipe": "pg", "kategori": "literasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Kalimat yang paling efektif dan sesuai ejaan adalah ....",
            "opsi": [
                "Para siswa-siswa berkumpul di lapangan untuk mengikuti upacara.",
                "Para siswa berkumpul di lapangan untuk mengikuti upacara.",
                "Para siswa berkumpul dilapangan untuk mengikuti upacara.",
                "Para siswa berkumpul di lapangan guna untuk mengikuti upacara.",
            ],
            "kunci": "B",
            "pembahasan": "Pilihan A salah karena \"para\" dan \"siswa-siswa\" bermakna jamak ganda; C salah karena \"di lapangan\" harus dipisah; D salah karena \"guna untuk\" mubazir.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "mudah",
            "stimulus": "",
            "pertanyaan": "25% dari 480 adalah ....",
            "opsi": ["100", "110", "120", "130"],
            "kunci": "C",
            "pembahasan": "25% = 1/4, sehingga 480 × 1/4 = 120.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Jika 4x − 5 = 3x + 2, maka nilai x adalah ....",
            "opsi": ["3", "5", "7", "9"],
            "kunci": "C",
            "pembahasan": "4x − 5 = 3x + 2 → 4x − 3x = 2 + 5 → x = 7.",
        },
        {
            "tipe": "pg", "kategori": "numerasi", "tingkat": "mudah",
            "stimulus": "",
            "pertanyaan": "Rata-rata dari bilangan 6, 7, 8, 9, dan 10 adalah ....",
            "opsi": ["7", "7,5", "8", "8,5"],
            "kunci": "C",
            "pembahasan": "Jumlah = 6 + 7 + 8 + 9 + 10 = 40. Banyak data = 5. Rata-rata = 40 ÷ 5 = 8.",
        },
        {
            "tipe": "isian", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Sebuah persegi panjang memiliki panjang 12 cm dan lebar 5 cm. Kelilingnya adalah ... cm. (Tulis angka saja.)",
            "opsi": [], "kunci": "34", "toleransi": 0.0,
            "pembahasan": "Keliling = 2 × (panjang + lebar) = 2 × (12 + 5) = 2 × 17 = 34 cm.",
        },
        {
            "tipe": "isian", "kategori": "numerasi", "tingkat": "sedang",
            "stimulus": "",
            "pertanyaan": "Sebuah baju berharga Rp250.000 mendapat diskon 20%. Harga baju setelah diskon adalah Rp ... (Tulis angka tanpa titik, misalnya 250000.)",
            "opsi": [], "kunci": "200000", "toleransi": 0.0,
            "pembahasan": "Diskon = 20% × 250.000 = 50.000. Harga akhir = 250.000 − 50.000 = 200.000.",
        },
    ],
}
