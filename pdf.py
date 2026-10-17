# -*- coding: utf-8 -*-
"""
pdf.py — Pembuat PDF minimal tanpa dependensi eksternal.

Mendukung teks (Helvetica / Helvetica-Bold standar PDF), garis, kotak berwarna,
dan banyak halaman. Koordinat memakai titik (pt), A4 = 595.28 x 841.89.
Titik asal di kiri-atas agar mudah dipakai untuk tata letak laporan.
"""
import zlib

# Lebar karakter (per 1000 unit) dari metrik font standar Helvetica.
_W_REG = {
    32: 278, 33: 278, 34: 355, 35: 556, 36: 556, 37: 889, 38: 667, 39: 191,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 278, 59: 278, 60: 584, 61: 584, 62: 584, 63: 556,
    64: 1015, 65: 667, 66: 667, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 500, 75: 667, 76: 556, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 278, 92: 278, 93: 278, 94: 469, 95: 556,
    96: 333, 97: 556, 98: 556, 99: 500, 100: 556, 101: 556, 102: 278, 103: 556,
    104: 556, 105: 222, 106: 222, 107: 500, 108: 222, 109: 833, 110: 556,
    111: 556, 112: 556, 113: 556, 114: 333, 115: 500, 116: 278, 117: 556,
    118: 500, 119: 722, 120: 500, 121: 500, 122: 500, 123: 334, 124: 260,
    125: 334, 126: 584,
}
_W_BOLD = {
    32: 278, 33: 333, 34: 474, 35: 556, 36: 556, 37: 889, 38: 722, 39: 238,
    40: 333, 41: 333, 42: 389, 43: 584, 44: 278, 45: 333, 46: 278, 47: 278,
    48: 556, 49: 556, 50: 556, 51: 556, 52: 556, 53: 556, 54: 556, 55: 556,
    56: 556, 57: 556, 58: 333, 59: 333, 60: 584, 61: 584, 62: 584, 63: 611,
    64: 975, 65: 722, 66: 722, 67: 722, 68: 722, 69: 667, 70: 611, 71: 778,
    72: 722, 73: 278, 74: 556, 75: 722, 76: 611, 77: 833, 78: 722, 79: 778,
    80: 667, 81: 778, 82: 722, 83: 667, 84: 611, 85: 722, 86: 667, 87: 944,
    88: 667, 89: 667, 90: 611, 91: 333, 92: 278, 93: 333, 94: 584, 95: 556,
    96: 333, 97: 556, 98: 611, 99: 556, 100: 611, 101: 556, 102: 333, 103: 611,
    104: 611, 105: 278, 106: 278, 107: 556, 108: 278, 109: 889, 110: 611,
    111: 611, 112: 611, 113: 611, 114: 389, 115: 556, 116: 333, 117: 611,
    118: 556, 119: 778, 120: 556, 121: 556, 122: 500, 123: 389, 124: 280,
    125: 389, 126: 584,
}

# Peta karakter di luar ASCII -> padanan Latin-1/WinAnsi yang aman.
_TRANSLIT = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
    "\u2022": "-", "\u2192": "->", "\u2190": "<-", "\u2264": "<=", "\u2265": ">=",
    "\u00d7": "x", "\u00f7": "/",
}


def _clean(s):
    s = str(s)
    for k, v in _TRANSLIT.items():
        s = s.replace(k, v)
    # buang karakter di luar Latin-1 agar tidak merusak encoding PDF
    return "".join(ch if ord(ch) < 256 else "?" for ch in s)


def _escape(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "(":
            out.append("\\(")
        elif ch == ")":
            out.append("\\)")
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append("\\%03o" % (o & 0xFF))
    return "".join(out)


class PDF:
    """Kanvas PDF sederhana dengan titik asal kiri-atas."""

    A4 = (595.276, 841.890)

    def __init__(self, size=None):
        self.w, self.h = size or self.A4
        self.pages = []
        self.cur = None
        self.new_page()

    # -- manajemen halaman ------------------------------------------------
    def new_page(self):
        self.cur = []
        self.pages.append(self.cur)

    def _y(self, y):
        return self.h - y

    # -- primitif ---------------------------------------------------------
    def text(self, x, y, s, size=10, bold=False, color=(0, 0, 0), align="left", width=None):
        s = _clean(s)
        if align in ("right", "center") and width is not None:
            tw = self.text_width(s, size, bold)
            x = x + width - tw if align == "right" else x + (width - tw) / 2
        r, g, b = [c / 255 for c in color]
        font = "/F2" if bold else "/F1"
        self.cur.append(
            "BT %s %.2f Tf %.4f %.4f %.4f rg 1 0 0 1 %.2f %.2f Tm (%s) Tj ET"
            % (font, size, r, g, b, x, self._y(y) - size * 0.78, _escape(s))
        )
        return self.text_width(s, size, bold)

    def text_width(self, s, size=10, bold=False):
        table = _W_BOLD if bold else _W_REG
        return sum(table.get(ord(c), 556) for c in _clean(s)) * size / 1000.0

    def rect(self, x, y, w, h, fill=None, stroke=None, line_width=0.7):
        ops = []
        if fill:
            r, g, b = [c / 255 for c in fill]
            ops.append("%.4f %.4f %.4f rg" % (r, g, b))
        if stroke:
            r, g, b = [c / 255 for c in stroke]
            ops.append("%.4f %.4f %.4f RG %.2f w" % (r, g, b, line_width))
        ops.append("%.2f %.2f %.2f %.2f re" % (x, self._y(y) - h, w, h))
        ops.append("B" if (fill and stroke) else ("f" if fill else "S"))
        self.cur.append(" ".join(ops))

    def line(self, x1, y1, x2, y2, color=(200, 200, 200), width=0.7):
        r, g, b = [c / 255 for c in color]
        self.cur.append(
            "%.4f %.4f %.4f RG %.2f w %.2f %.2f m %.2f %.2f l S"
            % (r, g, b, width, x1, self._y(y1), x2, self._y(y2))
        )

    def hline(self, x, y, w, **kw):
        self.line(x, y, x + w, y, **kw)

    # -- keluaran ---------------------------------------------------------
    def output(self) -> bytes:
        objs = []          # daftar bytes objek (1-indexed nanti)

        def add(b):
            objs.append(b)
            return len(objs)          # nomor objek

        # Katalog & Pages ditambahkan terakhir agar nomornya diketahui;
        # gunakan placeholder dulu.
        catalog_no = add(b"")          # 1
        pages_no = add(b"")            # 2
        font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica"
                    b" /Encoding /WinAnsiEncoding >>")           # 3
        font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold"
                    b" /Encoding /WinAnsiEncoding >>")           # 4

        page_nos = []
        for ops in self.pages:
            stream = "\n".join(ops).encode("latin-1", "replace")
            comp = zlib.compress(stream, 6)
            content_no = add(
                b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(comp)
                + comp + b"\nendstream"
            )
            page_no = add(
                ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f]"
                 " /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >>"
                 " /Contents %d 0 R >>" % (pages_no, self.w, self.h, font1, font2, content_no)
                 ).encode()
            )
            page_nos.append(page_no)

        objs[catalog_no - 1] = ("<< /Type /Catalog /Pages %d 0 R >>" % pages_no).encode()
        kids = " ".join("%d 0 R" % n for n in page_nos)
        objs[pages_no - 1] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                              % (kids, len(page_nos))).encode()

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref_at = len(out)
        out += b"xref\n0 %d\n" % (len(objs) + 1)
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += b"%010d 00000 n \n" % off
        out += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                % (len(objs) + 1, catalog_no, xref_at))
        return bytes(out)
