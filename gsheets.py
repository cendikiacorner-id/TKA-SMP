# -*- coding: utf-8 -*-
"""
gsheets.py — Klien Google Sheets minimal tanpa dependensi eksternal.

Cara kerja:
  1. Service account (JSON key) dipakai membuat JWT bertanda tangan RS256.
  2. JWT ditukar menjadi access token di oauth2.googleapis.com.
  3. Token dipakai memanggil Sheets API v4.

Tanda tangan RS256 diimplementasikan di Python murni (PKCS#1 v1.5 + SHA-256),
karena Python standard library tidak menyediakan RSA. Sudah diuji terhadap
`openssl dgst -verify`.

Untuk pengujian, endpoint dapat diarahkan ke server tiruan lewat variabel
lingkungan GTOKEN_URL dan GAPI_BASE.
"""
import base64
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = os.environ.get("GTOKEN_URL", "https://oauth2.googleapis.com/token")
API_BASE = os.environ.get("GAPI_BASE", "https://sheets.googleapis.com/v4")
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TIMEOUT = 20

_DIGESTINFO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")


class SheetsError(Exception):
    """Kesalahan saat berkomunikasi dengan Google Sheets."""


# ---------------------------------------------------------------------------
# Utilitas encoding
# ---------------------------------------------------------------------------
def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Parsing kunci privat RSA (format PEM PKCS#1 atau PKCS#8)
# ---------------------------------------------------------------------------
def _der_next(buf, pos):
    """Baca satu elemen DER. Kembalikan (tag, isi, posisi_berikutnya)."""
    if pos + 2 > len(buf):
        raise SheetsError("Struktur kunci tidak valid (DER terpotong).")
    tag = buf[pos]
    pos += 1
    length = buf[pos]
    pos += 1
    if length & 0x80:
        n = length & 0x7F
        if n == 0 or n > 4 or pos + n > len(buf):
            raise SheetsError("Struktur kunci tidak valid (panjang DER).")
        length = int.from_bytes(buf[pos:pos + n], "big")
        pos += n
    if pos + length > len(buf):
        raise SheetsError("Struktur kunci tidak valid (isi DER melebihi data).")
    return tag, buf[pos:pos + length], pos + length


def parse_rsa_private_key(pem: str):
    """Kembalikan (n, e, d) dari kunci privat RSA berformat PEM."""
    if not isinstance(pem, str) or "PRIVATE KEY" not in pem:
        raise SheetsError("private_key pada JSON bukan kunci PEM yang sah.")
    body = "".join(
        line.strip()
        for line in pem.strip().splitlines()
        if line.strip() and not line.strip().startswith("-----")
    )
    try:
        der = base64.b64decode(body, validate=True)
    except Exception:
        raise SheetsError("Kunci privat tidak dapat didekode (base64 rusak).")

    tag, outer, _ = _der_next(der, 0)
    if tag != 0x30:
        raise SheetsError("Kunci privat bukan struktur DER yang dikenali.")

    tag1, v1, p = _der_next(outer, 0)
    tag2, v2, p = _der_next(outer, p)
    tag3, v3, p = _der_next(outer, p)

    # PKCS#8: SEQUENCE { INTEGER versi, SEQUENCE algoritma, OCTET STRING kunci }
    if tag1 == 0x02 and tag2 == 0x30 and tag3 == 0x04:
        tag, outer, _ = _der_next(v3, 0)
        if tag != 0x30:
            raise SheetsError("Isi kunci PKCS#8 tidak dikenali.")
        tag1, v1, p = _der_next(outer, 0)

    # PKCS#1: SEQUENCE { versi, n, e, d, p, q, ... }
    if tag1 != 0x02:
        raise SheetsError("Format kunci privat tidak didukung.")
    t, n_b, p = _der_next(outer, p)
    t, e_b, p = _der_next(outer, p)
    t, d_b, p = _der_next(outer, p)
    if t != 0x02:
        raise SheetsError("Format kunci privat tidak didukung (n/e/d).")
    return (
        int.from_bytes(n_b, "big"),
        int.from_bytes(e_b, "big"),
        int.from_bytes(d_b, "big"),
    )


# ---------------------------------------------------------------------------
# Tanda tangan RS256 (PKCS#1 v1.5)
# ---------------------------------------------------------------------------
def sign_rs256(message: bytes, n: int, d: int) -> bytes:
    k = (n.bit_length() + 7) // 8
    digest_info = _DIGESTINFO_SHA256 + hashlib.sha256(message).digest()
    pad_len = k - len(digest_info) - 3
    if pad_len < 8:
        raise SheetsError("Kunci RSA terlalu pendek.")
    em = b"\x00\x01" + b"\xff" * pad_len + b"\x00" + digest_info
    sig = pow(int.from_bytes(em, "big"), d, n)
    return sig.to_bytes(k, "big")


def build_jwt(client_email: str, private_key_pem: str, scope: str = SCOPE,
              now: int = None, lifetime: int = 3600) -> str:
    n, _e, d = parse_rsa_private_key(private_key_pem)
    now = int(now if now is not None else time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": client_email,
        "scope": scope,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + lifetime,
    }
    signing_input = (
        b64u(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64u(json.dumps(claims, separators=(",", ":")).encode())
    )
    signature = sign_rs256(signing_input.encode("ascii"), n, d)
    return signing_input + "." + b64u(signature)


# ---------------------------------------------------------------------------
# Cache token di tingkat proses
# ---------------------------------------------------------------------------
_token_cache = {}
_token_lock = threading.Lock()


def _http(method, url, data=None, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:400]}
        return e.code, payload
    except urllib.error.URLError as e:
        raise SheetsError(f"Tidak dapat menghubungi Google: {e.reason}")
    except TimeoutError:
        raise SheetsError("Koneksi ke Google melewatkan batas waktu.")


class SheetsClient:
    """Klien tipis untuk Google Sheets API v4 memakai service account."""

    def __init__(self, sa_info: dict, sheet_id: str):
        if not isinstance(sa_info, dict):
            raise SheetsError("Kredensial harus berupa objek JSON.")
        self.email = str(sa_info.get("client_email", "")).strip()
        self.key = sa_info.get("private_key", "")
        self.sheet_id = str(sheet_id or "").strip()
        if not self.email or "@" not in self.email:
            raise SheetsError("client_email tidak ditemukan pada JSON kredensial.")
        if not self.key:
            raise SheetsError("private_key tidak ditemukan pada JSON kredensial.")
        if not self.sheet_id:
            raise SheetsError("ID Google Sheet belum diisi.")
        # Validasi awal agar kesalahan konfigurasi cepat terdeteksi.
        parse_rsa_private_key(self.key)

    # -- autentikasi ------------------------------------------------------
    def access_token(self) -> str:
        cache_key = self.email + "|" + self.sheet_id
        with _token_lock:
            hit = _token_cache.get(cache_key)
            if hit and hit[1] > time.time() + 60:
                return hit[0]

        assertion = build_jwt(self.email, self.key)
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode()
        status, payload = _http(
            "POST", TOKEN_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if status != 200 or "access_token" not in payload:
            msg = payload.get("error_description") or payload.get("error") or str(payload)[:200]
            raise SheetsError(
                "Gagal memperoleh token Google. Periksa JSON kredensial. "
                f"Pesan Google: {msg}"
            )
        token = payload["access_token"]
        expires = time.time() + int(payload.get("expires_in", 3600))
        with _token_lock:
            _token_cache[cache_key] = (token, expires)
        return token

    def _api(self, method, path, body=None, retries=3):
        url = API_BASE + path
        data = json.dumps(body).encode() if body is not None else None
        last = None
        for attempt in range(retries):
            token = self.access_token()
            headers = {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            }
            status, payload = _http(method, url, data=data, headers=headers)
            if 200 <= status < 300:
                return payload
            last = (status, payload)
            # 401 -> token kedaluwarsa, paksa ambil ulang
            if status == 401 and attempt < retries - 1:
                with _token_lock:
                    _token_cache.pop(self.email + "|" + self.sheet_id, None)
                continue
            # 429 / 5xx -> coba ulang dengan jeda
            if status in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(1.2 * (attempt + 1))
                continue
            break
        status, payload = last
        msg = ""
        if isinstance(payload, dict):
            msg = (payload.get("error") or {}).get("message") if isinstance(payload.get("error"), dict) else payload.get("error")
        raise SheetsError(f"Google Sheets menolak permintaan (HTTP {status}): {msg or str(payload)[:200]}")

    # -- operasi ----------------------------------------------------------
    def info(self) -> dict:
        """Ambil metadata spreadsheet (sekaligus uji koneksi)."""
        data = self._api("GET", f"/spreadsheets/{self.sheet_id}?fields=properties.title,sheets.properties.title")
        return {
            "title": (data.get("properties") or {}).get("title", ""),
            "tabs": [
                (s.get("properties") or {}).get("title", "")
                for s in data.get("sheets", [])
            ],
        }

    def ensure_tab(self, tab: str):
        """Pastikan tab tersedia; buat bila belum ada."""
        info = self.info()
        if tab in info.get("tabs", []):
            return False
        try:
            self._api("POST", f"/spreadsheets/{self.sheet_id}:batchUpdate", {
                "requests": [{"addSheet": {"properties": {"title": tab}}}]
            })
        except SheetsError as e:
            # Bisa terjadi bila tab baru saja dibuat proses lain.
            if "already exists" not in str(e).lower():
                raise
            return False
        return True

    def ensure_header(self, tab: str, header: list):
        rng = urllib.parse.quote(f"{tab}!A1:{chr(ord('A') + len(header) - 1)}1")
        data = self._api("GET", f"/spreadsheets/{self.sheet_id}/values/{rng}")
        rows = data.get("values") or []
        if rows and any(str(c).strip() for c in rows[0]):
            return False
        body = {"values": [header]}
        self._api(
            "PUT",
            f"/spreadsheets/{self.sheet_id}/values/{rng}?valueInputOption=RAW",
            body,
        )
        return True

    def append_rows(self, tab: str, rows: list):
        if not rows:
            return 0
        rng = urllib.parse.quote(f"{tab}!A1")
        self._api(
            "POST",
            f"/spreadsheets/{self.sheet_id}/values/{rng}:append"
            "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
            {"values": rows},
        )
        return len(rows)

    def sync_rows(self, tab: str, header: list, rows: list):
        created = self.ensure_tab(tab)
        self.ensure_header(tab, header)
        n = self.append_rows(tab, rows)
        return {"tabs_created": created, "rows": n}


def client_from_config(cfg: dict) -> SheetsClient:
    sa = cfg.get("service_account")
    if isinstance(sa, str):
        try:
            sa = json.loads(sa)
        except json.JSONDecodeError:
            raise SheetsError("JSON kredensial tidak valid.")
    return SheetsClient(sa or {}, cfg.get("sheet_id", ""))
