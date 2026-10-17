# -*- coding: utf-8 -*-
"""
reports.py — Laporan PDF hasil TKA (per siswa & rekapitulasi kelas)
dibangun di atas pdf.py tanpa dependensi eksternal.
"""
from datetime import datetime
from pdf import PDF

BRAND = (91, 75, 255)
BRAND_DARK = (60, 48, 190)
INK = (34, 29, 59)
MUTED = (123, 117, 148)
LINE = (232, 228, 246)
SOFT = (248, 247, 255)
GREEN = (18, 184, 134)
AMBER = (230, 150, 20)
RED = (228, 62, 87)
WHITE = (255, 255, 255)

MARGIN = 40
W = 595.276
H = 841.890
CONTENT_W = W - MARGIN * 2


def _fmt_date(iso):
    if not iso:
        return "-"
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                 "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        return f"{d.day} {bulan[d.month - 1]} {d.year}, {d.hour:02d}.{d.minute:02d} WIB"
    except (ValueError, TypeError):
        return str(iso)


def _durasi(start, end):
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return f"{max(1, round((b - a).total_seconds() / 60))} menit"
    except (ValueError, TypeError):
        return "-"


class Report:
    """Pembungkus tata letak dengan pemenggalan halaman otomatis."""

    def __init__(self, title, subtitle, school_name="SMP"):
        self.pdf = PDF()
        self.title = title
        self.subtitle = subtitle
        self.school = school_name
        self.y = 0
        self._header()

    # -- halaman ---------------------------------------------------------
    def _header(self):
        p = self.pdf
        p.rect(0, 0, W, 74, fill=BRAND)
        p.rect(0, 74, W, 4, fill=(255, 176, 32))
        p.text(MARGIN, 18, "TKA CERDAS", 16, bold=True, color=WHITE)
        p.text(MARGIN, 40, self.school or "SMP", 9.5, color=(226, 220, 255))
        p.text(MARGIN, 18, self.title, 13, bold=True, color=WHITE, align="right", width=CONTENT_W)
        p.text(MARGIN, 38, self.subtitle, 8.5, color=(226, 220, 255), align="right", width=CONTENT_W)
        self.y = 100

    def new_page(self):
        self.pdf.new_page()
        self._header()

    def need(self, h):
        if self.y + h > H - 52:
            self.new_page()

    def finish(self) -> bytes:
        total = len(self.pdf.pages)
        for i, page in enumerate(self.pdf.pages, start=1):
            p = self.pdf
            p.rect(MARGIN, H - 38, CONTENT_W, 0.7, fill=LINE)
            p.text(MARGIN, H - 30, "Dicetak dari TKA Cerdas", 7.5, color=MUTED)
            p.text(MARGIN, H - 30, f"Halaman {i} dari {total}", 7.5, color=MUTED,
                   align="right", width=CONTENT_W)
        return self.pdf.output()

    # -- komponen --------------------------------------------------------
    def section(self, text):
        self.need(34)
        self.pdf.text(MARGIN, self.y + 12, text, 11.5, bold=True, color=INK)
        self.pdf.hline(MARGIN, self.y + 20, CONTENT_W, color=LINE)
        self.y += 30

    def kv_grid(self, pairs, cols=2):
        rows = (len(pairs) + cols - 1) // cols
        self.need(rows * 34 + 6)
        col_w = CONTENT_W / cols
        for i, (k, v) in enumerate(pairs):
            cx = MARGIN + (i % cols) * col_w
            cy = self.y + (i // cols) * 34
            self.pdf.text(cx, cy, k.upper(), 7, bold=True, color=MUTED)
            self.pdf.text(cx, cy + 12, str(v), 10, bold=True, color=INK)
        self.y += rows * 34 + 6

    def score_box(self, score, verdict, subtitle, status="Tuntas"):
        self.need(96)
        color = GREEN if score >= 80 else (BRAND if score >= 70 else (AMBER if score >= 50 else RED))
        p = self.pdf
        p.rect(MARGIN, self.y, 150, 84, fill=color)
        p.text(MARGIN + 14, self.y + 14, "NILAI AKHIR", 8, bold=True, color=(240, 240, 255))
        p.text(MARGIN + 14, self.y + 30, f"{score:g}", 32, bold=True, color=WHITE)
        p.text(MARGIN + 14, self.y + 68, "skala 0 - 100", 7.5, color=(240, 240, 255))

        p.rect(MARGIN + 160, self.y, CONTENT_W - 160, 84, fill=SOFT, stroke=LINE)
        p.text(MARGIN + 178, self.y + 18, status, 16, bold=True, color=color)
        p.text(MARGIN + 178, self.y + 42, subtitle, 9, color=INK)
        p.text(MARGIN + 178, self.y + 60,
               "Dokumen ini dihasilkan otomatis oleh aplikasi TKA Cerdas.",
               8, color=MUTED)
        self.y += 100

    def bars(self, items):
        """items: [(label, nilai 0-100, warna)]"""
        if not items:
            return
        self.need(len(items) * 26 + 6)
        for label, val, color in items:
            val = 0 if val is None else val
            p = self.pdf
            p.text(MARGIN, self.y, label, 9.5, bold=True, color=INK)
            p.text(MARGIN, self.y, f"{val:g}%", 9.5, bold=True, color=color,
                   align="right", width=CONTENT_W)
            bar_y = self.y + 13
            p.rect(MARGIN, bar_y, CONTENT_W, 8, fill=(242, 239, 254))
            p.rect(MARGIN, bar_y, max(2, CONTENT_W * min(100, max(0, val)) / 100), 8, fill=color)
            self.y += 26

    def table(self, headers, widths, rows, aligns=None, row_h=19, header_bg=(240, 237, 255)):
        """Tabel sederhana dengan header berulang antar halaman."""
        aligns = aligns or ["left"] * len(headers)
        self.need(row_h * 3)

        def draw_header():
            p = self.pdf
            p.rect(MARGIN, self.y, CONTENT_W, row_h + 3, fill=header_bg)
            x = MARGIN
            for i, htxt in enumerate(headers):
                p.text(x + 5, self.y + 5, htxt, 8, bold=True, color=BRAND_DARK,
                       align=aligns[i], width=widths[i] - 10)
                x += widths[i]
            self.y += row_h + 3

        draw_header()
        for idx, row in enumerate(rows):
            if self.y + row_h > H - 52:
                self.new_page()
                draw_header()
            if idx % 2 == 1:
                self.pdf.rect(MARGIN, self.y, CONTENT_W, row_h, fill=(250, 249, 255))
            x = MARGIN
            for i, cell in enumerate(row):
                c = INK
                bold = False
                txt = str(cell)
                if i == len(row) - 1 and txt in ("Tuntas", "Belum", "Tidak hadir"):
                    c = GREEN if txt == "Tuntas" else RED
                    bold = True
                self.pdf.text(x + 5, self.y + 4.5, txt, 8.5, bold=bold, color=c,
                              align=aligns[i], width=widths[i] - 10)
                x += widths[i]
            self.pdf.hline(MARGIN, self.y + row_h, CONTENT_W, color=(240, 238, 250))
            self.y += row_h
        self.y += 8


# ---------------------------------------------------------------------------
# Laporan per siswa
# ---------------------------------------------------------------------------
def student_report(result, kkm=70.0, school_name="SMP"):
    """result: dict hasil attempt_result(include_student=True)."""
    score = result.get("score") or 0
    student = result.get("student") or {}
    kategori = result.get("kategori") or {}
    pkg = result.get("paket", "Ujian")
    tuntas = score >= kkm
    verdict = "TUNTAS" if tuntas else "BELUM TUNTAS"

    rep = Report("Laporan Hasil Ujian", f"{pkg}", school_name)
    rep.kv_grid([
        ("Nama siswa", student.get("name", "-")),
        ("Email", student.get("email", "-")),
        ("Paket ujian", pkg),
        ("Mata pelajaran", result.get("mapel", "-")),
        ("Dikumpulkan", _fmt_date(result.get("submitted_at"))),
        ("Durasi pengerjaan", _durasi(result.get("started_at"), result.get("submitted_at"))),
    ])
    rep.y += 6
    rep.score_box(
        score, verdict,
        f"Benar {result.get('correct_count', 0)} dari {result.get('total_count', 0)} soal "
        f"\u00b7 Nilai minimum ketuntasan (KKM) {kkm:g}",
        status=("TUNTAS" if tuntas else "BELUM TUNTAS"),
    )

    rep.section("Penguasaan per kategori")
    warna = {"literasi": (59, 157, 246), "numerasi": (255, 176, 32)}
    items = [(("Literasi" if k == "literasi" else "Numerasi"), v, warna.get(k, BRAND))
             for k, v in kategori.items() if v is not None]
    if items:
        rep.bars(items)
    else:
        rep.pdf.text(MARGIN, rep.y, "Tidak ada data kategori.", 9, color=MUTED)
        rep.y += 18

    rep.y += 4
    rep.section("Rincian jawaban per soal")
    rows = []
    for q in result.get("questions", []):
        jawab = (q.get("jawaban") or "").strip() or "(kosong)"
        rows.append([
            q.get("nomor", ""),
            "Literasi" if q.get("kategori") == "literasi" else "Numerasi",
            jawab[:34],
            str(q.get("kunci", "")),
            "Benar" if q.get("benar") else "Salah",
        ])
    rep.table(
        ["No", "Kategori", "Jawaban siswa", "Kunci", "Hasil"],
        [40, 110, 230, 60, 75],
        rows,
        aligns=["center", "left", "left", "center", "center"],
    )
    return rep.finish()


# ---------------------------------------------------------------------------
# Rekapitulasi kelas
# ---------------------------------------------------------------------------
def class_report(data, kkm=70.0, school_name="SMP", kelas="", judul_paket=""):
    """data: dict hasil analytics(conn, package_id) + daftar peserta opsional."""
    s = data.get("stats", {})
    pkg = judul_paket or f"Paket #{data.get('package_id')}"
    rep = Report("Rekapitulasi Hasil Kelas", pkg, school_name)

    peserta = s.get("peserta", 0)
    rep.kv_grid([
        ("Kelas", kelas or "Seluruh siswa"),
        ("Paket ujian", pkg),
        ("Jumlah peserta", str(peserta)),
        ("Rata-rata nilai", f"{s.get('rata_rata'):g}" if s.get("rata_rata") is not None else "-"),
        ("Nilai tertinggi", f"{s.get('tertinggi'):g}" if s.get("tertinggi") is not None else "-"),
        ("Nilai terendah", f"{s.get('terendah'):g}" if s.get("terendah") is not None else "-"),
        ("KKM", f"{kkm:g}"),
        ("Persentase tuntas",
         f"{s.get('persen_tuntas'):g}% ({s.get('tuntas', 0)} siswa)" if s.get("persen_tuntas") is not None else "-"),
    ])
    rep.y += 6

    rep.section("Distribusi nilai")
    dist = data.get("distribusi", [])
    if dist:
        maxn = max(1, max(d["jumlah"] for d in dist))
        bar_w = CONTENT_W - 120
        for d in dist:
            p = rep.pdf
            rep.need(22)
            p.text(MARGIN, rep.y, d["label"], 9, bold=True, color=INK)
            w = max(2, bar_w * d["jumlah"] / maxn) if d["jumlah"] else 0
            p.rect(MARGIN + 80, rep.y + 1, bar_w, 10, fill=(242, 239, 254))
            if w:
                p.rect(MARGIN + 80, rep.y + 1, w, 10, fill=BRAND)
            p.text(MARGIN, rep.y, f"{d['jumlah']} siswa", 8.5, color=MUTED,
                   align="right", width=CONTENT_W)
            rep.y += 20
    rep.y += 10

    rep.section("Peringkat peserta")
    rows = []
    for i, a in enumerate(data.get("attempts", []), start=1):
        rows.append([
            str(i),
            a.get("name", "-"),
            a.get("email", "-"),
            f"{a.get('score'):g}",
            f"{a.get('correct_count', 0)}/{a.get('total_count', 0)}",
            "Tuntas" if (a.get("score") or 0) >= kkm else "Belum",
        ])
    if rows:
        rep.table(
            ["#", "Nama siswa", "Email", "Nilai", "Benar", "Status"],
            [34, 150, 170, 50, 55, 56],
            rows,
            aligns=["center", "left", "left", "center", "center", "center"],
        )
    else:
        rep.pdf.text(MARGIN, rep.y, "Belum ada peserta yang mengumpulkan.", 9, color=MUTED)
        rep.y += 20

    pq = data.get("per_question", [])
    if pq:
        rep.section("Analisis butir soal")
        rows = []
        for q in pq:
            rows.append([
                str(q.get("nomor", "")),
                "Literasi" if q.get("kategori") == "literasi" else "Numerasi",
                f"{q.get('persen_benar', 0):g}%",
                q.get("label", "").capitalize(),
                q.get("pertanyaan", "")[:56],
            ])
        rep.table(
            ["No", "Kategori", "Benar", "Tingkat", "Butir soal"],
            [36, 82, 52, 66, 279],
            rows,
            aligns=["center", "left", "center", "left", "left"],
        )

        sulit = [q for q in pq if q.get("persen_benar", 100) < 40]
        if sulit:
            rep.section("Catatan untuk guru")
            rep.need(30 + len(sulit) * 13)
            rep.pdf.text(MARGIN, rep.y, "Butir soal dengan tingkat penguasaan rendah (<40%):",
                         9, bold=True, color=RED)
            rep.y += 15
            for q in sulit:
                rep.need(13)
                rep.pdf.text(MARGIN + 8, rep.y,
                             f"Soal {q.get('nomor')} — {q.get('persen_benar', 0):g}% benar "
                             f"({q.get('pertanyaan', '')[:70]})", 8.5, color=INK)
                rep.y += 13
            rep.pdf.text(MARGIN, rep.y + 4,
                         "Disarankan mengulang pembahasan materi terkait.",
                         8.5, color=MUTED)
            rep.y += 16

    return rep.finish()


# ---------------------------------------------------------------------------
# Rekap kehadiran (PDF)
# ---------------------------------------------------------------------------
def attendance_report(rows, kkm, school_name, paket):
    """rows: [(nama, email, kelas, nilai|None, status)]"""
    rep = Report("Rekap Kehadiran Peserta", paket, school_name)
    hadir = sum(1 for r in rows if r[4] != "Tidak hadir")
    rep.kv_grid([
        ("Paket ujian", paket),
        ("Jumlah siswa", str(len(rows))),
        ("Sudah mengerjakan", str(hadir)),
        ("Belum mengerjakan", str(len(rows) - hadir)),
        ("KKM", f"{kkm:g}"),
        ("Tanggal cetak", datetime.now().strftime("%d-%m-%Y %H:%M")),
    ])
    rep.y += 6
    rep.section("Daftar peserta")
    table_rows = []
    for i, (nama, email, kelas, nilai, status) in enumerate(rows, start=1):
        table_rows.append([
            str(i), nama, kelas or "-",
            "-" if nilai is None else f"{nilai:g}",
            status,
        ])
    rep.table(
        ["#", "Nama siswa", "Kelas", "Nilai", "Keterangan"],
        [34, 200, 90, 70, 121],
        table_rows,
        aligns=["center", "left", "left", "center", "center"],
    )
    return rep.finish()
