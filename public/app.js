/* ============================================================
   TKA Cerdas — logika aplikasi (vanilla JS, tanpa dependensi)
   ============================================================ */
(() => {
  "use strict";

  // ------------------------------------------------------------
  // Penyimpanan aman (localStorage bisa diblokir di iframe sandbox)
  // ------------------------------------------------------------
  const mem = {};
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return k in mem ? mem[k] : null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { mem[k] = v; } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { delete mem[k]; } },
  };

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const state = {
    token: store.get("tka_token") || "",
    user: null,
    packages: [],
    exam: null,          // sesi ujian aktif
    guruTab: "analytics",
    guruPkg: null,
    guruClass: null,
    classes: [],
    answerTimer: null,
  };

  const KKM_DEFAULT = 70;

  // ------------------------------------------------------------
  // Util
  // ------------------------------------------------------------
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString("id-ID", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const fmtDur = (start, end) => {
    if (!start || !end) return "—";
    const m = Math.max(1, Math.round((new Date(end) - new Date(start)) / 60000));
    return m + " menit";
  };

  function toast(msg, type = "success") {
    const el = document.createElement("div");
    el.className = "toast" + (type !== "success" ? " " + type : "");
    el.textContent = msg;
    $("#toast-root").appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 320); }, 2800);
  }

  async function api(path, opts = {}) {
    const headers = { "Content-Type": "application/json" };
    if (state.token) headers.Authorization = "Bearer " + state.token;
    let res;
    try {
      res = await fetch(path, { ...opts, headers });
    } catch (e) {
      throw new Error("Tidak dapat terhubung ke server. Periksa koneksi lalu coba lagi.");
    }
    let body = {};
    try { body = await res.json(); } catch (e) { /* kosong */ }
    if (!res.ok) {
      if (res.status === 401 && state.token) { clearSession(); showAuth(); }
      const err = new Error(body.error || "Terjadi kesalahan. Coba lagi.");
      if (body.need_token) { err.needToken = true; err.schedule = body.schedule || null; }
      throw err;
    }
    return body;
  }

  function downloadWithAuth(path) {
    fetch(path, { headers: { Authorization: "Bearer " + state.token } })
      .then(async (res) => {
        if (!res.ok) {
          let m = "Gagal mengunduh berkas.";
          try { m = (await res.json()).error || m; } catch (e) { /* abaikan */ }
          throw new Error(m);
        }
        const blob = await res.blob();
        const disp = res.headers.get("Content-Disposition") || "";
        const m = /filename="([^"]+)"/.exec(disp);
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = m ? m[1] : "unduhan";
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
        toast("Berkas berhasil diunduh.");
      })
      .catch((e) => toast(e.message, "error"));
  }

  // ------------------------------------------------------------
  // Sesi
  // ------------------------------------------------------------
  function setSession(token, user) {
    state.token = token || "";
    state.user = user || null;
    if (token) store.set("tka_token", token); else store.del("tka_token");
  }
  function clearSession() { setSession("", null); }

  function showAuth() {
    stopTimer();
    $("#app-view").classList.add("hidden");
    $("#auth-view").classList.remove("hidden");
  }

  function enterApp() {
    $("#auth-view").classList.add("hidden");
    $("#app-view").classList.remove("hidden");
    const u = state.user;
    $("#user-name").textContent = u.name;
    $("#avatar").textContent = (u.name || "?").trim().charAt(0).toUpperCase();
    if (u.role === "guru") {
      $("#role-badge").textContent = "Guru";
      $("#role-badge").classList.add("guru");
      $("#guru-nav").classList.remove("hidden");
      showGuruTab(state.guruTab);
    } else {
      $("#role-badge").textContent = "Siswa";
      $("#role-badge").classList.remove("guru");
      $("#guru-nav").classList.add("hidden");
      hideAllPanels();
      $("#student-home").classList.remove("hidden");
      renderStudentHome();
    }
  }

  function hideAllPanels() {
    ["student-home", "exam-view", "result-view", "guru-analytics", "guru-bank",
     "guru-jadwal", "guru-kelas", "guru-settings"]
      .forEach((id) => $("#" + id).classList.add("hidden"));
  }

  // ------------------------------------------------------------
  // Auth UI
  // ------------------------------------------------------------
  function switchAuthTab(tab) {
    $$(".tabbtn").forEach((b) => {
      const on = b.dataset.tab === tab;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    $("#login-form").classList.toggle("hidden", tab !== "login");
    $("#register-form").classList.toggle("hidden", tab !== "register");
    $("#login-error").textContent = "";
    $("#register-error").textContent = "";
  }

  async function doLogin(e) {
    e.preventDefault();
    const err = $("#login-error");
    err.textContent = "";
    const email = $("#login-email").value.trim();
    const password = $("#login-password").value;
    if (!email || !password) { err.textContent = "Email dan password wajib diisi."; return; }
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = "Membuka…";
    try {
      const res = await api("/api/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setSession(res.token, res.user);
      enterApp();
      toast(`Halo, ${res.user.name.split(" ")[0]}! 👋`);
    } catch (error) {
      err.textContent = error.message;
    } finally {
      btn.disabled = false; btn.textContent = "Masuk";
    }
  }

  async function doRegister(e) {
    e.preventDefault();
    const err = $("#register-error");
    err.textContent = "";
    const name = $("#reg-name").value.trim();
    const email = $("#reg-email").value.trim();
    const password = $("#reg-password").value;
    const role = $("#reg-role").value;
    const guru_code = $("#reg-guru-code").value.trim();
    if (!name || !email || !password) { err.textContent = "Semua kolom wajib diisi."; return; }
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = "Mendaftarkan…";
    try {
      const res = await api("/api/register", {
        method: "POST",
        body: JSON.stringify({ name, email, password, role, guru_code }),
      });
      setSession(res.token, res.user);
      enterApp();
      toast("Akun berhasil dibuat. Selamat bergabung! 🎉");
    } catch (error) {
      err.textContent = error.message;
    } finally {
      btn.disabled = false; btn.textContent = "Daftar";
    }
  }

  async function logout() {
    if (state.exam && !confirm("Ujian masih berjalan. Keluar sekarang? Jawaban yang tersimpan tetap aman, tetapi waktu terus berjalan.")) return;
    try { await api("/api/logout", { method: "POST", body: "{}" }); } catch (e) { /* diamkan */ }
    clearSession();
    stopTimer();
    state.exam = null;
    $("#login-form").reset();
    $("#register-form").reset();
    switchAuthTab("login");
    showAuth();
  }

  // ------------------------------------------------------------
  // Siswa — beranda
  // ------------------------------------------------------------
  function scorePill(score) {
    if (score == null) return '<span class="muted">—</span>';
    const cls = score >= 80 ? "good" : score >= 70 ? "mid" : "low";
    return `<span class="scorepill ${cls}">${score}</span>`;
  }

  async function renderStudentHome() {
    const box = $("#student-home");
    box.innerHTML = '<div class="card"><p class="muted">Memuat data…</p></div>';
    try {
      const [pk, rs] = await Promise.all([
        api("/api/packages"),
        api("/api/my-results"),
      ]);
      state.packages = pk.packages;
      state.myClass = pk.class || null;
      const results = rs.results;

      const done = results.length;
      const avg = done ? Math.round(results.reduce((a, r) => a + r.score, 0) / done * 10) / 10 : null;
      const best = done ? Math.max(...results.map((r) => r.score)) : null;
      const hour = new Date().getHours();
      const greet = hour < 11 ? "Selamat pagi" : hour < 15 ? "Selamat siang" : hour < 19 ? "Selamat sore" : "Selamat malam";
      const nama = state.user.name.split(" ")[0];

      const pkgCards = state.packages.map((p) => {
        const tag = p.kategori === "literasi" ? "tag-literasi" : p.kategori === "numerasi" ? "tag-numerasi" : "tag-campuran";
        const stripe = p.kategori === "literasi" ? "#3B9DF6" : p.kategori === "numerasi" ? "#FFB020" : "#8B5CF6";
        const bestTxt = p.nilai_terbaik != null
          ? `<span class="bestscore">Nilai terbaik: ${p.nilai_terbaik}</span>`
          : '<span class="bestscore empty">Belum dikerjakan</span>';
        const ongoing = p.attempt_id
          ? `<button class="btn teal sm auto" data-resume="${p.attempt_id}">Lanjutkan</button>`
          : `<button class="btn primary sm auto" data-start="${p.id}" data-nama="${esc(p.judul)}">${p.percobaan ? "Kerjakan lagi" : "Mulai"}</button>`;
        const sched = (p.schedules || [])
          .map((sc) => {
            const st = sc.state === "terbuka" ? ["🔓 Sedang berlangsung", "good"]
              : sc.state === "belum_mulai" ? ["⏳ Belum mulai", "mid"] : ["🔒 Sudah berakhir", "low"];
            return `<span class="sched-pill ${st[1]}" title="${fmtDate(sc.start_at)} s.d. ${fmtDate(sc.end_at)}">
              ${st[0]} · ${fmtDate(sc.start_at)}</span>`;
          }).join("");
        return `
          <article class="pkgcard">
            <span class="stripe" style="background:${stripe}"></span>
            <span class="kategori-tag ${tag}">${esc(p.kategori)}</span>
            <h4>${esc(p.judul)}</h4>
            <p class="desc">${esc(p.deskripsi)}</p>
            <div class="pkgmeta">
              <span>📝 <b>${p.jumlah_soal}</b> soal</span>
              <span>⏱ <b>${p.durasi}</b> menit</span>
              <span>📘 ${esc(p.mapel)}</span>
            </div>
            ${sched ? `<div class="sched-row">${sched}</div>` : ""}
            <div class="pkgfoot">${bestTxt}${ongoing}</div>
          </article>`;
      }).join("");

      const riwayat = results.length
        ? `<div class="tablewrap"><table class="tbl">
            <thead><tr><th>Paket</th><th>Nilai</th><th>Benar</th><th>Dikumpulkan</th><th></th></tr></thead>
            <tbody>${results.map((r) => `
              <tr>
                <td>${esc(r.judul)}</td>
                <td>${scorePill(r.score)}</td>
                <td>${r.correct_count}/${r.total_count}</td>
                <td>${fmtDate(r.submitted_at)}</td>
                <td><button class="btn ghost sm" data-view="${r.id}">Lihat pembahasan</button></td>
              </tr>`).join("")}
            </tbody></table></div>`
        : `<div class="empty"><span class="em">🚀</span><p>Belum ada ujian yang dikerjakan.</p><p class="muted">Pilih salah satu paket di atas untuk memulai.</p></div>`;

      box.innerHTML = `
        <div class="greet">
          <div>
            <h2>${greet}, ${esc(nama)}! 👋</h2>
            <p>${new Date().toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
              ${state.myClass && state.myClass.name ? ` · Kelas <b>${esc(state.myClass.name)}</b>` : ""}</p>
          </div>
        </div>
        <div class="statgrid">
          <article class="statcard v1"><span class="em">📝</span><p class="lbl">Ujian selesai</p><p class="val">${done}</p><p class="note">dari ${state.packages.length} paket tersedia</p></article>
          <article class="statcard v2"><span class="em">🎯</span><p class="lbl">Rata-rata nilai</p><p class="val">${avg == null ? "—" : avg}</p><p class="note">seluruh paket</p></article>
          <article class="statcard v3"><span class="em">🏆</span><p class="lbl">Nilai terbaik</p><p class="val">${best == null ? "—" : best}</p><p class="note">pertahankan!</p></article>
        </div>
        <section class="card">
          <div class="card-head"><div><h3>Paket Ujian</h3><div class="sub">Pilih paket untuk mulai mengerjakan. Waktu berjalan otomatis setelah dimulai.</div></div></div>
          <div class="pkggrid">${pkgCards}</div>
        </section>
        <section class="card">
          <div class="card-head"><div><h3>Riwayat Hasil</h3><div class="sub">Klik untuk melihat pembahasan tiap soal.</div></div></div>
          ${riwayat}
        </section>`;

      box.querySelectorAll("[data-start]").forEach((b) =>
        b.addEventListener("click", () => startExam(Number(b.dataset.start), b)));
      box.querySelectorAll("[data-resume]").forEach((b) =>
        b.addEventListener("click", () => openAttempt(Number(b.dataset.resume))));
      box.querySelectorAll("[data-view]").forEach((b) =>
        b.addEventListener("click", () => openAttempt(Number(b.dataset.view))));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Ujian
  // ------------------------------------------------------------
  function stopTimer() {
    if (state.exam && state.exam.timerId) {
      clearInterval(state.exam.timerId);
      state.exam.timerId = null;
    }
  }

  async function startExam(pkgId, btn, token) {
    if (btn) { btn.disabled = true; btn.textContent = "Menyiapkan…"; }
    try {
      const body = { package_id: pkgId };
      if (token) body.token = token;
      const res = await api("/api/attempts", { method: "POST", body: JSON.stringify(body) });
      if (res.resumed) toast("Melanjutkan ujian yang sedang berjalan.", "info");
      closeModal();
      await openAttempt(res.attempt_id);
    } catch (e) {
      if (e.needToken) {
        showTokenModal(pkgId, e.schedule, btn, e.message);
      } else {
        toast(e.message, "error");
      }
      if (btn) { btn.disabled = false; btn.textContent = "Mulai"; }
    }
  }

  function showTokenModal(pkgId, schedule, btn, pesan) {
    const waktu = schedule
      ? `${fmtDate(schedule.start_at)} — ${fmtDate(schedule.end_at)}${schedule.class_name ? " · " + esc(schedule.class_name) : ""}`
      : "";
    openModal("Masukkan token ujian 🔑", `
      <p class="modal-body-text">${esc(pesan)}</p>
      ${waktu ? `<div class="infobox" style="margin:12px 0"><div class="k">Jadwal</div><div class="v" style="font-size:13px">${waktu}</div></div>` : ""}
      <label class="field" for="token-input">Token dari guru</label>
      <input id="token-input" class="field-input" placeholder="Contoh: TKA2026"
        maxlength="12" autocomplete="off" style="letter-spacing:.18em;font-weight:900;font-size:18px">
      <p class="form-error" id="token-error" style="min-height:0"></p>
      <div class="modal-actions">
        <button class="btn ghost" id="m-cancel">Batal</button>
        <button class="btn primary" id="m-ok" style="width:auto">Mulai ujian</button>
      </div>`);
    setTimeout(() => $("#token-input")?.focus(), 150);
    $("#m-cancel").addEventListener("click", closeModal);
    const go = () => {
      const t = $("#token-input").value.trim();
      if (!t) { $("#token-error").textContent = "Token wajib diisi."; return; }
      closeModal();
      startExam(pkgId, btn, t);
    };
    $("#m-ok").addEventListener("click", go);
    $("#token-input").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  }

  async function openAttempt(attemptId) {
    try {
      const data = await api("/api/attempts/" + attemptId);
      if (data.status === "submitted") {
        hideAllPanels();
        $("#result-view").classList.remove("hidden");
        renderResult(data, { back: "home" });
        return;
      }
      beginExamUI(data);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  function beginExamUI(data) {
    hideAllPanels();
    $("#exam-view").classList.remove("hidden");
    const skew = new Date(data.server_time).getTime() - Date.now();
    state.exam = {
      id: data.id,
      paket: data.paket,
      mapel: data.mapel,
      questions: data.questions,
      answers: {},
      idx: 0,
      deadline: new Date(data.deadline_at).getTime(),
      skew,
      submitted: false,
      timerId: null,
      saveTimers: {},
    };
    data.questions.forEach((q) => { state.exam.answers[q.id] = q.jawaban || ""; });
    renderExam();
    startTimer();
    window.onbeforeunload = () => "Ujian sedang berjalan. Yakin ingin meninggalkan halaman?";
  }

  function startTimer() {
    stopTimer();
    const tick = () => {
      const ex = state.exam;
      if (!ex) return;
      const left = Math.max(0, ex.deadline - (Date.now() + ex.skew));
      const el = $("#timer");
      if (el) {
        const s = Math.floor(left / 1000);
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = s % 60;
        el.textContent = "⏱ " + (h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
          : `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`);
        el.classList.toggle("warn", left <= 10 * 60000 && left > 5 * 60000);
        el.classList.toggle("danger", left <= 5 * 60000);
      }
      if (left <= 0) {
        stopTimer();
        autoSubmit();
      }
    };
    tick();
    state.exam.timerId = setInterval(tick, 1000);
  }

  function renderExam() {
    const ex = state.exam;
    const q = ex.questions[ex.idx];
    const answeredCount = ex.questions.filter((x) => (ex.answers[x.id] || "").trim() !== "").length;

    const dots = ex.questions.map((item, i) => {
      const answered = (ex.answers[item.id] || "").trim() !== "";
      const cur = i === ex.idx ? " current" : "";
      const ans = answered ? " answered" : "";
      return `<button class="qdot${ans}${cur}" data-goto="${i}" aria-label="Soal ${i + 1}">${i + 1}</button>`;
    }).join("");

    let answerArea = "";
    if (q.tipe === "pg") {
      answerArea = `<div class="options">${q.opsi.map((opt, i) => {
        const L = String.fromCharCode(65 + i);
        const sel = (ex.answers[q.id] || "").toUpperCase() === L ? " selected" : "";
        return `<button class="opt${sel}" data-opt="${L}" type="button">
          <span class="letter">${L}</span><span>${esc(opt)}</span>
        </button>`;
      }).join("")}</div>`;
    } else {
      answerArea = `<div class="isian-wrap">
        <input id="isian-input" type="text" inputmode="decimal" placeholder="Tulis jawaban angka…"
          value="${esc(ex.answers[q.id] || "")}" autocomplete="off">
      </div>`;
    }

    $("#exam-view").innerHTML = `
      <div class="exam-head">
        <div>
          <div class="exam-title">${esc(ex.paket)}</div>
          <div class="exam-sub">Soal ${ex.idx + 1} dari ${ex.questions.length} · terjawab ${answeredCount}</div>
        </div>
        <div id="timer" class="timer">⏱ --:--</div>
      </div>
      <div class="exam-grid">
        <aside class="qnav">
          <h4>Navigasi soal</h4>
          <div class="qnav-grid">${dots}</div>
          <div class="qnav-legend">
            <span><span class="lg-dot" style="background:#B7EBD7"></span>Sudah dijawab</span>
            <span><span class="lg-dot" style="background:#fff;border:2px solid #5B4BFF"></span>Soal aktif</span>
          </div>
        </aside>
        <section class="qcard">
          <div class="qmeta">
            <span class="qnum">Soal ${q.nomor}</span>
            <span class="qtag ${q.kategori}">${q.kategori === "literasi" ? "Literasi" : "Numerasi"}</span>
            <span class="qtag ${q.tingkat}">${esc(q.tingkat)}</span>
          </div>
          ${q.stimulus ? `<div class="stimulus">${esc(q.stimulus)}</div>` : ""}
          <div class="qtext">${esc(q.pertanyaan)}</div>
          ${answerArea}
          <div class="exam-foot">
            <div class="savehint" id="savehint"></div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn ghost sm" id="prev-btn" ${ex.idx === 0 ? "disabled" : ""}>← Sebelumnya</button>
              ${ex.idx < ex.questions.length - 1
                ? '<button class="btn primary sm auto" id="next-btn">Berikutnya →</button>'
                : '<button class="btn teal sm" id="finish-btn">Kumpulkan Jawaban</button>'}
              ${ex.idx < ex.questions.length - 1 ? '<button class="btn ghost sm" id="finish-btn2">Kumpulkan</button>' : ""}
            </div>
          </div>
        </section>
      </div>`;

    $$("#exam-view .qdot").forEach((d) => d.addEventListener("click", () => {
      state.exam.idx = Number(d.dataset.goto); renderExam();
    }));
    $$("#exam-view .opt").forEach((o) => o.addEventListener("click", () => {
      const qid = state.exam.questions[state.exam.idx].id;
      state.exam.answers[qid] = o.dataset.opt;
      $$("#exam-view .opt").forEach((x) => x.classList.remove("selected"));
      o.classList.add("selected");
      updateAnsweredCount();
      saveAnswer(qid, o.dataset.opt);
    }));

    const isian = $("#isian-input");
    if (isian) {
      isian.addEventListener("input", () => {
        const qid = state.exam.questions[state.exam.idx].id;
        state.exam.answers[qid] = isian.value;
        clearTimeout(state.exam.saveTimers[qid]);
        state.exam.saveTimers[qid] = setTimeout(() => saveAnswer(qid, isian.value), 600);
        updateAnsweredCount();
      });
      isian.addEventListener("blur", () => {
        const qid = state.exam.questions[state.exam.idx].id;
        saveAnswer(qid, isian.value);
      });
    }

    $("#prev-btn")?.addEventListener("click", () => { state.exam.idx--; renderExam(); });
    $("#next-btn")?.addEventListener("click", () => { state.exam.idx++; renderExam(); });
    $("#finish-btn")?.addEventListener("click", confirmSubmit);
    $("#finish-btn2")?.addEventListener("click", confirmSubmit);
    updateAnsweredCount();
  }

  function updateAnsweredCount() {
    const ex = state.exam;
    if (!ex) return;
    const n = ex.questions.filter((x) => (ex.answers[x.id] || "").trim() !== "").length;
    const sub = $("#exam-view .exam-sub");
    if (sub) sub.textContent = `Soal ${ex.idx + 1} dari ${ex.questions.length} · terjawab ${n}`;
    $$("#exam-view .qdot").forEach((d, i) => {
      const q = ex.questions[i];
      d.classList.toggle("answered", (ex.answers[q.id] || "").trim() !== "");
    });
  }

  async function saveAnswer(qid, val) {
    const ex = state.exam;
    if (!ex || ex.submitted) return;
    const hint = $("#savehint");
    try {
      await api(`/api/attempts/${ex.id}/answer`, {
        method: "POST",
        body: JSON.stringify({ question_id: qid, answer: val }),
      });
      if (hint) {
        hint.textContent = "Tersimpan ✓";
        setTimeout(() => { if (hint.textContent === "Tersimpan ✓") hint.textContent = ""; }, 1500);
      }
    } catch (e) {
      if (hint) hint.textContent = "";
      toast(e.message, "error");
    }
  }

  function confirmSubmit() {
    const ex = state.exam;
    const belum = ex.questions.filter((x) => (ex.answers[x.id] || "").trim() === "").length;
    openModal("Kumpulkan jawaban?", `
      <p class="modal-body-text">
        ${belum > 0
          ? `Masih ada <b>${belum} soal</b> yang belum dijawab. Soal yang kosong akan dinilai salah.`
          : "Semua soal sudah dijawab. Jawaban tidak dapat diubah setelah dikumpulkan."}
      </p>
      <div class="modal-actions">
        <button class="btn ghost" id="m-cancel">Periksa lagi</button>
        <button class="btn teal" id="m-ok">Ya, kumpulkan</button>
      </div>`);
    $("#m-cancel").addEventListener("click", closeModal);
    $("#m-ok").addEventListener("click", async () => {
      closeModal();
      await submitExam();
    });
  }

  async function submitExam() {
    const ex = state.exam;
    if (!ex || ex.submitted) return;
    ex.submitted = true;
    stopTimer();
    try {
      const res = await api(`/api/attempts/${ex.id}/submit`, { method: "POST", body: "{}" });
      window.onbeforeunload = null;
      state.exam = null;
      hideAllPanels();
      $("#result-view").classList.remove("hidden");
      renderResult(res, { back: "home" });
      toast("Jawaban terkirim. Nilai keluar otomatis! ⚡");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      ex.submitted = false;
      startTimer();
      toast(e.message, "error");
    }
  }

  function autoSubmit() {
    const ex = state.exam;
    if (!ex || ex.submitted) return;
    toast("Waktu habis. Jawaban dikumpulkan otomatis.", "info");
    submitExam();
  }

  // ------------------------------------------------------------
  // Hasil & pembahasan
  // ------------------------------------------------------------
  function verdictFor(score, kkm) {
    if (score == null) return ["—", ""];
    if (score >= 90) return ["Luar biasa! 🌟", "Penguasaan materi sangat baik."];
    if (score >= kkm) return ["Tuntas! 🎉", "Kamu sudah mencapai batas ketuntasan."];
    if (score >= 50) return ["Hampir tuntas 💪", "Perkuat lagi bagian yang masih lemah."];
    return ["Perlu latihan lagi 📚", "Pelajari kembali pembahasan di bawah, lalu coba lagi."];
  }

  function renderResult(data, opts = {}) {
    const kkm = KKM_DEFAULT;
    const score = data.score == null ? 0 : data.score;
    const [vtext, vsub] = verdictFor(score, kkm);
    const R = 70;
    const C = 2 * Math.PI * R;
    const dash = (Math.min(100, Math.max(0, score)) / 100) * C;
    const color = score >= 80 ? "#12B886" : score >= 70 ? "#5B4BFF" : score >= 50 ? "#FFB020" : "#F4526B";
    const benar = data.correct_count || 0;
    const total = data.total_count || 0;
    const salah = total - benar;

    const catRows = Object.entries(data.kategori || {})
      .filter(([, v]) => v != null)
      .map(([k, v]) => {
        const c = k === "literasi" ? "#3B9DF6" : "#FFB020";
        return `<div class="catbar">
          <div class="cb-head"><span>${k === "literasi" ? "📖 Literasi" : "🧮 Numerasi"}</span><b>${v}%</b></div>
          <div class="cb-track"><div class="cb-fill" style="width:0%;background:${c}"></div></div>
        </div>`;
      }).join("");

    const review = (data.questions || []).map((q) => {
      const isian = q.tipe === "isian";
      const userAns = (q.jawaban || "").trim();
      const kunci = String(q.kunci || "");
      let optsHtml = "";
      if (!isian) {
        optsHtml = `<div class="optlist">${(q.opsi || []).map((o, i) => {
          const L = String.fromCharCode(65 + i);
          const isKey = L === kunci.toUpperCase();
          const isMine = L === userAns.toUpperCase();
          const cls = isKey ? " correct" : (isMine ? " wrong" : "");
          const tag = isKey ? " ✔ kunci" : (isMine ? " · jawabanmu" : "");
          return `<div class="optrow${cls}"><span class="ol">${L}</span><span>${esc(o)}${tag}</span></div>`;
        }).join("")}</div>`;
      }
      return `<div class="revitem ${q.benar ? "ok" : "no"}">
        <button class="revhead" type="button">
          <span class="revmark">${q.benar ? "✓" : "✕"}</span>
          <span>Soal ${q.nomor} · ${q.kategori === "literasi" ? "Literasi" : "Numerasi"}${isian ? " · isian" : ""}</span>
          <span style="margin-left:auto;font-size:12px;color:#7B7594">${q.benar ? "Benar" : "Salah"}</span>
        </button>
        <div class="revbody">
          ${q.stimulus ? `<div class="stim">${esc(q.stimulus)}</div>` : ""}
          <div style="font-weight:800;margin-bottom:10px">${esc(q.pertanyaan)}</div>
          ${optsHtml}
          <div class="ansrow"><span class="k">Jawabanmu</span><span>${userAns ? esc(userAns) : "<i>tidak dijawab</i>"}${isian ? "" : ""}</span></div>
          <div class="ansrow"><span class="k">Kunci jawaban</span><span><b>${esc(kunci)}</b></span></div>
          ${q.pembahasan ? `<div class="explain"><b>Pembahasan:</b> ${esc(q.pembahasan)}</div>` : ""}
        </div>
      </div>`;
    }).join("");

    const studentLine = opts.student
      ? `<div class="verdict-sub" style="margin-bottom:6px">${esc(opts.student.name)} · ${esc(opts.student.email)}</div>` : "";

    $("#result-view").innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
        <button class="btn ghost sm" id="back-btn">← Kembali</button>
        ${data.id ? '<button class="btn ghost sm" id="pdf-student">📄 Unduh Laporan PDF</button>' : ""}
      </div>
      <section class="result-hero">
        ${studentLine}
        <div class="score-ring">
          <svg width="168" height="168" viewBox="0 0 168 168">
            <circle cx="84" cy="84" r="${R}" fill="none" stroke="#F2EFFE" stroke-width="14"></circle>
            <circle cx="84" cy="84" r="${R}" fill="none" stroke="${color}" stroke-width="14"
              stroke-linecap="round"
              stroke-dasharray="${dash} ${C}" transform="rotate(-90 84 84)">
            </circle>
          </svg>
          <div class="score-num"><b style="color:${color}">${score}</b><span>Nilai</span></div>
        </div>
        <div class="verdict">${vtext}</div>
        <div class="verdict-sub">${esc(data.paket || "")}${data.submitted_at ? " · " + fmtDate(data.submitted_at) : ""}</div>
        <div class="result-stats">
          <div class="rs-item"><b>${benar}</b><span>Benar</span></div>
          <div class="rs-item"><b>${salah}</b><span>Salah</span></div>
          <div class="rs-item"><b>${fmtDur(data.started_at, data.submitted_at)}</b><span>Waktu</span></div>
          <div class="rs-item"><b>${kkm}</b><span>KKM</span></div>
        </div>
      </section>
      ${catRows ? `<section class="card"><div class="card-head"><h3>Penguasaan per kategori</h3></div><div class="catbars">${catRows}</div></section>` : ""}
      <section class="card">
        <div class="card-head"><div><h3>Pembahasan soal</h3><div class="sub">Klik tiap soal untuk melihat jawaban dan penjelasan.</div></div></div>
        <div class="review">${review}</div>
      </section>`;

    requestAnimationFrame(() => {
      $$("#result-view .cb-fill").forEach((el, i) => {
        const v = Object.values(data.kategori || {}).filter((x) => x != null)[i];
        el.style.width = Math.max(0, Math.min(100, v)) + "%";
      });
    });
    $$("#result-view .revhead").forEach((b) =>
      b.addEventListener("click", () => b.parentElement.classList.toggle("open")));
    const pdfBtn = $("#pdf-student");
    if (pdfBtn) pdfBtn.addEventListener("click", () => downloadWithAuth("/api/report/student/" + data.id));
    $("#back-btn").addEventListener("click", () => {
      if (opts.back === "analytics" && state.user.role === "guru") {
        hideAllPanels(); $("#guru-analytics").classList.remove("hidden"); loadAnalytics(state.guruPkg);
      } else {
        hideAllPanels(); $("#student-home").classList.remove("hidden"); renderStudentHome();
      }
    });
    if (opts.autoOpenFirst) {
      const first = $("#result-view .revhead");
      if (first) first.parentElement.classList.add("open");
    }
  }

  // ------------------------------------------------------------
  // Guru — analisis
  // ------------------------------------------------------------
  function showGuruTab(tab) {
    state.guruTab = tab;
    $$(".navbtn").forEach((b) => b.classList.toggle("active", b.dataset.gnav === tab));
    hideAllPanels();
    if (tab === "analytics") { $("#guru-analytics").classList.remove("hidden"); loadAnalytics(state.guruPkg); }
    if (tab === "bank") { $("#guru-bank").classList.remove("hidden"); loadBank(state.guruPkg); }
    if (tab === "jadwal") { $("#guru-jadwal").classList.remove("hidden"); loadJadwal(); }
    if (tab === "kelas") { $("#guru-kelas").classList.remove("hidden"); loadKelas(); }
    if (tab === "settings") { $("#guru-settings").classList.remove("hidden"); loadSettings(); }
  }

  async function loadAnalytics(pkgId, classId) {
    const box = $("#guru-analytics");
    box.innerHTML = '<div class="card"><p class="muted">Memuat analisis…</p></div>';
    try {
      const q = [];
      if (pkgId) q.push("package_id=" + pkgId);
      if (classId) q.push("class_id=" + classId);
      const data = await api("/api/analytics" + (q.length ? "?" + q.join("&") : ""));
      state.guruPkg = data.package_id;
      state.guruClass = data.class_id;
      const s = data.stats;
      const chips = data.packages.map((p) =>
        `<button class="pkgchip ${p.id === data.package_id ? "active" : ""}" data-pkg="${p.id}">${esc(p.judul)}</button>`
      ).join("");

      const maxD = Math.max(1, ...data.distribusi.map((d) => d.jumlah));
      const chart = data.distribusi.map((d, i) => {
        const h = Math.round((d.jumlah / maxD) * 100);
        const cls = i <= 1 ? "low" : i >= 3 ? "good" : "";
        return `<div class="bar-col">
          <span class="bar-val">${d.jumlah}</span>
          <div class="bar-track"><div class="bar ${cls}" style="height:${Math.max(d.jumlah ? 6 : 2, h)}%"></div></div>
          <span class="bar-lbl">${d.label}</span>
        </div>`;
      }).join("");

      const kat = Object.entries(data.per_kategori || {})
        .filter(([, v]) => v != null)
        .map(([k, v]) => {
          const c = k === "literasi" ? "#3B9DF6" : "#FFB020";
          return `<div class="catbar"><div class="cb-head"><span>${k === "literasi" ? "📖 Literasi" : "🧮 Numerasi"}</span><b>${v}%</b></div>
            <div class="cb-track"><div class="cb-fill" style="width:${v}%;background:${c}"></div></div></div>`;
        }).join("");

      const rows = data.attempts.length ? data.attempts.map((a, i) => `
        <tr class="clickable" data-att="${a.id}">
          <td><span class="ranknum ${i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : ""}">${i + 1}</span></td>
          <td><b>${esc(a.name)}</b><br><span class="muted" style="font-size:11.5px">${esc(a.email)}</span></td>
          <td>${scorePill(a.score)}</td>
          <td>${a.correct_count}/${a.total_count}</td>
          <td>${fmtDur(a.started_at, a.submitted_at)}</td>
          <td>${fmtDate(a.submitted_at)}</td>
        </tr>`).join("")
        : `<tr><td colspan="6"><div class="empty"><span class="em">📭</span><p>Belum ada siswa yang mengumpulkan paket ini.</p></div></td></tr>`;

      const iq = data.per_question.length ? data.per_question.map((q) => {
        const color = q.persen_benar >= 70 ? "#12B886" : q.persen_benar >= 40 ? "#FFB020" : "#F4526B";
        const dist = q.distribusi.map((d) => {
          const maxN = Math.max(1, ...q.distribusi.map((x) => x.jumlah), q.kosong);
          return `<div class="distrow ${d.huruf === q.kunci ? "key" : ""}">
            <span class="dl">${d.huruf}</span>
            <div class="dbar"><div style="width:${Math.round(d.jumlah / maxN * 100)}%"></div></div>
            <span class="dn">${d.jumlah}</span>
          </div>`;
        }).join("");
        return `<div class="iqitem">
          <button class="iqhead" type="button">
            <span class="iqno">${q.nomor}</span>
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:52%">${esc(q.pertanyaan)}</span>
            <span class="iqmeta">
              <span class="qtag ${q.kategori}">${q.kategori === "literasi" ? "Literasi" : "Numerasi"}</span>
              <span class="qtag ${q.label}">${q.label}</span>
              <b style="color:${color}">${q.persen_benar}% benar</b>
            </span>
          </button>
          <div class="iqbody">
            <div class="pbar"><div style="width:${q.persen_benar}%;background:${color}"></div></div>
            <div style="font-size:12.5px;color:#7B7594;font-weight:700;margin-bottom:10px">
              ${q.jumlah_benar} dari ${s.peserta} siswa menjawab benar
              ${q.kosong ? `· ${q.kosong} tidak menjawab` : ""}
            </div>
            ${q.tipe === "isian"
              ? `<div class="keyline">Kunci: ${esc(q.kunci)}</div>`
              : `<div style="font-size:12px;font-weight:900;color:#7B7594;margin-top:6px">Sebaran pilihan jawaban</div>${dist}`}
          </div>
        </div>`;
      }).join("") : `<div class="empty"><span class="em">📝</span><p>Belum ada data analisis butir soal.</p></div>`;

      const classChips = (data.classes || []).length
        ? `<div class="pkgchips" style="margin-top:-6px">
             <button class="pkgchip ${!data.class_id ? "active" : ""}" data-cls="">Semua kelas</button>
             ${data.classes.map((c) => `<button class="pkgchip ${c.id === data.class_id ? "active" : ""}" data-cls="${c.id}">${esc(c.name)}</button>`).join("")}
           </div>` : "";

      box.innerHTML = `
        <div class="pkgchips">${chips}</div>
        ${classChips}
        <div class="btnrow" style="margin:0 0 16px">
          <button class="btn ghost sm" id="pdf-class">📄 Unduh Rekap PDF</button>
          <button class="btn ghost sm" id="pdf-attendance">🗒️ PDF Kehadiran</button>
          <button class="btn ghost sm" id="csv-attendance">⬇️ CSV Kehadiran</button>
        </div>
        <div class="statgrid">
          <article class="statcard v1"><span class="em">👥</span><p class="lbl">Peserta</p><p class="val">${s.peserta}</p><p class="note">sudah mengumpulkan</p></article>
          <article class="statcard v2"><span class="em">📊</span><p class="lbl">Rata-rata nilai</p><p class="val">${s.rata_rata == null ? "—" : s.rata_rata}</p><p class="note">tertinggi ${s.tertinggi ?? "—"} · terendah ${s.terendah ?? "—"}</p></article>
          <article class="statcard v3"><span class="em">✅</span><p class="lbl">Tuntas (KKM ${s.kkm})</p><p class="val">${s.persen_tuntas == null ? "—" : s.persen_tuntas + "%"}</p><p class="note">${s.tuntas} dari ${s.peserta} siswa</p></article>
        </div>
        <div class="setgrid" style="grid-template-columns:1fr 1fr;align-items:stretch">
          <section class="card"><div class="card-head"><h3>Distribusi nilai</h3></div><div class="chart">${chart}</div></section>
          <section class="card"><div class="card-head"><h3>Rata-rata per kategori</h3></div>${kat || '<p class="muted">Belum ada data.</p>'}</section>
        </div>
        <section class="card">
          <div class="card-head"><div><h3>Daftar peserta</h3><div class="sub">Diurutkan dari nilai tertinggi. Klik baris untuk melihat pembahasan siswa.</div></div></div>
          <div class="tablewrap"><table class="tbl">
            <thead><tr><th>#</th><th>Siswa</th><th>Nilai</th><th>Benar</th><th>Durasi</th><th>Dikumpulkan</th></tr></thead>
            <tbody>${rows}</tbody>
          </table></div>
        </section>
        <section class="card">
          <div class="card-head"><div><h3>Analisis butir soal</h3><div class="sub">Tingkat kesulitan dihitung otomatis dari persentase siswa yang menjawab benar.</div></div></div>
          ${iq}
        </section>`;

      box.querySelectorAll("[data-pkg]").forEach((b) =>
        b.addEventListener("click", () => loadAnalytics(Number(b.dataset.pkg), state.guruClass)));
      box.querySelectorAll("[data-cls]").forEach((b) =>
        b.addEventListener("click", () => loadAnalytics(state.guruPkg, b.dataset.cls ? Number(b.dataset.cls) : null)));

      const qs = () => {
        const parts = [`package_id=${state.guruPkg}`];
        if (state.guruClass) parts.push(`class_id=${state.guruClass}`);
        return "?" + parts.join("&");
      };
      const pb = $("#pdf-class"), pa = $("#pdf-attendance"), ca = $("#csv-attendance");
      if (pb) pb.addEventListener("click", () => downloadWithAuth("/api/report/class" + qs()));
      if (pa) pa.addEventListener("click", () => downloadWithAuth("/api/report/attendance" + qs()));
      if (ca) ca.addEventListener("click", () => downloadWithAuth("/api/attendance.csv" + qs()));

      box.querySelectorAll("[data-att]").forEach((tr) =>
        tr.addEventListener("click", async () => {
          try {
            const res = await api("/api/analytics/attempt/" + tr.dataset.att);
            hideAllPanels();
            $("#result-view").classList.remove("hidden");
            renderResult(res, { back: "analytics", student: res.student });
            window.scrollTo({ top: 0, behavior: "smooth" });
          } catch (e) { toast(e.message, "error"); }
        }));
      box.querySelectorAll(".iqhead").forEach((b) =>
        b.addEventListener("click", () => b.parentElement.classList.toggle("open")));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Guru — bank soal
  // ------------------------------------------------------------
  async function loadBank(pkgId) {
    const box = $("#guru-bank");
    box.innerHTML = '<div class="card"><p class="muted">Memuat bank soal…</p></div>';
    try {
      const data = await api("/api/analytics" + (pkgId ? "?package_id=" + pkgId : ""));
      state.guruPkg = data.package_id;
      const qs = (await api("/api/questions?package_id=" + data.package_id)).questions;
      const chips = data.packages.map((p) =>
        `<button class="pkgchip ${p.id === data.package_id ? "active" : ""}" data-pkg="${p.id}">${esc(p.judul)}</button>`
      ).join("");
      const items = qs.map((q) => `
        <div class="qbank">
          <div class="qbank-head">
            <span class="iqno">${q.nomor}</span>
            <div style="flex:1">
              <div style="font-weight:800;font-size:14px">${esc(q.pertanyaan)}</div>
              <div class="qmeta" style="margin:7px 0 0">
                <span class="qtag ${q.kategori}">${q.kategori === "literasi" ? "Literasi" : "Numerasi"}</span>
                <span class="qtag ${q.tingkat}">${esc(q.tingkat)}</span>
                <span class="qtag" style="background:#F2EFFE;color:#5B4BFF">${q.tipe === "pg" ? "Pilihan ganda" : "Isian angka"}</span>
              </div>
            </div>
          </div>
          <div class="qbank-body">
            ${q.stimulus ? `<div class="stimulus" style="margin-bottom:12px">${esc(q.stimulus)}</div>` : ""}
            ${q.tipe === "isian"
              ? `<div class="keyline">Kunci: ${esc(q.kunci)}${q.toleransi ? ` (toleransi ${q.toleransi})` : ""}</div>`
              : `<div class="optlist">${q.opsi.map((o, i) => {
                  const L = String.fromCharCode(65 + i);
                  return `<div class="optrow ${L === q.kunci ? "correct" : ""}"><span class="ol">${L}</span><span>${esc(o)}</span></div>`;
                }).join("")}</div>`}
            ${q.pembahasan ? `<div class="explain" style="margin-top:12px;background:#F5F3FF;border-radius:11px;padding:12px 14px;font-size:13px;line-height:1.6"><b>Pembahasan:</b> ${esc(q.pembahasan)}</div>` : ""}
          </div>
        </div>`).join("");
      box.innerHTML = `
        <div class="pkgchips">${chips}</div>
        <section class="card">
          <div class="card-head"><div><h3>Impor Soal</h3>
            <div class="sub">Unggah soal dari Excel (.xlsx), Word (.docx), CSV, atau TXT. Soal akan ditambahkan ke paket yang dipilih di atas.</div></div></div>
          <div class="importbox" id="dropzone">
            <div class="import-emoji">📥</div>
            <p class="import-title">Tarik berkas ke sini, atau klik untuk memilih</p>
            <p class="muted" style="font-size:12.5px">Maksimal 5 MB · .xlsx, .docx, .csv, .txt</p>
            <input type="file" id="import-file" accept=".xlsx,.xlsm,.docx,.csv,.txt,.md" class="hidden">
          </div>
          <div class="btnrow">
            <button class="btn ghost sm" id="dl-template-xlsx">⬇️ Template Excel</button>
            <button class="btn ghost sm" id="dl-template-txt">⬇️ Template Word/TXT</button>
          </div>
          <p class="form-error" id="import-error" style="min-height:0"></p>
          <div id="import-result"></div>
        </section>
        <section class="card">
          <div class="card-head"><div><h3>Bank soal (${qs.length} soal)</h3>
            <div class="sub">Soal bawaan sudah dilengkapi kunci dan pembahasan. Klik untuk membuka detail.</div></div></div>
          ${items}
        </section>`;
      box.querySelectorAll("[data-pkg]").forEach((b) =>
        b.addEventListener("click", () => loadBank(Number(b.dataset.pkg))));
      box.querySelectorAll(".qbank-head").forEach((h) =>
        h.addEventListener("click", () => h.parentElement.classList.toggle("open")));

      // ---- impor ----
      const zone = $("#dropzone"), fileInput = $("#import-file");
      zone.addEventListener("click", () => fileInput.click());
      zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
      zone.addEventListener("dragleave", () => zone.classList.remove("over"));
      zone.addEventListener("drop", (e) => {
        e.preventDefault(); zone.classList.remove("over");
        if (e.dataTransfer.files.length) handleImportFile(e.dataTransfer.files[0], data.package_id);
      });
      fileInput.addEventListener("change", () => {
        if (fileInput.files.length) handleImportFile(fileInput.files[0], data.package_id);
      });
      $("#dl-template-xlsx").addEventListener("click", () => downloadWithAuth("/api/template.xlsx"));
      $("#dl-template-txt").addEventListener("click", () => downloadWithAuth("/api/template.txt"));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Impor soal
  // ------------------------------------------------------------
  function uploadFile(path, file, fields) {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
      fd.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", path);
      if (state.token) xhr.setRequestHeader("Authorization", "Bearer " + state.token);
      xhr.onload = () => {
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch (e) { /* abaikan */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error(body.error || "Gagal mengunggah berkas."));
      };
      xhr.onerror = () => reject(new Error("Tidak dapat mengunggah berkas. Periksa koneksi."));
      xhr.send(fd);
    });
  }

  async function handleImportFile(file, packageId) {
    const errEl = $("#import-error");
    const out = $("#import-result");
    if (!errEl || !out) return;
    errEl.textContent = "";
    out.innerHTML = '<p class="muted" style="font-size:13px">Membaca berkas…</p>';
    if (file.size > 5 * 1024 * 1024) {
      errEl.textContent = "Ukuran berkas melebihi 5 MB.";
      out.innerHTML = "";
      return;
    }
    try {
      const res = await uploadFile("/api/import/questions", file, {
        package_id: String(packageId), mode: "preview",
      });
      renderImportPreview(file, res, packageId);
    } catch (e) {
      errEl.textContent = e.message;
      out.innerHTML = "";
    }
  }

  function renderImportPreview(file, res, packageId) {
    const out = $("#import-result");
    const kat = (k) => (k === "literasi" ? "Literasi" : "Numerasi");
    const list = (res.questions || []).map((q, i) => `
      <div class="prevq">
        <div class="prevq-head">
          <span class="iqno">${i + 1}</span>
          <div style="flex:1;min-width:0">
            <div class="prevq-text">${esc(q.pertanyaan).slice(0, 220)}</div>
            <div class="qmeta" style="margin-top:6px">
              <span class="qtag ${q.kategori}">${kat(q.kategori)}</span>
              <span class="qtag ${q.tingkat}">${esc(q.tingkat)}</span>
              <span class="qtag" style="background:#F2EFFE;color:#5B4BFF">${q.tipe === "pg" ? "PG" : "Isian"}</span>
              ${q.opsi.length ? `<span class="muted" style="font-size:12px">${q.opsi.length} opsi</span>` : ""}
              <span class="keyline" style="margin:0">Kunci: ${esc(q.kunci)}</span>
            </div>
          </div>
        </div>
      </div>`).join("");

    const errList = (res.errors || []).length
      ? `<div class="warnbox"><b>${res.errors.length} peringatan:</b><ul style="margin:6px 0 0 18px;padding:0">
           ${res.errors.slice(0, 10).map((e) => `<li>${esc(e)}</li>`).join("")}</ul></div>` : "";

    out.innerHTML = `
      <div class="import-summary">
        <div>
          <b>${res.total} soal</b> terdeteksi dari <b>${esc(file.name)}</b>
          <div class="muted" style="font-size:12.5px">${esc(res.info || "")} · tujuan: ${esc(res.package)}</div>
        </div>
        <div class="btnrow" style="margin:0">
          <button class="btn ghost sm" id="imp-cancel">Batal</button>
          <button class="btn teal sm" id="imp-confirm">Impor ${res.total} soal</button>
        </div>
      </div>
      ${errList}
      <div class="prevlist">${list || '<p class="muted">Tidak ada soal yang bisa ditampilkan.</p>'}</div>`;

    $("#imp-cancel").addEventListener("click", () => { out.innerHTML = ""; });
    $("#imp-confirm").addEventListener("click", async () => {
      const btn = $("#imp-confirm");
      btn.disabled = true; btn.textContent = "Mengimpor…";
      try {
        const r = await uploadFile("/api/import/questions", file, {
          package_id: String(packageId), mode: "import",
        });
        toast(`${r.imported} soal berhasil ditambahkan ke bank soal. 🎉`);
        loadBank(packageId);
      } catch (e) {
        toast(e.message, "error");
        btn.disabled = false; btn.textContent = "Impor";
      }
    });
  }

  // ------------------------------------------------------------
  // Guru — jadwal & token
  // ------------------------------------------------------------
  const toLocalInput = (iso) => {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  function stateBadge(state) {
    const map = {
      terbuka: ["Sedang berlangsung", "#E9FBF3", "#0B8A5F"],
      belum_mulai: ["Belum mulai", "#FFF6E0", "#A56A00"],
      berakhir: ["Sudah berakhir", "#FFEBEE", "#C62839"],
    };
    const [t, bg, c] = map[state] || ["—", "#F2EFFE", "#5B4BFF"];
    return `<span style="background:${bg};color:${c};font-weight:900;font-size:11.5px;padding:4px 10px;border-radius:999px">${t}</span>`;
  }

  async function loadJadwal() {
    const box = $("#guru-jadwal");
    box.innerHTML = '<div class="card"><p class="muted">Memuat jadwal…</p></div>';
    try {
      const [sch, pk, kl] = await Promise.all([
        api("/api/schedules"), api("/api/packages"), api("/api/classes"),
      ]);
      state.packages = pk.packages;
      state.classes = kl.classes;

      const now = new Date();
      const defStart = toLocalInput(new Date(now.getTime() + 3600000));
      const defEnd = toLocalInput(new Date(now.getTime() + 3 * 3600000));

      const rows = sch.schedules.length ? sch.schedules.map((s) => `
        <tr>
          <td><b>${esc(s.judul)}</b><br><span class="muted" style="font-size:11.5px">${esc(s.kode || "")}</span></td>
          <td>${s.class_name ? esc(s.class_name) : '<i class="muted">Semua kelas</i>'}</td>
          <td style="white-space:nowrap">${fmtDate(s.start_at)}<br><span class="muted" style="font-size:11.5px">s.d. ${fmtDate(s.end_at)}</span></td>
          <td><code style="font-size:13px;letter-spacing:.1em;font-weight:900">${esc(s.token)}</code></td>
          <td>${stateBadge(s.state)}</td>
          <td style="white-space:nowrap">
            <button class="btn ghost sm" data-newtoken="${s.id}" title="Buat token baru">🔄 Token</button>
            <button class="btn ghost sm" data-delsched="${s.id}" title="Hapus jadwal">🗑️</button>
          </td>
        </tr>`).join("")
        : `<tr><td colspan="6"><div class="empty"><span class="em">🗓️</span><p>Belum ada jadwal ujian.</p><p class="muted">Buat jadwal agar siswa wajib memasukkan token.</p></div></td></tr>`;

      box.innerHTML = `
        <section class="card">
          <div class="card-head"><div><h3>Buat Jadwal Ujian</h3>
            <div class="sub">Siswa hanya bisa memulai ujian pada rentang waktu ini, dan wajib memasukkan token dari guru.</div></div></div>
          <div class="fieldrow">
            <div><label class="field" for="sch-pkg">Paket ujian</label>
              <select id="sch-pkg" class="field-input">${state.packages.map((p) =>
                `<option value="${p.id}">${esc(p.judul)}</option>`).join("")}</select></div>
            <div><label class="field" for="sch-class">Kelas</label>
              <select id="sch-class" class="field-input"><option value="">Semua kelas</option>
                ${state.classes.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}
              </select></div>
          </div>
          <div class="fieldrow">
            <div><label class="field" for="sch-start">Mulai (waktu lokal)</label>
              <input id="sch-start" type="datetime-local" class="field-input" value="${defStart}"></div>
            <div><label class="field" for="sch-end">Selesai (waktu lokal)</label>
              <input id="sch-end" type="datetime-local" class="field-input" value="${defEnd}"></div>
          </div>
          <label class="field" for="sch-token">Token (kosongkan untuk dibuat otomatis)</label>
          <input id="sch-token" class="field-input" placeholder="Contoh: TKA2026" maxlength="12" style="max-width:260px">
          <p class="form-error" id="sch-error" style="min-height:0"></p>
          <div class="btnrow"><button class="btn primary sm auto" id="sch-save">Buat jadwal</button></div>
        </section>

        <section class="card">
          <div class="card-head"><div><h3>Daftar Jadwal</h3>
            <div class="sub">Token dibagikan ke siswa sebelum ujian dimulai.</div></div></div>
          <div class="tablewrap"><table class="tbl">
            <thead><tr><th>Paket</th><th>Kelas</th><th>Waktu</th><th>Token</th><th>Status</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
          </table></div>
        </section>`;

      $("#sch-save").addEventListener("click", async () => {
        const errEl = $("#sch-error");
        errEl.textContent = "";
        const start = $("#sch-start").value, end = $("#sch-end").value;
        if (!start || !end) { errEl.textContent = "Waktu mulai dan selesai wajib diisi."; return; }
        const btn = $("#sch-save");
        btn.disabled = true; btn.textContent = "Menyimpan…";
        try {
          const res = await api("/api/schedules", {
            method: "POST",
            body: JSON.stringify({
              package_id: Number($("#sch-pkg").value),
              class_id: $("#sch-class").value || null,
              start_at: new Date(start).toISOString(),
              end_at: new Date(end).toISOString(),
              token: $("#sch-token").value.trim(),
            }),
          });
          toast(`Jadwal dibuat. Token: ${res.token} 📋`);
          loadJadwal();
        } catch (e) {
          errEl.textContent = e.message;
          btn.disabled = false; btn.textContent = "Buat jadwal";
        }
      });

      box.querySelectorAll("[data-newtoken]").forEach((b) => b.addEventListener("click", async () => {
        try {
          const res = await api(`/api/schedules/${b.dataset.newtoken}/token`, { method: "POST", body: "{}" });
          toast(`Token baru: ${res.token} 🔄`);
          loadJadwal();
        } catch (e) { toast(e.message, "error"); }
      }));

      box.querySelectorAll("[data-delsched]").forEach((b) => b.addEventListener("click", async () => {
        openModal("Hapus jadwal?", `<p class="modal-body-text">Jadwal ini akan dihapus. Hasil ujian yang sudah ada <b>tidak</b> ikut terhapus.</p>
          <div class="modal-actions"><button class="btn ghost" id="m-cancel">Batal</button>
          <button class="btn danger" id="m-ok">Ya, hapus</button></div>`);
        $("#m-cancel").addEventListener("click", closeModal);
        $("#m-ok").addEventListener("click", async () => {
          closeModal();
          try { await api(`/api/schedules/${b.dataset.delsched}`, { method: "DELETE" }); toast("Jadwal dihapus."); loadJadwal(); }
          catch (e) { toast(e.message, "error"); }
        });
      }));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Guru — kelas
  // ------------------------------------------------------------
  async function loadKelas() {
    const box = $("#guru-kelas");
    box.innerHTML = '<div class="card"><p class="muted">Memuat kelas…</p></div>';
    try {
      const [kl, st] = await Promise.all([api("/api/classes"), api("/api/students")]);
      state.classes = kl.classes;
      const siswa = st.students;

      const cards = state.classes.map((c) => {
        const anggota = siswa.filter((s) => s.class_id === c.id);
        return `<article class="pkgcard" style="cursor:default">
          <span class="stripe" style="background:#5B4BFF"></span>
          <div style="display:flex;align-items:center;justify-content:space-between">
            <h4 style="font-size:20px">${esc(c.name)}</h4>
            <span class="scorepill good">${c.anggota} siswa</span>
          </div>
          <p class="desc">${anggota.length ? anggota.map((a) => esc(a.name)).join(", ") : "Belum ada siswa."}</p>
          <div class="pkgfoot">
            <span class="muted" style="font-size:12px">${anggota.reduce((t, a) => t + a.jumlah_ujian, 0)} ujian dikumpulkan</span>
            <button class="btn ghost sm" data-delclass="${c.id}">Hapus</button>
          </div>
        </article>`;
      }).join("");

      const rows = siswa.map((s) => `
        <tr>
          <td><b>${esc(s.name)}</b><br><span class="muted" style="font-size:11.5px">${esc(s.email)}</span></td>
          <td>
            <select class="month-select" data-assign="${s.id}">
              <option value="">— Tanpa kelas —</option>
              ${state.classes.map((c) => `<option value="${c.id}" ${c.id === s.class_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
            </select>
          </td>
          <td>${s.jumlah_ujian}</td>
        </tr>`).join("");

      box.innerHTML = `
        <section class="card">
          <div class="card-head"><div><h3>Kelas</h3>
            <div class="sub">Kelas dipakai untuk membatasi siapa yang boleh mengikuti jadwal ujian tertentu.</div></div></div>
          <div class="pkggrid">${cards || '<p class="muted">Belum ada kelas.</p>'}</div>
          <div class="fieldrow" style="margin-top:16px;max-width:520px">
            <div><label class="field" for="cls-name">Nama kelas baru</label>
              <input id="cls-name" class="field-input" placeholder="Contoh: IX-D" maxlength="40"></div>
            <div style="display:flex;align-items:flex-end"><button class="btn primary sm auto" id="cls-add" style="width:100%">Tambah kelas</button></div>
          </div>
          <p class="form-error" id="cls-error" style="min-height:0"></p>
        </section>

        <section class="card">
          <div class="card-head"><div><h3>Penempatan Siswa</h3>
            <div class="sub">Ubah kelas siswa langsung dari daftar ini.</div></div></div>
          <div class="tablewrap"><table class="tbl">
            <thead><tr><th>Siswa</th><th>Kelas</th><th>Ujian</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="3"><div class="empty"><p>Belum ada siswa.</p></div></td></tr>'}</tbody>
          </table></div>
        </section>`;

      $("#cls-add").addEventListener("click", async () => {
        const errEl = $("#cls-error");
        errEl.textContent = "";
        try {
          await api("/api/classes", { method: "POST", body: JSON.stringify({ name: $("#cls-name").value.trim() }) });
          toast("Kelas ditambahkan.");
          loadKelas();
        } catch (e) { errEl.textContent = e.message; }
      });

      box.querySelectorAll("[data-assign]").forEach((sel) => sel.addEventListener("change", async () => {
        try {
          await api("/api/classes/assign", {
            method: "POST",
            body: JSON.stringify({ user_id: Number(sel.dataset.assign), class_id: sel.value || null }),
          });
          toast("Kelas siswa diperbarui.");
          loadKelas();
        } catch (e) { toast(e.message, "error"); }
      }));

      box.querySelectorAll("[data-delclass]").forEach((b) => b.addEventListener("click", async () => {
        openModal("Hapus kelas?", `<p class="modal-body-text">Kelas ini akan dihapus dan siswa di dalamnya menjadi tanpa kelas. Hasil ujian tidak terhapus.</p>
          <div class="modal-actions"><button class="btn ghost" id="m-cancel">Batal</button>
          <button class="btn danger" id="m-ok">Ya, hapus</button></div>`);
        $("#m-cancel").addEventListener("click", closeModal);
        $("#m-ok").addEventListener("click", async () => {
          closeModal();
          try { await api(`/api/classes/${b.dataset.delclass}`, { method: "DELETE" }); toast("Kelas dihapus."); loadKelas(); }
          catch (e) { toast(e.message, "error"); }
        });
      }));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Guru — pengaturan
  // ------------------------------------------------------------
  async function loadSettings() {
    const box = $("#guru-settings");
    box.innerHTML = '<div class="card"><p class="muted">Memuat pengaturan…</p></div>';
    try {
      const s = await api("/api/settings");
      const sh = s.sheets;
      const logs = s.logs.length ? s.logs.map((l) => `
        <div class="logitem ${l.ok ? "" : "err"}"><span class="lt">${fmtDate(l.at)}</span>${esc(l.message)}</div>`).join("")
        : '<p class="muted" style="font-size:13px">Belum ada aktivitas sinkronisasi.</p>';

      box.innerHTML = `
        <div class="setgrid">
          <section class="card">
            <div class="card-head"><div><h3>☁️ Google Sheets</h3><div class="sub">Salin otomatis hasil ujian ke spreadsheet Anda.</div></div></div>
            <div class="status ${sh.enabled ? "on" : "off"}">
              <span class="dotstatus"></span>
              ${sh.enabled ? "Sinkronisasi aktif" : "Sinkronisasi belum aktif"}
              ${sh.pending_sync ? `· ${sh.pending_sync} hasil menunggu dikirim` : ""}
            </div>
            <label class="field" for="set-sheet-id">ID Google Sheet</label>
            <input id="set-sheet-id" class="field-input" type="text" placeholder="Contoh: 1AbCdEfGhIjKlMnOpQrStUvWxYz..." value="${esc(sh.sheet_id || "")}">
            <p class="hint">Diambil dari tautan spreadsheet: docs.google.com/spreadsheets/d/<b>ID-INI</b>/edit</p>
            <label class="field" for="set-tab">Nama tab tujuan</label>
            <input id="set-tab" class="field-input" type="text" placeholder="Hasil" value="${esc(sh.tab || "Hasil")}">
            <label class="field" for="set-sa">JSON service account</label>
            <textarea id="set-sa" class="field-input" placeholder="${sh.has_key ? "Kredensial sudah tersimpan. Kosongkan bila tidak ingin mengubah." : "Tempel isi file JSON dari Google Cloud di sini…"}"></textarea>
            <p class="hint">${sh.client_email ? "Terhubung sebagai: <b>" + esc(sh.client_email) + "</b>" : "Buat service account di Google Cloud Console, aktifkan Google Sheets API, lalu tempel kuncinya."}</p>
            <div class="btnrow">
              <button class="btn ghost sm" id="test-sheets">Tes koneksi</button>
              <button class="btn primary sm auto" id="save-sheets">Simpan &amp; aktifkan</button>
            </div>
            <p class="form-error" id="sheet-error" style="min-height:0"></p>
          </section>

          <section class="card">
            <div class="card-head"><div><h3>📦 Data &amp; cadangan</h3><div class="sub">Unduh rekap atau cadangan penuh.</div></div></div>
            <div class="btnrow" style="margin-top:0">
              <button class="btn teal sm" id="do-backfill">Sinkronkan sekarang</button>
              <button class="btn ghost sm" id="dl-csv">Unduh CSV hasil</button>
              <button class="btn ghost sm" id="dl-backup">Unduh backup .json</button>
            </div>
            <label class="field" for="set-school">Nama sekolah (untuk kop laporan PDF)</label>
            <input id="set-school" class="field-input" type="text" maxlength="80" value="${esc(s.school_name || "SMP Negeri 1")}">
            <label class="field" for="set-kkm">Batas ketuntasan (KKM)</label>
            <input id="set-kkm" class="field-input" type="number" min="0" max="100" step="1" value="${s.kkm}">
            <p class="hint">Dipakai pada grafik analisis, status tuntas siswa, dan laporan PDF.</p>
            <div class="btnrow"><button class="btn ghost sm" id="save-kkm">Simpan pengaturan nilai</button></div>
            <p class="hint" style="margin-top:14px">Kode akses pendaftaran guru: <code>${esc(s.guru_code)}</code></p>
          </section>
        </div>

        <section class="card">
          <div class="card-head"><div><h3>📜 Riwayat sinkronisasi</h3><div class="sub">12 aktivitas terakhir.</div></div></div>
          <div class="loglist">${logs}</div>
        </section>`;

      $("#test-sheets").addEventListener("click", async () => {
        const errEl = $("#sheet-error");
        errEl.textContent = "";
        const btn = $("#test-sheets");
        btn.disabled = true; btn.textContent = "Menguji…";
        try {
          const payload = { sheet_id: $("#set-sheet-id").value.trim() };
          const sa = $("#set-sa").value.trim();
          if (sa) payload.service_account_json = sa;
          const res = await api("/api/settings/test-sheets", { method: "POST", body: JSON.stringify(payload) });
          toast(`Berhasil terhubung ke "${res.title}" 🎉`);
        } catch (e) {
          errEl.textContent = e.message;
        } finally {
          btn.disabled = false; btn.textContent = "Tes koneksi";
        }
      });

      $("#save-sheets").addEventListener("click", async () => {
        const errEl = $("#sheet-error");
        errEl.textContent = "";
        const btn = $("#save-sheets");
        btn.disabled = true; btn.textContent = "Menyimpan…";
        try {
          const payload = {
            sheet_id: $("#set-sheet-id").value.trim(),
            tab: $("#set-tab").value.trim(),
            enabled: true,
          };
          const sa = $("#set-sa").value.trim();
          if (sa) payload.service_account_json = sa;
          await api("/api/settings", { method: "POST", body: JSON.stringify(payload) });
          toast("Pengaturan Google Sheets tersimpan & diaktifkan. ✅");
          loadSettings();
        } catch (e) {
          errEl.textContent = e.message;
          btn.disabled = false; btn.textContent = "Simpan & aktifkan";
        }
      });

      $("#save-kkm").addEventListener("click", async () => {
        try {
          await api("/api/settings", {
            method: "POST",
            body: JSON.stringify({
              kkm: Number($("#set-kkm").value),
              school_name: $("#set-school").value.trim(),
            }),
          });
          toast("Pengaturan nilai & sekolah diperbarui.");
          loadSettings();
        } catch (e) { toast(e.message, "error"); }
      });

      $("#do-backfill").addEventListener("click", async () => {
        const btn = $("#do-backfill");
        btn.disabled = true; btn.textContent = "Mengirim…";
        try {
          const res = await api("/api/sync/backfill", { method: "POST", body: "{}" });
          toast(res.rows ? `${res.rows} baris terkirim ke Google Sheets.` : "Tidak ada data yang perlu dikirim.");
          loadSettings();
        } catch (e) {
          toast(e.message, "error");
          btn.disabled = false; btn.textContent = "Sinkronkan sekarang";
        }
      });

      $("#dl-csv").addEventListener("click", () => downloadWithAuth("/api/export.csv"));
      $("#dl-backup").addEventListener("click", () => downloadWithAuth("/api/backup"));
    } catch (e) {
      box.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p></div>`;
    }
  }

  // ------------------------------------------------------------
  // Modal
  // ------------------------------------------------------------
  function openModal(title, bodyHtml) {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = bodyHtml;
    $("#modal").showModal();
  }
  function closeModal() { $("#modal").close(); }

  // ------------------------------------------------------------
  // Binding & init
  // ------------------------------------------------------------
  function bind() {
    $$(".tabbtn").forEach((b) => b.addEventListener("click", () => switchAuthTab(b.dataset.tab)));
    $("#login-form").addEventListener("submit", doLogin);
    $("#register-form").addEventListener("submit", doRegister);
    $("#logout-btn").addEventListener("click", logout);

    $("#reg-role").addEventListener("change", (e) => {
      $("#guru-code-wrap").classList.toggle("hidden", e.target.value !== "guru");
    });

    $$(".chip-demo").forEach((b) => b.addEventListener("click", () => {
      const guru = b.dataset.demo === "guru";
      $("#login-email").value = guru ? "guru@tka.id" : "siswa@tka.id";
      $("#login-password").value = guru ? "guru123" : "siswa123";
      switchAuthTab("login");
      $("#login-form").requestSubmit();
    }));

    $$(".navbtn").forEach((b) => b.addEventListener("click", () => showGuruTab(b.dataset.gnav)));

    $("#modal-close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", (e) => {
      const d = $("#modal");
      const r = d.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeModal();
    });
  }

  async function init() {
    bind();
    switchAuthTab("login");
    if (!state.token) { showAuth(); return; }
    try {
      const res = await api("/api/me");
      state.user = res.user;
      enterApp();
    } catch (e) {
      clearSession();
      showAuth();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
