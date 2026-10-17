# -*- coding: utf-8 -*-
"""
office.py — Pembaca berkas Excel (.xlsx/.xlsm), Word (.docx), CSV, dan TXT
tanpa dependensi eksternal.

.xlsx dan .docx sebenarnya adalah arsip ZIP berisi XML, sehingga dapat dibaca
dengan zipfile + xml.etree dari pustaka standar.
"""
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

MAX_FILE = 5 * 1024 * 1024          # 5 MB
MAX_ROWS = 500


class ImportError_(Exception):
    """Berkas tidak dapat dibaca."""


# ---------------------------------------------------------------------------
# Utilitas bersama
# ---------------------------------------------------------------------------
def _col_index(ref):
    """'B12' -> 1 (0-based)."""
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return max(0, n - 1)


def _clean_cell(s):
    if s is None:
        return ""
    s = str(s).replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", s).strip()


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------
def read_xlsx(data: bytes):
    """Kembalikan daftar baris (list of list of str) dari sheet pertama."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ImportError_("Berkas bukan Excel (.xlsx) yang sah.")

    names = set(zf.namelist())
    if "xl/workbook.xml" not in names:
        raise ImportError_("Struktur Excel tidak dikenali (workbook.xml tidak ada).")

    # --- shared strings
    shared = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            texts = [t.text or "" for t in si.iter(f"{NS}t")]
            shared.append("".join(texts))

    # --- sheet pertama
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = wb.find(f"{NS}sheets")
    if sheets is None or not len(sheets):
        raise ImportError_("Berkas Excel tidak memiliki sheet.")
    first = list(sheets)[0]
    rid = first.get(f"{NS_R}id") or first.get("r:id")

    target = "xl/worksheets/sheet1.xml"
    if rid and "xl/_rels/workbook.xml.rels" in names:
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rels:
            if rel.get("Id") == rid:
                t = (rel.get("Target") or "").lstrip("/")
                target = t if t.startswith("xl/") else "xl/" + t
                break
    if target not in names:
        cands = [n for n in names if n.startswith("xl/worksheets/sheet")]
        if not cands:
            raise ImportError_("Worksheet tidak ditemukan di dalam berkas Excel.")
        target = sorted(cands)[0]

    ws = ET.fromstring(zf.read(target))
    rows = []
    sheet_data = ws.find(f"{NS}sheetData")
    if sheet_data is None:
        return rows

    for row in sheet_data.findall(f"{NS}row"):
        values = {}
        for c in row.findall(f"{NS}c"):
            t = c.get("t")
            v = c.find(f"{NS}v")
            if t == "inlineStr":
                is_el = c.find(f"{NS}is")
                text = "".join(x.text or "" for x in is_el.iter(f"{NS}t")) if is_el is not None else ""
            elif t == "s":
                idx = int(v.text) if v is not None and v.text else -1
                text = shared[idx] if 0 <= idx < len(shared) else ""
            elif t == "str":
                text = v.text if v is not None and v.text else ""
            else:
                text = v.text if v is not None and v.text else ""
                # angka bulat tanpa .0
                if isinstance(text, str) and re.fullmatch(r"-?\d+\.0+", text):
                    text = text.split(".")[0]
            values[_col_index(c.get("r", "A1"))] = _clean_cell(text)
        if values:
            width = max(values) + 1
            rows.append([values.get(i, "") for i in range(width)])
        if len(rows) > MAX_ROWS:
            raise ImportError_(f"Baris melebihi batas {MAX_ROWS}. Persempit berkasnya.")
    return rows


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def _docx_paragraph_text(p):
    return "".join(t.text or "" for t in p.iter(f"{NS_W}t"))


def read_docx_blocks(data: bytes):
    """Kembalikan daftar blok: ('p', teks) atau ('tbl', [[sel,...],...])."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ImportError_("Berkas bukan Word (.docx) yang sah.")
    if "word/document.xml" not in zf.namelist():
        raise ImportError_("Struktur Word tidak dikenali (document.xml tidak ada).")
    root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(f"{NS_W}body")
    if body is None:
        raise ImportError_("Isi dokumen Word kosong.")

    blocks = []
    for child in body:
        if child.tag == f"{NS_W}p":
            blocks.append(("p", _docx_paragraph_text(child)))
        elif child.tag == f"{NS_W}tbl":
            table = []
            for tr in child.findall(f"{NS_W}tr"):
                cells = []
                for tc in tr.findall(f"{NS_W}tc"):
                    txt = " ".join(_docx_paragraph_text(p) for p in tc.findall(f"{NS_W}p"))
                    cells.append(_clean_cell(txt))
                table.append(cells)
            blocks.append(("tbl", table))
    return blocks


# ---------------------------------------------------------------------------
# CSV / TXT
# ---------------------------------------------------------------------------
def read_csv(data: bytes):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportError_("Berkas CSV tidak dapat dibaca (encoding tidak dikenali).")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [[_clean_cell(c) for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    rows = [r for r in rows if any(r)]
    if len(rows) > MAX_ROWS:
        raise ImportError_(f"Baris melebihi batas {MAX_ROWS}.")
    return rows


# ---------------------------------------------------------------------------
# Normalisasi soal
# ---------------------------------------------------------------------------
ALIAS = {
    "no": "no", "nomor": "no", "no.": "no", "num": "no",
    "tipe": "tipe", "jenis": "tipe", "type": "tipe", "bentuk": "tipe",
    "kategori": "kategori", "category": "kategori", "aspek": "kategori",
    "tingkat": "tingkat", "level": "tingkat", "kesulitan": "tingkat",
    "stimulus": "stimulus", "teks": "stimulus", "wacana": "stimulus", "bacaan": "stimulus",
    "pertanyaan": "pertanyaan", "soal": "pertanyaan", "question": "pertanyaan",
    "a": "a", "b": "b", "c": "c", "d": "d", "e": "e",
    "pilihan a": "a", "pilihan b": "b", "pilihan c": "c",
    "pilihan d": "d", "pilihan e": "e",
    "kunci": "kunci", "kunci jawaban": "kunci", "jawaban": "kunci", "answer": "kunci",
    "pembahasan": "pembahasan", "penjelasan": "pembahasan", "explanation": "pembahasan",
    "toleransi": "toleransi", "tolerance": "toleransi",
}


def _norm_header(h):
    h = _clean_cell(h).lower().rstrip(":").strip()
    return ALIAS.get(h, None)


def rows_to_questions(rows, default_kategori="numerasi"):
    """
    Ubah tabel (baris pertama header) menjadi daftar soal.
    Mengembalikan (questions, errors).
    """
    errors = []
    questions = []
    if not rows:
        return [], ["Berkas kosong."]

    headers = [_norm_header(h) for h in rows[0]]
    if "pertanyaan" not in headers:
        raise ImportError_(
            "Baris pertama harus berupa judul kolom dan memuat kolom 'Pertanyaan'. "
            "Kolom yang dikenali: no, tipe, kategori, tingkat, stimulus, pertanyaan, "
            "a, b, c, d, e, kunci, pembahasan, toleransi."
        )

    for r_i, row in enumerate(rows[1:], start=2):
        rec = {}
        for idx, key in enumerate(headers):
            if key and idx < len(row):
                rec[key] = _clean_cell(row[idx])
        pertanyaan = rec.get("pertanyaan", "")
        if not pertanyaan:
            if any(rec.values()):
                errors.append(f"Baris {r_i}: kolom pertanyaan kosong, dilewati.")
            continue

        tipe = (rec.get("tipe") or "pg").lower()
        if tipe in ("isian", "essay", "esai", "jawaban singkat", "short", "angka"):
            tipe = "isian"
        else:
            tipe = "pg"

        opsi = [rec.get(k, "") for k in ("a", "b", "c", "d", "e")]
        # buang opsi kosong di belakang, tetapi pertahankan urutan
        while opsi and not opsi[-1]:
            opsi.pop()

        kunci = (rec.get("kunci") or "").strip()
        kategori = (rec.get("kategori") or default_kategori).lower()
        kategori = "literasi" if kategori.startswith("lit") else "numerasi"
        tingkat = (rec.get("tingkat") or "sedang").lower()
        tingkat = {"mudah": "mudah", "easy": "mudah", "sulit": "sulit", "sukar": "sulit",
                   "hard": "sulit", "sedang": "sedang", "medium": "sedang"}.get(tingkat, "sedang")

        if tipe == "pg":
            if len(opsi) < 2:
                errors.append(f"Baris {r_i}: soal pilihan ganda butuh minimal 2 opsi, dilewati.")
                continue
            kunci_norm = kunci.upper().replace(".", "").strip()
            if kunci_norm in ("A", "B", "C", "D", "E"):
                pos = "ABCDE".index(kunci_norm)
                if pos >= len(opsi):
                    errors.append(f"Baris {r_i}: kunci {kunci_norm} tetapi opsi hanya {len(opsi)}.")
                    continue
                kunci = kunci_norm
            elif kunci.isdigit():
                pos = int(kunci) - 1
                if not 0 <= pos < len(opsi):
                    errors.append(f"Baris {r_i}: kunci nomor {kunci} di luar jumlah opsi.")
                    continue
                kunci = "ABCDE"[pos]
            else:
                errors.append(f"Baris {r_i}: kunci harus huruf A-E (atau nomor 1-5).")
                continue
        else:
            try:
                float(kunci.replace(".", "").replace(",", ".") if "," in kunci else kunci)
            except ValueError:
                errors.append(f"Baris {r_i}: soal isian butuh kunci berupa angka.")
                continue

        toleransi = 0.0
        if rec.get("toleransi"):
            try:
                toleransi = float(rec["toleransi"].replace(",", "."))
            except ValueError:
                errors.append(f"Baris {r_i}: toleransi '{rec['toleransi']}' bukan angka, dipakai 0.")
                toleransi = 0.0

        questions.append({
            "tipe": tipe,
            "kategori": kategori,
            "tingkat": tingkat,
            "stimulus": rec.get("stimulus", ""),
            "pertanyaan": pertanyaan,
            "opsi": opsi if tipe == "pg" else [],
            "kunci": kunci,
            "toleransi": toleransi,
            "pembahasan": rec.get("pembahasan", ""),
        })
    return questions, errors


# ---------------------------------------------------------------------------
# Parser teks gaya Word (juga untuk .txt)
# ---------------------------------------------------------------------------
RE_Q = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(.+)$")
RE_OPT = re.compile(r"^\s*([A-Ea-e])\s*[.)]\s*(.+)$")
RE_META = re.compile(r"^\s*(kunci(?:\s+jawaban)?|jawaban|pembahasan|kategori|tingkat|stimulus|tipe)\s*[:\-]\s*(.*)$", re.I)


def parse_text_questions(text, default_kategori="numerasi"):
    """Parser format soal berbasis teks (hasil salin-tempel Word / .txt)."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    questions, errors = [], []
    cur = None
    field = None          # kolom yang sedang diisi (untuk multi-baris)

    def flush():
        nonlocal cur
        if cur is None:
            return
        if not cur["pertanyaan"].strip():
            return
        if cur["opsi"]:
            cur["tipe"] = "pg"
            if cur["kunci"]:
                k = cur["kunci"].strip().upper().replace(".", "")
                if k and k[0] in "ABCDE":
                    cur["kunci"] = k[0]
                    if "ABCDE".index(k[0]) >= len(cur["opsi"]):
                        errors.append(f"Soal {cur['nomor']}: kunci {k[0]} melebihi jumlah opsi.")
                elif k.isdigit():
                    cur["kunci"] = "ABCDE"[int(k) - 1]
        else:
            cur["tipe"] = "isian"
        if not cur["kunci"]:
            errors.append(f"Soal {cur['nomor']}: kunci jawaban tidak ditemukan.")
        questions.append(cur)
        cur = None

    for raw in lines:
        line = raw.strip()
        if not line:
            field = None
            continue

        m = RE_Q.match(line)
        if m and not RE_OPT.match(line):
            # baris pertanyaan baru (hindari menangkap "A. ..." sebagai soal)
            flush()
            cur = {
                "nomor": m.group(1), "pertanyaan": m.group(2).strip(),
                "opsi": [], "kunci": "", "pembahasan": "", "stimulus": "",
                "kategori": default_kategori, "tingkat": "sedang", "toleransi": 0.0,
            }
            field = "pertanyaan"
            continue

        if cur is None:
            continue

        m = RE_META.match(line)
        if m:
            key = m.group(1).lower()
            val = m.group(2).strip()
            if key.startswith("kunci") or key == "jawaban":
                cur["kunci"] = val
                field = None
            elif key == "pembahasan":
                cur["pembahasan"] = val
                field = "pembahasan"
            elif key == "kategori":
                cur["kategori"] = "literasi" if val.lower().startswith("lit") else "numerasi"
                field = None
            elif key == "tingkat":
                v = val.lower()
                cur["tingkat"] = "mudah" if v.startswith("mud") else ("sulit" if v.startswith("sul") else "sedang")
                field = None
            elif key == "stimulus":
                cur["stimulus"] = val
                field = "stimulus"
            elif key == "tipe":
                cur["tipe"] = "isian" if val.lower().startswith("is") else "pg"
                field = None
            continue

        m = RE_OPT.match(line)
        if m:
            cur["opsi"].append(m.group(2).strip())
            field = None
            continue

        # lanjutan teks
        if field == "pertanyaan":
            cur["pertanyaan"] += "\n" + line
        elif field == "pembahasan":
            cur["pembahasan"] += "\n" + line
        elif field == "stimulus":
            cur["stimulus"] += "\n" + line
        else:
            cur["pertanyaan"] += "\n" + line

    flush()
    return questions, errors


def parse_file(filename: str, data: bytes, default_kategori="numerasi"):
    """Deteksi jenis berkas dan kembalikan (questions, errors, info)."""
    if len(data) > MAX_FILE:
        raise ImportError_("Ukuran berkas melebihi 5 MB.")
    if not data:
        raise ImportError_("Berkas kosong.")

    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        rows = read_xlsx(data)
        qs, errs = rows_to_questions(rows, default_kategori)
        return qs, errs, f"Excel: {len(rows) - 1} baris dibaca"

    if name.endswith(".docx"):
        blocks = read_docx_blocks(data)
        # bila dokumen memuat tabel, coba baca sebagai tabel
        tables = [b[1] for b in blocks if b[0] == "tbl" and b[1]]
        if tables:
            best = max(tables, key=len)
            heads = [_norm_header(h) for h in best[0]]
            if "pertanyaan" in heads:
                qs, errs = rows_to_questions(best, default_kategori)
                return qs, errs, f"Word: tabel {len(best) - 1} baris dibaca"
        text = "\n".join(b[1] for b in blocks if b[0] == "p")
        qs, errs = parse_text_questions(text, default_kategori)
        return qs, errs, f"Word: {len(text.splitlines())} paragraf dibaca"

    if name.endswith((".csv", ".tsv")):
        rows = read_csv(data)
        qs, errs = rows_to_questions(rows, default_kategori)
        return qs, errs, f"CSV: {len(rows) - 1} baris dibaca"

    if name.endswith((".txt", ".md")):
        text = data.decode("utf-8", "replace")
        qs, errs = parse_text_questions(text, default_kategori)
        return qs, errs, f"Teks: {len(qs)} soal terdeteksi"

    # .xls lama atau format lain
    raise ImportError_(
        "Format belum didukung. Gunakan .xlsx, .docx, .csv, atau .txt. "
        "Untuk berkas .xls lama, simpan ulang sebagai .xlsx di Excel."
    )


def _xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_template_xlsx():
    """Bangun berkas .xlsx sederhana (inline strings) berisi contoh format soal."""
    header, contoh = template_rows()
    rows = [header] + contoh

    def col_letter(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    sheet_rows = []
    for r_i, row in enumerate(rows, start=1):
        cells = []
        for c_i, val in enumerate(row):
            ref = f"{col_letter(c_i)}{r_i}"
            if r_i == 1:
                cells.append(
                    f'<c r="{ref}" t="inlineStr" s="1"><is><t>{_xml_escape(val)}</t></is></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(val)}</t></is></c>')
        sheet_rows.append(f'<row r="{r_i}">' + "".join(cells) + "</row>")

    widths = ""
    for i, w in enumerate([5, 9, 11, 9, 40, 60, 22, 22, 22, 22, 22, 9, 40, 10]):
        widths += f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'

    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<cols>{widths}</cols><sheetData>' + "".join(sheet_rows) + "</sheetData></worksheet>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="2"><xf xfId="0"/><xf fontId="1" xfId="0" applyFont="1"/></cellXfs>'
        '</styleSheet>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Soal" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def template_rows():
    """Contoh tabel untuk diunduh sebagai template Excel/CSV."""
    header = ["no", "tipe", "kategori", "tingkat", "stimulus", "pertanyaan",
              "a", "b", "c", "d", "e", "kunci", "pembahasan", "toleransi"]
    contoh = [
        ["1", "pg", "numerasi", "mudah", "",
         "Hasil dari 12 x 8 adalah ....", "86", "96", "106", "116", "", "B",
         "12 x 8 = 96.", "0"],
        ["2", "pg", "literasi", "sedang",
         "Banjir sering terjadi karena saluran air tersumbat sampah.",
         "Ide pokok teks tersebut adalah ....",
         "Penyebab banjir", "Cara membuat sampah", "Jenis saluran air", "Waktu banjir", "", "A",
         "Teks menjelaskan penyebab banjir, yaitu saluran air tersumbat sampah.", "0"],
        ["3", "isian", "numerasi", "sedang", "",
         "Keliling persegi dengan sisi 9 cm adalah ... cm.", "", "", "", "", "", "36",
         "Keliling = 4 x 9 = 36 cm.", "0"],
    ]
    return header, contoh
