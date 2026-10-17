#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TKA Cerdas — aplikasi asesmen Literasi & Numerasi jenjang SMP.
Backend tanpa dependensi eksternal: Python standard library + SQLite.

Jalankan:  python3 server.py          (default port 8000)
"""
import csv
import hashlib
import io
import json
import os
import random
import re
import secrets
import sqlite3
import sys
import threading
import traceback
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gsheets
import office
import reports
from seed_soal import PAKET, PAKET_SOAL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Lokasi basis data dapat dipindah (mis. volume persisten di Docker/Render).
DB_DIR = os.environ.get("TKA_DB_DIR", BASE_DIR)
os.makedirs(DB_DIR, exist_ok=True) if DB_DIR else None
DB_PATH = os.path.join(DB_DIR, "tka.db")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY = 512 * 1024
GURU_CODE_DEFAULT = os.environ.get("GURU_CODE", "GURU2026")
DEMO_ON = os.environ.get("TKA_SEED_DEMO", "1") not in ("0", "false", "False", "")
ADMIN_EMAIL = os.environ.get("TKA_ADMIN_EMAIL", "guru@tka.id")
ADMIN_NAME = os.environ.get("TKA_ADMIN_NAME", "Guru TKA")
ADMIN_PASSWORD = os.environ.get("TKA_ADMIN_PASSWORD", "guru123")
KKM_DEFAULT = float(os.environ.get("TKA_KKM", "70"))
GRACE_SECONDS = 90          # toleransi setelah waktu habis
SHEET_TAB_DEFAULT = "Hasil"
SHEET_HEADER = [
    "Waktu Kumpul", "Nama Siswa", "Email", "Paket", "Mapel",
    "Skor", "Benar", "Total", "Nilai Literasi (%)", "Nilai Numerasi (%)",
    "Durasi (menit)", "Attempt ID",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


# ---------------------------------------------------------------------------
# Waktu
# ---------------------------------------------------------------------------
def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(s):
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return utc_now()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return secrets.compare_digest(test, digest)


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def init_db():
    conn = db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'siswa' CHECK (role IN ('guru','siswa')),
                created_at    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS packages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                kode      TEXT NOT NULL UNIQUE,
                judul     TEXT NOT NULL,
                mapel     TEXT NOT NULL,
                kategori  TEXT NOT NULL,
                deskripsi TEXT NOT NULL DEFAULT '',
                durasi    INTEGER NOT NULL DEFAULT 60,
                urutan    INTEGER NOT NULL DEFAULT 0,
                aktif     INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS questions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                nomor      INTEGER NOT NULL,
                tipe       TEXT NOT NULL CHECK (tipe IN ('pg','isian')),
                kategori   TEXT NOT NULL,
                tingkat    TEXT NOT NULL DEFAULT 'sedang',
                stimulus   TEXT NOT NULL DEFAULT '',
                pertanyaan TEXT NOT NULL,
                opsi_json  TEXT NOT NULL DEFAULT '[]',
                kunci      TEXT NOT NULL,
                toleransi  REAL NOT NULL DEFAULT 0,
                pembahasan TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_q_pkg ON questions (package_id, nomor);
            CREATE TABLE IF NOT EXISTS attempts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                package_id    INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                started_at    TEXT NOT NULL,
                deadline_at   TEXT NOT NULL,
                submitted_at  TEXT,
                status        TEXT NOT NULL DEFAULT 'in_progress'
                              CHECK (status IN ('in_progress','submitted')),
                score         REAL,
                correct_count INTEGER NOT NULL DEFAULT 0,
                total_count   INTEGER NOT NULL DEFAULT 0,
                synced        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_att_user ON attempts (user_id, status);
            CREATE TABLE IF NOT EXISTS answers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id  INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                jawaban     TEXT NOT NULL DEFAULT '',
                benar       INTEGER NOT NULL DEFAULT 0,
                UNIQUE (attempt_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                at      TEXT NOT NULL,
                ok      INTEGER NOT NULL,
                message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS classes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                class_id   INTEGER REFERENCES classes(id) ON DELETE CASCADE,
                start_at   TEXT NOT NULL,
                end_at     TEXT NOT NULL,
                token      TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        # Migrasi kolom (aman dijalankan berulang)
        for stmt in (
            "ALTER TABLE users ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL",
            "ALTER TABLE attempts ADD COLUMN schedule_id INTEGER",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # kolom sudah ada
        conn.commit()
        seed_packages(conn)
        seed_users(conn)
        seed_kelas(conn)
        seed_demo_attempts(conn)
        seed_schedule_demo(conn)
        conn.commit()
    finally:
        conn.close()


def seed_packages(conn):
    if conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] > 0:
        return
    for p in PAKET:
        cur = conn.execute(
            "INSERT INTO packages (kode, judul, mapel, kategori, deskripsi, durasi, urutan)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (p["kode"], p["judul"], p["mapel"], p["kategori"], p["deskripsi"], p["durasi"], p["urutan"]),
        )
        pkg_id = cur.lastrowid
        for i, q in enumerate(PAKET_SOAL[p["kode"]], start=1):
            conn.execute(
                "INSERT INTO questions (package_id, nomor, tipe, kategori, tingkat, stimulus,"
                " pertanyaan, opsi_json, kunci, toleransi, pembahasan)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pkg_id, i, q["tipe"], q["kategori"], q.get("tingkat", "sedang"),
                    q.get("stimulus", ""), q["pertanyaan"],
                    json.dumps(q.get("opsi", []), ensure_ascii=False),
                    q["kunci"], float(q.get("toleransi", 0)), q.get("pembahasan", ""),
                ),
            )


def seed_users(conn):
    now = iso(utc_now())
    # Akun admin/guru selalu dibuat (kredensial dapat diatur lewat variabel lingkungan).
    seed = [(ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, "guru")]
    if DEMO_ON:
        seed.append(("Siswa Demo", "siswa@tka.id", "siswa123", "siswa"))
    for name, email, pw, role in seed:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (name, email, hash_password(pw), role, now),
        )


def seed_kelas(conn):
    """Kelas contoh + penempatan siswa demo."""
    if not DEMO_ON:
        return
    if conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 0:
        conn.execute("INSERT INTO classes (name, created_at) VALUES (?, ?)",
                     ("IX-A", iso(utc_now())))
        conn.execute("INSERT INTO classes (name, created_at) VALUES (?, ?)",
                     ("IX-B", iso(utc_now())))
        conn.commit()
    kela = conn.execute("SELECT id FROM classes WHERE name = 'IX-A'").fetchone()
    if kela:
        emails = ["siswa@tka.id", "aisyah@tka.id", "bagas@tka.id",
                  "citra@tka.id", "dimas@tka.id"]
        for em in emails:
            conn.execute("UPDATE users SET class_id = ? WHERE email = ? AND class_id IS NULL",
                         (kela["id"], em))
        conn.commit()


def seed_schedule_demo(conn):
    """Satu jadwal ujian terbuka (dengan token) untuk mendemokan fitur jadwal."""
    if not DEMO_ON:
        return
    if conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0] > 0:
        return
    pkg = conn.execute("SELECT id FROM packages WHERE kode = 'TRY-SMP-01'").fetchone()
    kela = conn.execute("SELECT id FROM classes WHERE name = 'IX-A'").fetchone()
    if not pkg or not kela:
        return
    now = utc_now()
    conn.execute(
        "INSERT INTO schedules (package_id, class_id, start_at, end_at, token, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (pkg["id"], kela["id"], iso(now - timedelta(days=1)),
         iso(now + timedelta(days=7)), "TRY2026", iso(now)),
    )
    conn.commit()


DEMO_SISWA = [
    ("Aisyah Putri", "aisyah@tka.id", 0.88),
    ("Bagas Pratama", "bagas@tka.id", 0.75),
    ("Citra Lestari", "citra@tka.id", 0.63),
    ("Dimas Saputra", "dimas@tka.id", 0.52),
    ("Eka Wulandari", "eka@tka.id", 0.42),
    ("Fajar Nugroho", "fajar@tka.id", 0.31),
]


def seed_demo_attempts(conn):
    """Buat hasil ujian contoh agar halaman analisis tidak kosong."""
    if not DEMO_ON:
        return
    if conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] > 0:
        return
    rnd = random.Random(20261017)
    now = utc_now()
    users = []
    for name, email, ability in DEMO_SISWA:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, role, created_at)"
                " VALUES (?, ?, ?, 'siswa', ?)",
                (name, email, hash_password("siswa123"), iso(now)),
            )
            user_id = cur.lastrowid
        else:
            user_id = row["id"]
        users.append((user_id, ability))

    packages = conn.execute("SELECT id, durasi FROM packages ORDER BY urutan").fetchall()
    day = 0
    for user_id, ability in users:
        for pkg in packages:
            questions = conn.execute(
                "SELECT id, tipe, opsi_json, kunci FROM questions"
                " WHERE package_id = ? ORDER BY nomor", (pkg["id"],)
            ).fetchall()
            started = now - timedelta(days=12 - day // 2, hours=rnd.randint(1, 6))
            submitted = started + timedelta(minutes=rnd.randint(18, pkg["durasi"] - 2))
            correct = 0
            rows = []
            for q in questions:
                if rnd.random() < ability:
                    ans = q["kunci"]
                    correct += 1
                elif q["tipe"] == "pg":
                    opts = json.loads(q["opsi_json"])
                    letters = [chr(65 + i) for i in range(len(opts))]
                    wrong = [l for l in letters if l != q["kunci"]]
                    ans = rnd.choice(wrong) if wrong else ""
                else:
                    ans = str(rnd.choice([0, 1, 5, 10, 12, 15, 20, 24, 40]))
                rows.append((q["id"], ans))
            total = len(questions)
            score = round(correct / total * 100, 1) if total else 0.0
            cur = conn.execute(
                "INSERT INTO attempts (user_id, package_id, started_at, deadline_at,"
                " submitted_at, status, score, correct_count, total_count)"
                " VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?)",
                (
                    user_id, pkg["id"], iso(started),
                    iso(started + timedelta(minutes=pkg["durasi"])),
                    iso(submitted), score, correct, total,
                ),
            )
            attempt_id = cur.lastrowid
            for q, (qid, ans) in zip(questions, rows):
                is_ok = 1 if grade_answer(q["tipe"], q["kunci"], ans, 0) else 0
                conn.execute(
                    "INSERT INTO answers (attempt_id, question_id, jawaban, benar)"
                    " VALUES (?, ?, ?, ?)", (attempt_id, qid, ans, is_ok),
                )
        day += 1


# ---------------------------------------------------------------------------
# Penilaian
# ---------------------------------------------------------------------------
def grade_answer(tipe, kunci, jawaban, toleransi):
    jawaban = (jawaban or "").strip()
    if not jawaban:
        return False
    if tipe == "pg":
        return jawaban.upper() == (kunci or "").strip().upper()
    # isian angka
    try:
        v = float(jawaban.replace(".", "").replace(",", ".")) if "," in jawaban else float(jawaban)
    except ValueError:
        try:
            v = float(jawaban.replace(",", "."))
        except ValueError:
            return False
    try:
        k = float(str(kunci).replace(",", "."))
    except ValueError:
        return False
    return abs(v - k) <= float(toleransi or 0) + 1e-9


def question_payload(q, with_answer):
    d = {
        "id": q["id"],
        "nomor": q["nomor"],
        "tipe": q["tipe"],
        "kategori": q["kategori"],
        "tingkat": q["tingkat"],
        "stimulus": q["stimulus"],
        "pertanyaan": q["pertanyaan"],
        "opsi": json.loads(q["opsi_json"] or "[]"),
    }
    if with_answer:
        d["kunci"] = q["kunci"]
        d["pembahasan"] = q["pembahasan"]
        d["toleransi"] = q["toleransi"]
    return d


def attempt_result(conn, attempt_id, include_student=False):
    a = conn.execute(
        "SELECT a.*, p.judul, p.mapel, p.kategori AS paket_kategori, u.name, u.email"
        " FROM attempts a JOIN packages p ON p.id = a.package_id"
        " JOIN users u ON u.id = a.user_id WHERE a.id = ?", (attempt_id,)
    ).fetchone()
    if a is None:
        return None
    qs = conn.execute(
        "SELECT * FROM questions WHERE package_id = ? ORDER BY nomor", (a["package_id"],)
    ).fetchall()
    saved = {
        r["question_id"]: r
        for r in conn.execute("SELECT * FROM answers WHERE attempt_id = ?", (attempt_id,))
    }
    items = []
    for q in qs:
        row = saved.get(q["id"])
        items.append({
            **question_payload(q, True),
            "jawaban": row["jawaban"] if row else "",
            "benar": bool(row["benar"]) if row else False,
        })
    cat = {"literasi": [0, 0], "numerasi": [0, 0]}
    for it in items:
        c = cat.setdefault(it["kategori"], [0, 0])
        c[1] += 1
        if it["benar"]:
            c[0] += 1
    kategori = {
        k: round(v[0] / v[1] * 100, 1) if v[1] else None for k, v in cat.items()
    }
    out = {
        "id": a["id"],
        "package_id": a["package_id"],
        "paket": a["judul"],
        "mapel": a["mapel"],
        "status": a["status"],
        "score": a["score"],
        "correct_count": a["correct_count"],
        "total_count": a["total_count"],
        "started_at": a["started_at"],
        "submitted_at": a["submitted_at"],
        "deadline_at": a["deadline_at"],
        "kategori": kategori,
        "questions": items,
    }
    if include_student:
        out["student"] = {"id": a["user_id"], "name": a["name"], "email": a["email"]}
    return out


# ---------------------------------------------------------------------------
# Sinkronisasi Google Sheets
# ---------------------------------------------------------------------------
def sheets_config(conn):
    raw = get_setting(conn, "sheets")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def log_sync(conn, ok, message):
    conn.execute(
        "INSERT INTO sync_log (at, ok, message) VALUES (?, ?, ?)",
        (iso(utc_now()), 1 if ok else 0, message[:500]),
    )
    conn.commit()


def sync_attempt_rows(conn, attempt_ids, cfg=None):
    cfg = cfg or sheets_config(conn)
    if not cfg or not cfg.get("enabled"):
        return {"skipped": True, "reason": "Sinkronisasi Google Sheets belum diaktifkan."}
    client = gsheets.client_from_config(cfg)
    rows = []
    for aid in attempt_ids:
        res = attempt_result(conn, aid, include_student=True)
        if not res or res["status"] != "submitted":
            continue
        dur = ""
        if res["submitted_at"] and res["started_at"]:
            delta = parse_iso(res["submitted_at"]) - parse_iso(res["started_at"])
            dur = max(1, round(delta.total_seconds() / 60))
        lit = res["kategori"].get("literasi")
        num = res["kategori"].get("numerasi")
        rows.append([
            res["submitted_at"], res["student"]["name"], res["student"]["email"],
            res["paket"], res["mapel"], res["score"], res["correct_count"],
            res["total_count"], "" if lit is None else lit,
            "" if num is None else num, dur, res["id"],
        ])
    if not rows:
        return {"rows": 0}
    tab = cfg.get("tab") or SHEET_TAB_DEFAULT
    out = client.sync_rows(tab, SHEET_HEADER, rows)
    return out


def sync_in_background(attempt_id):
    def run():
        try:
            conn = db()
            try:
                sync_attempt_rows(conn, [attempt_id])
                conn.execute("UPDATE attempts SET synced = 1 WHERE id = ?", (attempt_id,))
                conn.commit()
                log_sync(conn, True, f"Hasil ujian #{attempt_id} terkirim ke Google Sheets.")
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001 - kegagalan sync tidak boleh mengganggu ujian
            try:
                conn = db()
                try:
                    log_sync(conn, False, f"Gagal sinkron #{attempt_id}: {e}")
                finally:
                    conn.close()
            except Exception:
                traceback.print_exc()
    t = threading.Thread(target=run, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Handler HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "TKACerdas/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # -- util -------------------------------------------------------------
    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, data: bytes, ctype: str, filename=None, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Body tidak valid.")
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("Body terlalu besar.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("JSON tidak valid.")
        if not isinstance(data, dict):
            raise ValueError("JSON harus berupa objek.")
        return data

    def read_multipart(self):
        """Parser multipart/form-data sederhana (untuk unggah berkas soal)."""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary="?([^";]+)"?', ctype)
        if not m:
            raise ValueError("Unggahan tidak valid (boundary tidak ditemukan).")
        boundary = ("--" + m.group(1)).encode()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Ukuran unggahan tidak valid.")
        if length <= 0:
            raise ValueError("Berkas kosong.")
        if length > 6 * 1024 * 1024:
            raise ValueError("Berkas terlalu besar (maksimal 5 MB).")
        body = self.rfile.read(length)

        fields, file_part = {}, None
        for part in body.split(boundary):
            if not part or part in (b"--", b"--\r\n", b"\r\n"):
                continue
            part = part[2:] if part.startswith(b"\r\n") else part
            head, _, data = part.partition(b"\r\n\r\n")
            if not _:
                continue
            headers = head.decode("utf-8", "replace")
            fm = re.search(r'filename="([^"]*)"', headers)
            nm = re.search(r'name="([^"]*)"', headers)
            payload = data[:-2] if data.endswith(b"\r\n") else data
            if fm and fm.group(1):
                file_part = (fm.group(1), payload)
            elif nm:
                fields[nm.group(1)] = payload.decode("utf-8", "replace").strip()
        return fields, file_part

    def auth_user(self, conn):
        h = self.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            return None
        return conn.execute(
            "SELECT u.id, u.name, u.email, u.role FROM sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (h[7:].strip(),),
        ).fetchone()

    def need_user(self, conn, role=None):
        user = self.auth_user(conn)
        if user is None:
            self.send_json(401, {"error": "Silakan masuk terlebih dahulu."})
            return None
        if role and user["role"] != role:
            self.send_json(403, {"error": "Halaman ini khusus akun guru."})
            return None
        return user

    # -- GET --------------------------------------------------------------
    def do_GET(self):
        conn = None
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                return self.send_json(200, {"ok": True, "app": "TKA Cerdas"})
            if not path.startswith("/api/"):
                return self.serve_static(path)

            conn = db()
            if path == "/api/me":
                user = self.need_user(conn)
                if not user:
                    return
                return self.send_json(200, {"user": dict(user)})

            if path == "/api/packages":
                user = self.need_user(conn)
                if not user:
                    return
                my_class = student_class_id(conn, user["id"])
                kelas_row = (conn.execute("SELECT name FROM classes WHERE id = ?",
                                          (my_class,)).fetchone() if my_class else None)
                now_dt = utc_now()
                pkgs = []
                for p in conn.execute("SELECT * FROM packages WHERE aktif = 1 ORDER BY urutan"):
                    n = conn.execute("SELECT COUNT(*) FROM questions WHERE package_id = ?",
                                     (p["id"],)).fetchone()[0]
                    mine = conn.execute(
                        "SELECT COUNT(*) AS n, MAX(score) AS best FROM attempts"
                        " WHERE user_id = ? AND package_id = ? AND status = 'submitted'",
                        (user["id"], p["id"]),
                    ).fetchone()
                    active = conn.execute(
                        "SELECT id, deadline_at FROM attempts WHERE user_id = ? AND package_id = ?"
                        " AND status = 'in_progress' ORDER BY id DESC LIMIT 1",
                        (user["id"], p["id"]),
                    ).fetchone()
                    sched_list = []
                    for s in applicable_schedules(conn, p["id"], my_class):
                        sched_list.append({
                            "id": s["id"], "class_name": s["class_name"],
                            "start_at": s["start_at"], "end_at": s["end_at"],
                            "state": schedule_state(s, now_dt),
                        })
                    pkgs.append({
                        "id": p["id"], "kode": p["kode"], "judul": p["judul"],
                        "mapel": p["mapel"], "kategori": p["kategori"],
                        "deskripsi": p["deskripsi"], "durasi": p["durasi"],
                        "jumlah_soal": n, "percobaan": mine["n"],
                        "nilai_terbaik": mine["best"],
                        "attempt_id": active["id"] if active else None,
                        "deadline_at": active["deadline_at"] if active else None,
                        "schedules": sched_list,
                    })
                return self.send_json(200, {
                    "packages": pkgs,
                    "class": {"id": my_class, "name": kelas_row["name"] if kelas_row else None},
                })

            m = re.match(r"^/api/attempts/(\d+)$", path)
            if m:
                user = self.need_user(conn)
                if not user:
                    return
                aid = int(m.group(1))
                row = conn.execute("SELECT user_id, status, deadline_at FROM attempts WHERE id = ?",
                                   (aid,)).fetchone()
                if row is None:
                    return self.send_json(404, {"error": "Ujian tidak ditemukan."})
                if row["user_id"] != user["id"] and user["role"] != "guru":
                    return self.send_json(403, {"error": "Anda tidak berhak membuka ujian ini."})
                if row["status"] == "submitted":
                    return self.send_json(200, attempt_result(conn, aid, include_student=True))
                pkg = conn.execute(
                    "SELECT p.* FROM attempts a JOIN packages p ON p.id = a.package_id WHERE a.id = ?",
                    (aid,),
                ).fetchone()
                qs_rows = conn.execute(
                    "SELECT * FROM questions WHERE package_id = ? ORDER BY nomor", (pkg["id"],)
                ).fetchall()
                saved = {
                    r["question_id"]: r["jawaban"]
                    for r in conn.execute("SELECT question_id, jawaban FROM answers WHERE attempt_id = ?", (aid,))
                }
                return self.send_json(200, {
                    "id": aid, "status": "in_progress", "paket": pkg["judul"],
                    "mapel": pkg["mapel"], "durasi": pkg["durasi"],
                    "deadline_at": row["deadline_at"], "server_time": iso(utc_now()),
                    "questions": [
                        {**question_payload(q, False), "jawaban": saved.get(q["id"], "")}
                        for q in qs_rows
                    ],
                })

            if path == "/api/my-results":
                user = self.need_user(conn)
                if not user:
                    return
                rows = conn.execute(
                    "SELECT a.id, a.score, a.correct_count, a.total_count, a.submitted_at,"
                    " a.started_at, p.judul, p.mapel FROM attempts a"
                    " JOIN packages p ON p.id = a.package_id"
                    " WHERE a.user_id = ? AND a.status = 'submitted'"
                    " ORDER BY a.submitted_at DESC", (user["id"],),
                ).fetchall()
                return self.send_json(200, {"results": [dict(r) for r in rows]})

            if path == "/api/analytics":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                pid = (qs.get("package_id") or [""])[0]
                cid = (qs.get("class_id") or [""])[0]
                return self.send_json(200, analytics(conn, pid, cid))

            if path == "/api/classes":
                user = self.need_user(conn)
                if not user:
                    return
                rows = conn.execute(
                    "SELECT c.id, c.name, COUNT(u.id) AS anggota FROM classes c"
                    " LEFT JOIN users u ON u.class_id = c.id AND u.role = 'siswa'"
                    " GROUP BY c.id ORDER BY c.name")
                return self.send_json(200, {"classes": [dict(r) for r in rows]})

            if path == "/api/students":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                rows = conn.execute(
                    "SELECT u.id, u.name, u.email, u.class_id, c.name AS kelas,"
                    " (SELECT COUNT(*) FROM attempts a WHERE a.user_id = u.id"
                    "  AND a.status = 'submitted') AS jumlah_ujian"
                    " FROM users u LEFT JOIN classes c ON c.id = u.class_id"
                    " WHERE u.role = 'siswa' ORDER BY c.name, u.name")
                return self.send_json(200, {"students": [dict(r) for r in rows]})

            if path == "/api/schedules":
                user = self.need_user(conn)
                if not user:
                    return
                now_dt = utc_now()
                if user["role"] == "guru":
                    rows = conn.execute(
                        "SELECT s.*, p.judul, p.kode, c.name AS class_name,"
                        " (SELECT COUNT(*) FROM attempts a WHERE a.schedule_id = s.id"
                        "  AND a.status = 'submitted') AS peserta"
                        " FROM schedules s JOIN packages p ON p.id = s.package_id"
                        " LEFT JOIN classes c ON c.id = s.class_id"
                        " ORDER BY s.start_at DESC")
                    out = []
                    for r in rows:
                        d = dict(r)
                        d["state"] = schedule_state(r, now_dt)
                        out.append(d)
                    return self.send_json(200, {"schedules": out})
                # siswa: hanya jadwal untuk kelasnya
                kelas_id = student_class_id(conn, user["id"])
                rows = conn.execute(
                    "SELECT s.id, s.package_id, s.start_at, s.end_at, c.name AS class_name,"
                    " p.judul FROM schedules s JOIN packages p ON p.id = s.package_id"
                    " LEFT JOIN classes c ON c.id = s.class_id"
                    " WHERE (s.class_id IS NULL OR s.class_id = ?)"
                    " ORDER BY s.start_at DESC", (kelas_id if kelas_id is not None else -1,))
                out = []
                for r in rows:
                    d = dict(r)
                    d["state"] = schedule_state(r, now_dt)
                    out.append(d)
                return self.send_json(200, {"schedules": out})

            if path == "/api/report/student" or path.startswith("/api/report/student/"):
                user = self.need_user(conn)
                if not user:
                    return
                m = re.match(r"^/api/report/student/(\d+)$", path)
                if not m:
                    return self.send_json(400, {"error": "ID hasil ujian tidak valid."})
                aid = int(m.group(1))
                owner = conn.execute("SELECT user_id, status FROM attempts WHERE id = ?",
                                     (aid,)).fetchone()
                if owner is None:
                    return self.send_json(404, {"error": "Hasil ujian tidak ditemukan."})
                if owner["user_id"] != user["id"] and user["role"] != "guru":
                    return self.send_json(403, {"error": "Anda tidak berhak membuka laporan ini."})
                if owner["status"] != "submitted":
                    return self.send_json(409, {"error": "Ujian belum dikumpulkan."})
                res = attempt_result(conn, aid, include_student=True)
                kkm = float(get_setting(conn, "kkm", KKM_DEFAULT))
                sekolah = get_setting(conn, "school_name", "SMP")
                pdf_bytes = reports.student_report(res, kkm=kkm, school_name=sekolah)
                safe = re.sub(r"[^A-Za-z0-9._-]+", "-", res["student"]["name"])
                return self.send_file(pdf_bytes, "application/pdf",
                                      filename=f"laporan-{safe}-{aid}.pdf")

            if path == "/api/report/class":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                pid = (qs.get("package_id") or [""])[0]
                cid = (qs.get("class_id") or [""])[0]
                data = analytics(conn, pid, cid)
                kkm = float(get_setting(conn, "kkm", KKM_DEFAULT))
                sekolah = get_setting(conn, "school_name", "SMP")
                kelas = ""
                if cid:
                    row = conn.execute("SELECT name FROM classes WHERE id = ?", (cid,)).fetchone()
                    kelas = row["name"] if row else ""
                judul = next((p["judul"] for p in data["packages"] if p["id"] == data["package_id"]), "")
                pdf_bytes = reports.class_report(data, kkm=kkm, school_name=sekolah,
                                                 kelas=kelas, judul_paket=judul)
                return self.send_file(pdf_bytes, "application/pdf",
                                      filename=f"rekap-kelas-{data['package_id']}.pdf")

            if path == "/api/report/attendance":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                pid = (qs.get("package_id") or [""])[0]
                cid = (qs.get("class_id") or [""])[0]
                data = analytics(conn, pid, cid)
                kkm = float(get_setting(conn, "kkm", KKM_DEFAULT))
                sekolah = get_setting(conn, "school_name", "SMP")
                judul = next((p["judul"] for p in data["packages"] if p["id"] == data["package_id"]), "")
                rows = [(a["name"], a["email"], a["kelas"],
                         a["nilai"], "Tuntas" if (a["nilai"] or 0) >= kkm else
                         ("Belum" if a["nilai"] is not None else "Tidak hadir"))
                        for a in data["attendance"]]
                pdf_bytes = reports.attendance_report(rows, kkm, sekolah, judul)
                return self.send_file(pdf_bytes, "application/pdf",
                                      filename=f"kehadiran-{data['package_id']}.pdf")

            if path == "/api/attendance.csv":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                pid = (qs.get("package_id") or [""])[0]
                cid = (qs.get("class_id") or [""])[0]
                data = analytics(conn, pid, cid)
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["Nama Siswa", "Email", "Kelas", "Nilai", "Keterangan"])
                for a in data["attendance"]:
                    w.writerow([a["name"], a["email"], a["kelas"] or "",
                                "" if a["nilai"] is None else a["nilai"], a["status"]])
                body = "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")
                return self.send_file(body, "text/csv; charset=utf-8",
                                      filename=f"kehadiran-{data['package_id']}.csv")

            if path == "/api/template.xlsx":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                return self.send_file(office.build_template_xlsx(),
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                      filename="template-impor-soal.xlsx")

            if path == "/api/template.txt":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                teks = (
                    "TEMPLATE SOAL TKA (format teks / Word)\n"
                    "Salin format di bawah, lalu simpan sebagai .docx atau .txt.\n\n"
                    "1. Hasil dari 12 x 8 adalah ....\n"
                    "A. 86\nB. 96\nC. 106\nD. 116\n"
                    "Kunci: B\n"
                    "Kategori: numerasi\n"
                    "Tingkat: mudah\n"
                    "Pembahasan: 12 x 8 = 96.\n\n"
                    "2. Keliling persegi dengan sisi 9 cm adalah ... cm.\n"
                    "Kunci: 36\nKategori: numerasi\nTingkat: sedang\n"
                    "Pembahasan: Keliling = 4 x 9 = 36 cm.\n\n"
                    "3. Bacalah teks berikut: \"Banjir terjadi karena saluran air tersumbat sampah.\"\n"
                    "Ide pokok teks tersebut adalah ....\n"
                    "A. Penyebab banjir\nB. Cara membuat sampah\n"
                    "C. Jenis saluran air\nD. Waktu banjir\n"
                    "Kunci: A\nKategori: literasi\nTingkat: sedang\n"
                )
                return self.send_file(teks.encode("utf-8"), "text/plain; charset=utf-8",
                                      filename="template-soal.txt")

            m = re.match(r"^/api/analytics/attempt/(\d+)$", path)
            if m:
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                res = attempt_result(conn, int(m.group(1)), include_student=True)
                if res is None:
                    return self.send_json(404, {"error": "Hasil ujian tidak ditemukan."})
                return self.send_json(200, res)

            if path == "/api/questions":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                pid = (qs.get("package_id") or ["0"])[0]
                rows = conn.execute(
                    "SELECT * FROM questions WHERE package_id = ? ORDER BY nomor", (pid,)
                ).fetchall()
                return self.send_json(200, {"questions": [question_payload(q, True) for q in rows]})

            if path == "/api/settings":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                cfg = sheets_config(conn) or {}
                sa = cfg.get("service_account") or {}
                logs = [dict(r) for r in conn.execute(
                    "SELECT at, ok, message FROM sync_log ORDER BY id DESC LIMIT 12"
                )]
                pending = conn.execute(
                    "SELECT COUNT(*) FROM attempts WHERE status='submitted' AND synced=0"
                ).fetchone()[0]
                return self.send_json(200, {
                    "sheets": {
                        "enabled": bool(cfg.get("enabled")),
                        "sheet_id": cfg.get("sheet_id", ""),
                        "tab": cfg.get("tab", SHEET_TAB_DEFAULT),
                        "client_email": sa.get("client_email", ""),
                        "has_key": bool(sa.get("private_key")),
                    },
                    "kkm": float(get_setting(conn, "kkm", KKM_DEFAULT)),
                    "school_name": get_setting(conn, "school_name", "SMP Negeri 1"),
                    "guru_code": get_setting(conn, "guru_code", GURU_CODE_DEFAULT),
                    "logs": logs,
                    "pending_sync": pending,
                })

            if path == "/api/backup":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                return self.backup(conn)

            if path == "/api/export.csv":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                return self.export_csv(conn)

            return self.send_json(404, {"error": "Endpoint tidak ditemukan."})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "Terjadi kesalahan di server."})
        finally:
            if conn is not None:
                conn.close()

    # -- POST -------------------------------------------------------------
    def do_POST(self):
        conn = None
        try:
            path = urllib.parse.urlparse(self.path).path
            if not path.startswith("/api/"):
                return self.send_json(404, {"error": "Endpoint tidak ditemukan."})
            conn = db()

            if path == "/api/register":
                d = self.read_json()
                name = str(d.get("name", "")).strip()
                email = str(d.get("email", "")).strip().lower()
                pw = str(d.get("password", ""))
                role = str(d.get("role", "siswa")).strip().lower()
                code = str(d.get("guru_code", "")).strip()
                if len(name) < 2 or len(name) > 60:
                    return self.send_json(400, {"error": "Nama harus 2-60 karakter."})
                if not EMAIL_RE.match(email) or len(email) > 120:
                    return self.send_json(400, {"error": "Format email tidak valid."})
                if len(pw) < 6:
                    return self.send_json(400, {"error": "Password minimal 6 karakter."})
                if role not in ("siswa", "guru"):
                    return self.send_json(400, {"error": "Peran tidak valid."})
                if role == "guru":
                    expected = get_setting(conn, "guru_code", GURU_CODE_DEFAULT)
                    if code != expected:
                        return self.send_json(403, {"error": "Kode akses guru salah."})
                try:
                    cur = conn.execute(
                        "INSERT INTO users (name, email, password_hash, role, created_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (name, email, hash_password(pw), role, iso(utc_now())),
                    )
                except sqlite3.IntegrityError:
                    return self.send_json(409, {"error": "Email sudah terdaftar. Silakan masuk."})
                token = secrets.token_hex(32)
                conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                             (token, cur.lastrowid, iso(utc_now())))
                conn.commit()
                return self.send_json(201, {
                    "token": token,
                    "user": {"id": cur.lastrowid, "name": name, "email": email, "role": role},
                })

            if path == "/api/login":
                d = self.read_json()
                email = str(d.get("email", "")).strip().lower()
                pw = str(d.get("password", ""))
                row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if row is None or not verify_password(pw, row["password_hash"]):
                    return self.send_json(401, {"error": "Email atau password salah."})
                token = secrets.token_hex(32)
                conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                             (token, row["id"], iso(utc_now())))
                conn.commit()
                return self.send_json(200, {
                    "token": token,
                    "user": {"id": row["id"], "name": row["name"], "email": row["email"],
                             "role": row["role"]},
                })

            if path == "/api/logout":
                h = self.headers.get("Authorization", "")
                if h.startswith("Bearer "):
                    conn.execute("DELETE FROM sessions WHERE token = ?", (h[7:].strip(),))
                    conn.commit()
                return self.send_json(200, {"ok": True})

            if path == "/api/attempts":
                user = self.need_user(conn)
                if not user:
                    return
                if user["role"] != "siswa":
                    return self.send_json(403, {"error": "Hanya akun siswa yang dapat mengerjakan ujian."})
                d = self.read_json()
                try:
                    pid = int(d.get("package_id", 0))
                except (TypeError, ValueError):
                    return self.send_json(400, {"error": "Paket tidak valid."})
                pkg = conn.execute("SELECT * FROM packages WHERE id = ? AND aktif = 1", (pid,)).fetchone()
                if pkg is None:
                    return self.send_json(404, {"error": "Paket ujian tidak ditemukan."})
                existing = conn.execute(
                    "SELECT id, deadline_at FROM attempts WHERE user_id = ? AND package_id = ?"
                    " AND status = 'in_progress' ORDER BY id DESC LIMIT 1",
                    (user["id"], pid),
                ).fetchone()
                now = utc_now()
                if existing:
                    if parse_iso(existing["deadline_at"]) + timedelta(seconds=GRACE_SECONDS) >= now:
                        return self.send_json(200, {"attempt_id": existing["id"], "resumed": True})
                    close_stale_attempt(conn, existing["id"])

                # ---- pemeriksaan jadwal & token kelas ----
                started = utc_now()
                kelas_id = student_class_id(conn, user["id"])
                scheds = applicable_schedules(conn, pid, kelas_id)
                sched = None
                for s in scheds:
                    if schedule_state(s, started) == "terbuka":
                        sched = s
                        break

                def sched_info(s, with_token=False):
                    d = {
                        "id": s["id"], "start_at": s["start_at"], "end_at": s["end_at"],
                        "class_name": s["class_name"], "state": schedule_state(s, started),
                    }
                    if with_token:
                        d["token"] = s["token"]
                    return d

                if sched is not None:
                    token_in = str(d.get("token", "")).strip().upper()
                    if token_in != sched["token"].upper():
                        return self.send_json(403, {
                            "error": ("Token ujian wajib diisi. Mintalah token dari guru pengawas."
                                      if not token_in else "Token ujian salah. Periksa kembali."),
                            "need_token": True,
                            "schedule": sched_info(sched),
                        })
                elif scheds:
                    s0 = next((s for s in scheds if schedule_state(s, started) == "belum_mulai"), scheds[-1])
                    st = schedule_state(s0, started)
                    msg = ("Ujian ini dijadwalkan mulai "
                           + s0["start_at"][:16].replace("T", " ") + " UTC."
                           if st == "belum_mulai"
                           else "Jadwal ujian untuk kelas ini sudah berakhir.")
                    return self.send_json(403, {"error": msg, "schedule": sched_info(s0)})

                deadline = started + timedelta(minutes=pkg["durasi"])
                if sched is not None:
                    sched_end = parse_iso(sched["end_at"])
                    if sched_end < deadline:
                        deadline = sched_end
                cur = conn.execute(
                    "INSERT INTO attempts (user_id, package_id, started_at, deadline_at,"
                    " total_count, schedule_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (user["id"], pid, iso(started), iso(deadline),
                     conn.execute("SELECT COUNT(*) FROM questions WHERE package_id = ?",
                                  (pid,)).fetchone()[0],
                     sched["id"] if sched is not None else None),
                )
                conn.commit()
                return self.send_json(201, {"attempt_id": cur.lastrowid, "resumed": False})

            m = re.match(r"^/api/attempts/(\d+)/answer$", path)
            if m:
                user = self.need_user(conn)
                if not user:
                    return
                aid = int(m.group(1))
                d = self.read_json()
                att = conn.execute("SELECT * FROM attempts WHERE id = ?", (aid,)).fetchone()
                if att is None:
                    return self.send_json(404, {"error": "Ujian tidak ditemukan."})
                if att["user_id"] != user["id"]:
                    return self.send_json(403, {"error": "Ujian ini bukan milik Anda."})
                if att["status"] != "in_progress":
                    return self.send_json(409, {"error": "Ujian sudah dikumpulkan."})
                if utc_now() > parse_iso(att["deadline_at"]) + timedelta(seconds=GRACE_SECONDS):
                    return self.send_json(409, {"error": "Waktu ujian sudah habis."})
                try:
                    qid = int(d.get("question_id", 0))
                except (TypeError, ValueError):
                    return self.send_json(400, {"error": "Soal tidak valid."})
                q = conn.execute(
                    "SELECT * FROM questions WHERE id = ? AND package_id = ?",
                    (qid, att["package_id"]),
                ).fetchone()
                if q is None:
                    return self.send_json(404, {"error": "Soal tidak ditemukan pada paket ini."})
                ans = str(d.get("answer", ""))[:200].strip()
                ok = 1 if grade_answer(q["tipe"], q["kunci"], ans, q["toleransi"]) else 0
                conn.execute(
                    "INSERT INTO answers (attempt_id, question_id, jawaban, benar)"
                    " VALUES (?, ?, ?, ?)"
                    " ON CONFLICT(attempt_id, question_id)"
                    " DO UPDATE SET jawaban = excluded.jawaban, benar = excluded.benar",
                    (aid, qid, ans, ok),
                )
                conn.commit()
                return self.send_json(200, {"saved": True})

            m = re.match(r"^/api/attempts/(\d+)/submit$", path)
            if m:
                user = self.need_user(conn)
                if not user:
                    return
                aid = int(m.group(1))
                att = conn.execute("SELECT * FROM attempts WHERE id = ?", (aid,)).fetchone()
                if att is None:
                    return self.send_json(404, {"error": "Ujian tidak ditemukan."})
                if att["user_id"] != user["id"]:
                    return self.send_json(403, {"error": "Ujian ini bukan milik Anda."})
                if att["status"] == "submitted":
                    return self.send_json(200, attempt_result(conn, aid))
                finalize_attempt(conn, aid)
                res = attempt_result(conn, aid)
                sync_in_background(aid)
                return self.send_json(200, res)

            if path == "/api/settings":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                d = self.read_json()
                cfg = sheets_config(conn) or {}
                if "sheet_id" in d:
                    cfg["sheet_id"] = str(d["sheet_id"]).strip()
                if "tab" in d:
                    cfg["tab"] = (str(d["tab"]).strip() or SHEET_TAB_DEFAULT)[:60]
                if "enabled" in d:
                    cfg["enabled"] = bool(d["enabled"])
                sa_text = str(d.get("service_account_json", "")).strip()
                if sa_text:
                    try:
                        cfg["service_account"] = json.loads(sa_text)
                    except json.JSONDecodeError:
                        return self.send_json(400, {"error": "JSON kredensial tidak valid."})
                if "kkm" in d:
                    try:
                        kkm = float(d["kkm"])
                    except (TypeError, ValueError):
                        return self.send_json(400, {"error": "KKM tidak valid."})
                    if not 0 <= kkm <= 100:
                        return self.send_json(400, {"error": "KKM harus antara 0 dan 100."})
                    set_setting(conn, "kkm", str(kkm))
                if "school_name" in d:
                    nama = str(d["school_name"]).strip()
                    if len(nama) > 80:
                        return self.send_json(400, {"error": "Nama sekolah maksimal 80 karakter."})
                    set_setting(conn, "school_name", nama or "SMP")
                set_setting(conn, "sheets", json.dumps(cfg, ensure_ascii=False))
                conn.commit()
                return self.send_json(200, {"ok": True})

            if path == "/api/settings/test-sheets":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                d = self.read_json()
                cfg = sheets_config(conn) or {}
                if d.get("service_account_json"):
                    try:
                        cfg = {**cfg, "service_account": json.loads(d["service_account_json"])}
                    except json.JSONDecodeError:
                        return self.send_json(400, {"error": "JSON kredensial tidak valid."})
                if d.get("sheet_id"):
                    cfg["sheet_id"] = str(d["sheet_id"]).strip()
                try:
                    client = gsheets.client_from_config(cfg)
                    info = client.info()
                except gsheets.SheetsError as e:
                    log_sync(conn, False, f"Uji koneksi gagal: {e}")
                    return self.send_json(400, {"error": str(e)})
                log_sync(conn, True, f"Uji koneksi berhasil ke spreadsheet \"{info['title']}\".")
                return self.send_json(200, {"ok": True, **info,
                                            "client_email": cfg["service_account"].get("client_email", "")
                                            if isinstance(cfg.get("service_account"), dict) else ""})

            if path == "/api/classes":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                d = self.read_json()
                name = str(d.get("name", "")).strip()
                if not 2 <= len(name) <= 40:
                    return self.send_json(400, {"error": "Nama kelas harus 2-40 karakter."})
                try:
                    cur = conn.execute("INSERT INTO classes (name, created_at) VALUES (?, ?)",
                                       (name, iso(utc_now())))
                except sqlite3.IntegrityError:
                    return self.send_json(409, {"error": "Nama kelas sudah ada."})
                conn.commit()
                return self.send_json(201, {"id": cur.lastrowid, "name": name})

            if path == "/api/classes/assign":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                d = self.read_json()
                try:
                    uid = int(d.get("user_id", 0))
                except (TypeError, ValueError):
                    return self.send_json(400, {"error": "Siswa tidak valid."})
                cid = d.get("class_id")
                if cid not in (None, "", 0):
                    try:
                        cid = int(cid)
                    except (TypeError, ValueError):
                        return self.send_json(400, {"error": "Kelas tidak valid."})
                    if not conn.execute("SELECT 1 FROM classes WHERE id = ?", (cid,)).fetchone():
                        return self.send_json(404, {"error": "Kelas tidak ditemukan."})
                else:
                    cid = None
                cur = conn.execute("UPDATE users SET class_id = ? WHERE id = ? AND role = 'siswa'",
                                   (cid, uid))
                conn.commit()
                if cur.rowcount == 0:
                    return self.send_json(404, {"error": "Siswa tidak ditemukan."})
                return self.send_json(200, {"ok": True})

            if path == "/api/schedules":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                d = self.read_json()
                try:
                    pid = int(d.get("package_id", 0))
                except (TypeError, ValueError):
                    return self.send_json(400, {"error": "Paket tidak valid."})
                if not conn.execute("SELECT 1 FROM packages WHERE id = ?", (pid,)).fetchone():
                    return self.send_json(404, {"error": "Paket tidak ditemukan."})
                cid = d.get("class_id")
                if cid in ("", 0, "0", None):
                    cid = None
                else:
                    try:
                        cid = int(cid)
                    except (TypeError, ValueError):
                        return self.send_json(400, {"error": "Kelas tidak valid."})
                    if not conn.execute("SELECT 1 FROM classes WHERE id = ?", (cid,)).fetchone():
                        return self.send_json(404, {"error": "Kelas tidak ditemukan."})
                start_raw = str(d.get("start_at", "")).strip()
                end_raw = str(d.get("end_at", "")).strip()
                try:
                    start = parse_iso(start_raw) if start_raw else None
                    end = parse_iso(end_raw) if end_raw else None
                except Exception:
                    start = end = None
                if not start_raw or not end_raw or start is None or end is None:
                    return self.send_json(400, {"error": "Waktu mulai dan selesai wajib diisi."})
                if end <= start:
                    return self.send_json(400, {"error": "Waktu selesai harus setelah waktu mulai."})
                token = str(d.get("token", "")).strip().upper()
                if not token:
                    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                    token = "".join(secrets.choice(alphabet) for _ in range(6))
                if not re.fullmatch(r"[A-Z0-9]{4,12}", token):
                    return self.send_json(400, {"error": "Token 4-12 karakter, huruf/angka."})
                cur = conn.execute(
                    "INSERT INTO schedules (package_id, class_id, start_at, end_at, token, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, cid, iso(start), iso(end), token, iso(utc_now())))
                conn.commit()
                return self.send_json(201, {"id": cur.lastrowid, "token": token})

            m = re.match(r"^/api/schedules/(\d+)/token$", path)
            if m and self.command == "POST":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                sid = int(m.group(1))
                alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                token = "".join(secrets.choice(alphabet) for _ in range(6))
                cur = conn.execute("UPDATE schedules SET token = ? WHERE id = ?", (token, sid))
                conn.commit()
                if cur.rowcount == 0:
                    return self.send_json(404, {"error": "Jadwal tidak ditemukan."})
                return self.send_json(200, {"token": token})

            if path == "/api/import/questions":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                fields, file_part = self.read_multipart()
                if file_part is None:
                    return self.send_json(400, {"error": "Berkas soal belum dipilih."})
                fname, data = file_part
                try:
                    pid = int(fields.get("package_id", "0"))
                except (TypeError, ValueError):
                    return self.send_json(400, {"error": "Paket tujuan tidak valid."})
                pkg = conn.execute("SELECT * FROM packages WHERE id = ?", (pid,)).fetchone()
                if pkg is None:
                    return self.send_json(404, {"error": "Paket tujuan tidak ditemukan."})
                default_kat = pkg["kategori"] if pkg["kategori"] in ("literasi", "numerasi") else "numerasi"
                try:
                    qs, errs, info = office.parse_file(fname, data, default_kat)
                except office.ImportError_ as e:
                    return self.send_json(400, {"error": str(e)})
                if not qs:
                    return self.send_json(400, {
                        "error": "Tidak ada soal yang dapat dibaca dari berkas ini.",
                        "errors": errs, "info": info,
                    })
                if fields.get("mode", "preview") != "import":
                    return self.send_json(200, {
                        "preview": True, "total": len(qs), "questions": qs[:60],
                        "errors": errs, "info": info, "package": pkg["judul"],
                    })
                next_no = (conn.execute(
                    "SELECT COALESCE(MAX(nomor), 0) FROM questions WHERE package_id = ?",
                    (pid,)).fetchone()[0]) + 1
                for q in qs:
                    conn.execute(
                        "INSERT INTO questions (package_id, nomor, tipe, kategori, tingkat,"
                        " stimulus, pertanyaan, opsi_json, kunci, toleransi, pembahasan)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (pid, next_no, q["tipe"], q["kategori"], q["tingkat"],
                         q["stimulus"], q["pertanyaan"],
                         json.dumps(q["opsi"], ensure_ascii=False),
                         q["kunci"], float(q.get("toleransi", 0)),
                         q.get("pembahasan", "")),
                    )
                    next_no += 1
                conn.commit()
                return self.send_json(201, {
                    "imported": len(qs), "errors": errs, "info": info,
                    "total_sekarang": conn.execute(
                        "SELECT COUNT(*) FROM questions WHERE package_id = ?", (pid,)
                    ).fetchone()[0],
                })

            if path == "/api/sync/backfill":
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                ids = [r[0] for r in conn.execute(
                    "SELECT id FROM attempts WHERE status='submitted' AND synced=0 ORDER BY id"
                )]
                if not ids:
                    return self.send_json(200, {"rows": 0, "message": "Tidak ada data yang perlu disinkronkan."})
                try:
                    out = sync_attempt_rows(conn, ids)
                except gsheets.SheetsError as e:
                    log_sync(conn, False, f"Sinkronisasi massal gagal: {e}")
                    return self.send_json(400, {"error": str(e)})
                conn.executemany("UPDATE attempts SET synced = 1 WHERE id = ?", [(i,) for i in ids])
                conn.commit()
                log_sync(conn, True, f"Sinkronisasi massal: {out.get('rows', 0)} baris terkirim.")
                return self.send_json(200, {"rows": out.get("rows", 0)})

            return self.send_json(404, {"error": "Endpoint tidak ditemukan."})
        except ValueError as e:
            self.send_json(400, {"error": str(e)})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "Terjadi kesalahan di server."})
        finally:
            if conn is not None:
                conn.close()

    # -- DELETE -----------------------------------------------------------
    def do_DELETE(self):
        conn = None
        try:
            path = urllib.parse.urlparse(self.path).path
            conn = db()
            m = re.match(r"^/api/schedules/(\d+)$", path)
            if m:
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                conn.execute("DELETE FROM schedules WHERE id = ?", (int(m.group(1)),))
                conn.commit()
                return self.send_json(200, {"ok": True})

            m = re.match(r"^/api/classes/(\d+)$", path)
            if m:
                user = self.need_user(conn, role="guru")
                if not user:
                    return
                cid = int(m.group(1))
                conn.execute("UPDATE users SET class_id = NULL WHERE class_id = ?", (cid,))
                conn.execute("DELETE FROM classes WHERE id = ?", (cid,))
                conn.commit()
                return self.send_json(200, {"ok": True})

            m = re.match(r"^/api/analytics/attempt/(\d+)$", path)
            if not m:
                return self.send_json(404, {"error": "Endpoint tidak ditemukan."})
            user = self.need_user(conn, role="guru")
            if not user:
                return
            conn.execute("DELETE FROM attempts WHERE id = ?", (int(m.group(1)),))
            conn.commit()
            return self.send_json(200, {"ok": True})
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "Terjadi kesalahan di server."})
        finally:
            if conn is not None:
                conn.close()

    # -- unduhan ----------------------------------------------------------
    def backup(self, conn):
        data = {}
        for table in ("users", "packages", "questions", "attempts", "answers", "settings"):
            data[table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
        for u in data["users"]:
            u.pop("password_hash", None)  # jangan ekspor hash password
        payload = json.dumps({
            "app": "TKA Cerdas", "version": 1,
            "exported_at": iso(utc_now()), "data": data,
        }, ensure_ascii=False, indent=1).encode("utf-8")
        name = "backup-tka-" + utc_now().strftime("%Y%m%d-%H%M") + ".json"
        self.send_file(payload, "application/json; charset=utf-8", filename=name)

    def export_csv(self, conn):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Waktu Kumpul", "Nama Siswa", "Email", "Paket", "Mapel", "Skor",
                    "Benar", "Total", "Literasi (%)", "Numerasi (%)"])
        rows = conn.execute(
            "SELECT a.id, a.score, a.correct_count, a.total_count, a.submitted_at,"
            " u.name, u.email, p.judul, p.mapel FROM attempts a"
            " JOIN users u ON u.id = a.user_id JOIN packages p ON p.id = a.package_id"
            " WHERE a.status = 'submitted' ORDER BY a.submitted_at DESC"
        ).fetchall()
        for r in rows:
            res = attempt_result(conn, r["id"])
            lit = res["kategori"].get("literasi")
            num = res["kategori"].get("numerasi")
            w.writerow([r["submitted_at"], r["name"], r["email"], r["judul"], r["mapel"],
                        r["score"], r["correct_count"], r["total_count"],
                        "" if lit is None else lit, "" if num is None else num])
        body = "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")
        self.send_file(body, "text/csv; charset=utf-8",
                       filename="hasil-tka-" + utc_now().strftime("%Y%m%d") + ".csv")

    # -- statis -----------------------------------------------------------
    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        safe = os.path.realpath(os.path.join(PUBLIC_DIR, path.lstrip("/")))
        if not safe.startswith(PUBLIC_DIR + os.sep) or not os.path.isfile(safe):
            return self.send_json(404, {"error": "Tidak ditemukan."})
        ext = os.path.splitext(safe)[1].lower()
        try:
            with open(safe, "rb") as f:
                body = f.read()
        except OSError:
            return self.send_json(500, {"error": "Gagal membaca file."})
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


# ---------------------------------------------------------------------------
# Logika ujian & analisis
# ---------------------------------------------------------------------------
def finalize_attempt(conn, attempt_id):
    att = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    qs = conn.execute("SELECT id FROM questions WHERE package_id = ?",
                      (att["package_id"],)).fetchall()
    total = len(qs)
    saved = {
        r["question_id"]: r["benar"]
        for r in conn.execute("SELECT question_id, benar FROM answers WHERE attempt_id = ?",
                              (attempt_id,))
    }
    correct = sum(1 for q in qs if saved.get(q["id"]))
    score = round(correct / total * 100, 1) if total else 0.0
    conn.execute(
        "UPDATE attempts SET status='submitted', submitted_at=?, score=?,"
        " correct_count=?, total_count=? WHERE id=?",
        (iso(utc_now()), score, correct, total, attempt_id),
    )
    conn.commit()
    return score


def close_stale_attempt(conn, attempt_id):
    """Ujian yang ditinggalkan melewati batas waktu tetap dinilai."""
    att = conn.execute("SELECT status FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if att and att["status"] == "in_progress":
        finalize_attempt(conn, attempt_id)
        sync_in_background(attempt_id)


def student_class_id(conn, user_id):
    row = conn.execute("SELECT class_id FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["class_id"] if row else None


def applicable_schedules(conn, package_id, class_id):
    return conn.execute(
        "SELECT s.*, c.name AS class_name FROM schedules s"
        " LEFT JOIN classes c ON c.id = s.class_id"
        " WHERE s.package_id = ? AND (s.class_id IS NULL OR s.class_id = ?)"
        " ORDER BY s.start_at",
        (package_id, class_id if class_id is not None else -1),
    ).fetchall()


def schedule_state(s, now):
    if now < parse_iso(s["start_at"]):
        return "belum_mulai"
    if now > parse_iso(s["end_at"]):
        return "berakhir"
    return "terbuka"


def analytics(conn, package_id, class_id=None):
    kkm = float(get_setting(conn, "kkm", KKM_DEFAULT))
    pkgs = [dict(r) for r in conn.execute("SELECT id, judul, mapel, kategori FROM packages ORDER BY urutan")]
    try:
        pid = int(package_id) if package_id else (pkgs[0]["id"] if pkgs else 0)
    except ValueError:
        pid = pkgs[0]["id"] if pkgs else 0
    try:
        cid = int(class_id) if class_id else None
    except (TypeError, ValueError):
        cid = None

    where = "a.package_id = ? AND a.status = 'submitted'"
    args = [pid]
    if cid:
        where += " AND u.class_id = ?"
        args.append(cid)
    attempts = conn.execute(
        "SELECT a.id, a.score, a.correct_count, a.total_count, a.started_at, a.submitted_at,"
        " u.name, u.email, u.class_id FROM attempts a JOIN users u ON u.id = a.user_id"
        f" WHERE {where}"
        " ORDER BY a.score DESC, a.submitted_at ASC", args,
    ).fetchall()
    scores = [a["score"] for a in attempts]
    n = len(scores)
    stats = {
        "peserta": n,
        "rata_rata": round(sum(scores) / n, 1) if n else None,
        "tertinggi": max(scores) if n else None,
        "terendah": min(scores) if n else None,
        "tuntas": sum(1 for s in scores if s >= kkm),
        "persen_tuntas": round(sum(1 for s in scores if s >= kkm) / n * 100, 1) if n else None,
        "kkm": kkm,
    }
    buckets = [("0–59", 0, 59.99), ("60–69", 60, 69.99), ("70–79", 70, 79.99),
               ("80–89", 80, 89.99), ("90–100", 90, 100)]
    distribusi = [
        {"label": lbl, "jumlah": sum(1 for s in scores if lo <= s <= hi)}
        for lbl, lo, hi in buckets
    ]

    id_list = [a["id"] for a in attempts]
    per_question = []
    if id_list:
        ph = ",".join("?" * len(id_list))
        qs = conn.execute("SELECT * FROM questions WHERE package_id = ? ORDER BY nomor", (pid,)).fetchall()
        dist = {}
        for r in conn.execute(
            f"SELECT question_id, jawaban, COUNT(*) AS n FROM answers"
            f" WHERE attempt_id IN ({ph}) GROUP BY question_id, jawaban", id_list,
        ):
            dist.setdefault(r["question_id"], {})[(r["jawaban"] or "").upper()] = r["n"]
        benar_map = {
            r["question_id"]: r["n"]
            for r in conn.execute(
                f"SELECT question_id, SUM(benar) AS n FROM answers"
                f" WHERE attempt_id IN ({ph}) GROUP BY question_id", id_list,
            )
        }
        for q in qs:
            jumlah_benar = benar_map.get(q["id"], 0)
            pct = round(jumlah_benar / n * 100, 1) if n else 0
            if pct >= 70:
                label = "mudah"
            elif pct >= 40:
                label = "sedang"
            else:
                label = "sulit"
            d = dist.get(q["id"], {})
            opsi = json.loads(q["opsi_json"] or "[]")
            distribusi_opsi = []
            for i, _teks in enumerate(opsi):
                huruf = chr(65 + i)
                distribusi_opsi.append({"huruf": huruf, "jumlah": d.get(huruf, 0)})
            per_question.append({
                "id": q["id"], "nomor": q["nomor"], "kategori": q["kategori"],
                "pertanyaan": q["pertanyaan"], "kunci": q["kunci"], "tipe": q["tipe"],
                "jumlah_benar": jumlah_benar, "persen_benar": pct,
                "label": label, "kosong": d.get("", 0),
                "distribusi": distribusi_opsi,
            })

    kat = {}
    if id_list:
        ph = ",".join("?" * len(id_list))
        for r in conn.execute(
            f"SELECT q.kategori AS kategori, COUNT(*) AS total, SUM(a.benar) AS benar"
            f" FROM answers a JOIN questions q ON q.id = a.question_id"
            f" WHERE a.attempt_id IN ({ph}) GROUP BY q.kategori", id_list,
        ):
            kat[r["kategori"]] = round((r["benar"] or 0) / r["total"] * 100, 1) if r["total"] else None

    classes = [dict(r) for r in conn.execute("SELECT id, name FROM classes ORDER BY name")]
    sudah = {a["email"] for a in attempts}
    attendance = []
    for st in conn.execute(
        "SELECT u.name, u.email, c.name AS kelas, u.class_id FROM users u"
        " LEFT JOIN classes c ON c.id = u.class_id"
        " WHERE u.role = 'siswa'" + (" AND u.class_id = ?" if cid else "") +
        " ORDER BY u.name", ([cid] if cid else []),
    ):
        nilai = next((a["score"] for a in attempts if a["email"] == st["email"]), None)
        attendance.append({
            "name": st["name"], "email": st["email"], "kelas": st["kelas"],
            "nilai": nilai, "status": "Sudah" if st["email"] in sudah else "Tidak hadir",
        })

    return {
        "packages": pkgs, "package_id": pid, "stats": stats,
        "classes": classes, "class_id": cid,
        "distribusi": distribusi, "per_kategori": kat,
        "attempts": [dict(a) for a in attempts],
        "per_question": per_question,
        "attendance": attendance,
    }


def main():
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print(f"TKA Cerdas berjalan di http://0.0.0.0:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
