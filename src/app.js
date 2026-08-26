
(() => {
  'use strict';

  let API_BASE = (location.protocol === 'file:' || window.__TAURI__)
    ? (window.__WAC_API_BASE__ || 'http://127.0.0.1:8765')
    : '';

  const SUPPORTED_EXTS = new Set([
    '.mp4','.mkv','.avi','.mov','.flv','.wmv','.mpg','.mpeg',
    '.m4v','.webm','.ts','.m2ts','.vob','.3gp','.rm','.rmvb'
  ]);

  const dom = {
    mainArea: document.getElementById('mainArea'),
    emptyState: document.getElementById('emptyState'),
    taskList: document.getElementById('taskList'),
    btnBrowse: document.getElementById('btnBrowse'),
    profileSelect: document.getElementById('profileSelect'),
    btnConvert: document.getElementById('btnConvert'),
    btnSettings: document.getElementById('btnSettings'),
    btnOutputDir: document.getElementById('btnOutputDir'),
    outputPath: document.getElementById('outputPath'),
    btnPin: document.getElementById('btnPin'),
    btnMinimize: document.getElementById('btnMinimize'),
    btnClose: document.getElementById('btnClose'),
    
    settingsModal: document.getElementById('settingsModal'),
    btnCloseSettings: document.getElementById('btnCloseSettings'),
    btnSaveSettings: document.getElementById('btnSaveSettings'),
    spinW: document.getElementById('spinW'),
    spinH: document.getElementById('spinH'),
    spinVBit: document.getElementById('spinVBit'),
    spinABit: document.getElementById('spinABit'),
    fpsSelect: document.getElementById('fpsSelect'),
    outputDir: document.getElementById('outputDir'),
    btnPickDir: document.getElementById('btnPickDir'),
    btnClearDir: document.getElementById('btnClearDir'),
    chkLetterbox: document.getElementById('chkLetterbox'),
    chkSubtitle: document.getElementById('chkSubtitle'),
    
    toastContainer: document.getElementById('toastContainer'),
  };

  const state = {
    files: [],
    presets: [],
    presetIndex: 0,
    fpsOptions: [],
    ffmpegOk: false,
    running: false,
    eventSource: null,
    counters: { fileId: 0 },
    lastEventTs: 0,
    alwaysOnTop: false,
  };

  const uid = () => 'f_' + (++state.counters.fileId);

  async function api(method, path, body) {
    const opts = {
      method,
      headers: { 'Accept': 'application/json' },
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(API_BASE + path, opts);
    const text = await resp.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!resp.ok) {
      const msg = (data && data.detail) ? data.detail : (resp.status + ' ' + resp.statusText);
      throw new Error(msg);
    }
    return data;
  }

  function toast(kind, title, msg, ms = 3600) {
    const icons = {
      info: 'ℹ️',
      success: '✅',
      error: '❌',
      warn: '⚠️',
    };
    const el = document.createElement('div');
    el.className = 'toast toast-' + kind;
    el.innerHTML = '<div class="toast-icon" style="font-size:16px;">' + (icons[kind] || icons.info) + '</div><div class="toast-text"><strong>' + title + '</strong>' + (msg ? '<div>' + msg + '</div>' : '') + '</div>';
    dom.toastContainer.appendChild(el);
    setTimeout(() => {
      el.classList.add('toast-out');
      setTimeout(() => el.remove(), 280);
    }, ms);
  }

  function refreshApiBase() {
    const base = (location.protocol === 'file:' || window.__TAURI__)
      ? (window.__WAC_API_BASE__ || 'http://127.0.0.1:8765')
      : '';
    if (base !== API_BASE) {
      API_BASE = base;
      connectEventSource().catch(() => {});
      syncFromServerStatus().catch(() => {});
    } else {
      syncFromServerStatus().catch(() => {});
    }
  }
  window.addEventListener('wac://backend-updated', refreshApiBase);

  async function syncFromServerStatus() {
    try {
      const st = await api('GET', '/api/convert/status');
      if (!st || !st.queue?.length) return;
      const statusByName = st.status || {};
      const progressByName = st.progress || {};
      const outputsByName = st.outputs || {};
      let changed = false;
      for (const f of state.files) {
        const s = statusByName[f.name];
        const p = progressByName[f.name];
        const o = outputsByName[f.name];
        if (typeof p === 'number' && p !== f.progress) { f.progress = p; changed = true; }
        if (typeof s === 'string' && s !== f.status) { f.status = s; changed = true; }
        if (typeof o === 'string' && o !== f.output) { f.output = o; changed = true; }
      }
      if (st.running !== state.running) {
        state.running = Boolean(st.running);
        updateConvertButton();
        changed = true;
      }
      if (changed) {
        for (const f of state.files) {
          const card = dom.taskList.querySelector(`.task-card[data-id="${f.id}"]`);
          if (card) updateTaskCardProgress(card, f);
        }
      }
    } catch (_) {}
  }

  let statusPollTimer = null;
  function startStatusPolling() {
    stopStatusPolling();
    statusPollTimer = setInterval(() => {
      syncFromServerStatus().catch(() => {});
    }, 2000);
  }
  function stopStatusPolling() {
    if (statusPollTimer) { clearInterval(statusPollTimer); statusPollTimer = null; }
  }

  function buildPresetOptions(data) {
    state.presets = data.flat;
    state.fpsOptions = data.fps_options;

    dom.fpsSelect.innerHTML = '';
    for (const [label, val] of state.fpsOptions) {
      const o = document.createElement('option');
      o.value = val === null ? '__source__' : String(val);
      o.textContent = label;
      dom.fpsSelect.appendChild(o);
    }

    dom.profileSelect.innerHTML = '';
    let lastGroup = null;
    for (const p of state.presets) {
      if (lastGroup !== null && p.group !== lastGroup) {
        const sep = document.createElement('option');
        sep.disabled = true;
        sep.textContent = '─── ' + ' '.repeat(40);
        sep.style.color = '#555';
        dom.profileSelect.appendChild(sep);
      }
      const o = document.createElement('option');
      o.value = String(p.index);
      o.textContent = (p.disabled ? '✕ ' : '') + p.name;
      if (p.disabled) o.disabled = true;
      dom.profileSelect.appendChild(o);
      lastGroup = p.group;
    }

    const defaultIdx = state.presets.findIndex(p => !p.disabled);
    state.presetIndex = Math.max(0, defaultIdx);
    dom.profileSelect.value = String(state.presetIndex);
    applyPresetToForm(state.presetIndex);
  }

  function applyPresetToForm(idx) {
    const p = state.presets[idx];
    if (!p) return;
    const v = p.values;
    dom.spinW.value = v.width;
    dom.spinH.value = v.height;
    dom.spinVBit.value = v.video_bitrate;
    dom.spinABit.value = v.audio_bitrate;
    
    if (v.force_fps && v.fps !== null && v.fps !== undefined) {
      const match = state.fpsOptions.findIndex(([, val]) => val !== null && Math.abs(val - Number(v.fps)) < 0.01);
      if (match >= 0) dom.fpsSelect.selectedIndex = match;
      dom.fpsSelect.disabled = true;
    } else {
      dom.fpsSelect.disabled = false;
      dom.fpsSelect.value = '__source__';
    }
  }

  function renderTaskList() {
    const files = state.files;
    
    if (files.length === 0) {
      dom.emptyState.classList.remove('hidden');
      dom.taskList.innerHTML = '';
      updateConvertButton();
      return;
    }
    dom.emptyState.classList.add('hidden');

    const existingIds = new Set(files.map(f => f.id));
    const existingCards = new Map();
    dom.taskList.querySelectorAll('.task-card').forEach(card => {
      if (!existingIds.has(card.dataset.id)) card.remove();
      else existingCards.set(card.dataset.id, card);
    });

    let order = 0;
    for (const f of files) {
      let card = existingCards.get(f.id);
      if (!card) {
        card = createTaskCard(f);
        dom.taskList.appendChild(card);
      } else {
        updateTaskCardProgress(card, f);
      }
      card.style.order = String(order++);
    }
    updateConvertButton();
  }

  function createTaskCard(f) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.dataset.id = f.id;
    
    card.innerHTML = `
      <div class="card-header">
        <div class="card-icon">🎬</div>
        <div class="card-info">
          <div class="card-name-row">
            <span class="chip chip-format"></span>
            <div class="card-name-wrap">
              <div class="card-name" title=""></div>
            </div>
            <button class="card-remove" title="Remove">✖️</button>
          </div>
          <div class="card-chips"></div>
        </div>
      </div>
      <div class="card-progress-row">
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <div class="progress-text"></div>
        <div class="progress-state"></div>
      </div>
    `;
    
    card.querySelector('.card-remove').addEventListener('click', (e) => {
      e.stopPropagation();
      if (state.running) return;
      const i = state.files.findIndex(x => x.id === f.id);
      if (i >= 0) { state.files.splice(i, 1); renderTaskList(); }
    });
    
    updateTaskCardMeta(card, f);
    updateTaskCardProgress(card, f);
    return card;
  }

  function updateTaskCardMeta(card, f) {
    // format chip
    const fmtEl = card.querySelector('.chip-format');
    if (fmtEl) {
      const fmt = fileFormat(f.name);
      fmtEl.textContent = fmt;
      fmtEl.style.display = fmt ? 'inline-flex' : 'none';
    }

    const nameEl = card.querySelector('.card-name');
    nameEl.textContent = f.name;
    nameEl.title = f.path;

    // marquee scroll for long names
    const nameWrap = card.querySelector('.card-name-wrap');
    if (nameWrap) {
      nameWrap.classList.remove('marquee');
      nameEl.style.animationDuration = '';
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (nameEl.scrollWidth > nameWrap.clientWidth + 2) {
            const overflow = nameEl.scrollWidth - nameWrap.clientWidth;
            nameEl.style.setProperty('--marquee-distance', `-${overflow}px`);
            const duration = Math.max(3, overflow / 30);
            nameWrap.classList.add('marquee');
            nameEl.style.animationDuration = duration + 's';
          }
        });
      });
    }
    
    // chips
    const chipsEl = card.querySelector('.card-chips');
    if (f.info && !f.info.error) {
      chipsEl.innerHTML = '';
      const chips = buildChipsForInfo(f.info);
      for (const chip of chips) {
        const el = document.createElement('span');
        el.className = 'chip chip-' + chip.cls;
        el.textContent = chip.text;
        chipsEl.appendChild(el);
      }
      chipsEl.style.display = chips.length ? 'flex' : 'none';
    } else {
      chipsEl.style.display = 'none';
    }
  }

  function updateTaskCardProgress(card, f) {
    const fill = card.querySelector('.progress-fill');
    if (fill) fill.style.width = (f.progress || 0) + '%';
    const pt = card.querySelector('.progress-text');
    if (pt) pt.textContent = (f.progress || 0) + '%';
    
    const stateEl = card.querySelector('.progress-state');
    if (stateEl) {
      stateEl.textContent = f.status || 'Waiting';
      stateEl.className = 'progress-state ' + statusCls(f.status);
    }
  }

  function updateTaskCard(card, f) {
    updateTaskCardMeta(card, f);
    updateTaskCardProgress(card, f);
  }

  function fileFormat(name) {
    const m = name.match(/\.([a-zA-Z0-9]+)$/);
    return m ? m[1].toUpperCase() : '';
  }

  function buildChipsForInfo(info) {
    const chips = [];
    // Video chip: codec resolution fps aspect_ratio bitrate
    if (info.video_codec) {
      const parts = [codecLabel(info.video_codec)];
      if (info.width && info.height) parts.push(info.width + 'x' + info.height);
      if (info.fps) parts.push(info.fps + 'FPS');
      if (info.aspect_ratio) parts.push(info.aspect_ratio);
      if (info.bitrate) parts.push(humanBitrate(info.bitrate));
      chips.push({ cls: 'video', text: '🎬 ' + parts.join(' ') });
    }
    // Audio chip: codec bitrate
    if (info.audio_codec) {
      const parts = [codecLabel(info.audio_codec)];
      if (info.audio_bitrate) parts.push(humanBitrate(info.audio_bitrate));
      chips.push({ cls: 'audio', text: '🔊 ' + parts.join(' ') });
    }
    return chips;
  }

  function updateOutputPathDisplay() {
    const p = dom.outputDir.value;
    if (!p) {
      dom.outputPath.textContent = '同源目录';
      dom.outputPath.title = '输出到源文件所在目录';
    } else {
      dom.outputPath.textContent = p;
      dom.outputPath.title = p;
    }
  }

  function humanSize(bytes) {
    if (!bytes) return '';
    const units = ['B','KB','MB','GB'];
    let i = 0, v = bytes;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return v.toFixed(v >= 100 || i === 0 ? 0 : 1) + ' ' + units[i];
  }

  function humanBitrate(bps) {
    if (!bps) return '';
    if (bps >= 1000000) return Math.round(bps / 1000000) + ' Mbps';
    if (bps >= 1000) return Math.round(bps / 1000) + ' kbps';
    return bps + ' bps';
  }

  function codecLabel(codec) {
    if (!codec) return '';
    const map = {
      'h264': 'H.264', 'hevc': 'H.265', 'av1': 'AV1', 'vp9': 'VP9',
      'vp8': 'VP8', 'mpeg4': 'MPEG-4', 'mpeg2video': 'MPEG-2',
      'mpeg1video': 'MPEG-1', 'wmv2': 'WMV2', 'wmv3': 'WMV3',
      'rv10': 'RealVideo', 'rv20': 'RealVideo 2',
      'libx264': 'H.264', 'libx265': 'H.265', 'libxvid': 'Xvid',
      'libvpx': 'VP8', 'libvpx-vp9': 'VP9',
      'aac': 'AAC', 'mp3': 'MP3', 'opus': 'Opus', 'vorbis': 'Vorbis',
      'ac3': 'AC3', 'ac3_fixed': 'AC3',
      'wmav2': 'WMAv2', 'wma': 'WMA',
      'real_144': 'RealAudio', 'ra_144': 'RealAudio',
      'mp2': 'MP2', 'pcm_s16le': 'PCM', 'pcm_s16be': 'PCM',
      'flac': 'FLAC', 'alac': 'ALAC', 'ape': 'APE',
    };
    return map[codec] || codec.toUpperCase();
  }

  async function fetchFileInfo(path) {
    try {
      const encodedPath = encodeURIComponent(path);
      const data = await api('GET', '/api/files/info?path=' + encodedPath);
      return data;
    } catch (_) {
      return null;
    }
  }

  async function enrichFilesWithMeta(files) {
    for (const f of files) {
      if (f.info) continue;
      fetchFileInfo(f.path).then(info => {
        if (info) {
          f.info = info;
          const card = dom.taskList.querySelector(`.task-card[data-id="${f.id}"]`);
          if (card) updateTaskCardMeta(card, f);
        }
      });
    }
  }

  function statusCls(status) {
    if (!status) return '';
    const s = String(status);
    if (s.includes('Complete') || s.includes('完成')) return 'state-success';
    if (s.includes('Failed') || s.includes('Error') || s.includes('取消')) return 'state-error';
    if (s.includes('Running') || s.includes('转换中')) return 'state-running';
    return '';
  }

  function updateConvertButton() {
    dom.btnConvert.disabled = state.running || state.files.length === 0 || !state.ffmpegOk;
  }

  function setUIRunning(running) {
    state.running = running;
    updateConvertButton();
    
    const controls = [
      dom.btnBrowse,
      dom.profileSelect,
      dom.fpsSelect,
      dom.outputDir,
      dom.btnPickDir,
      dom.btnSettings,
    ];
    controls.forEach(el => {
      if (el) el.disabled = running;
    });
  }

  function addFilePaths(paths, extraMeta = {}) {
    let added = 0;
    const existPaths = new Set(state.files.map(f => f.path));
    for (const p of paths) {
      if (!p || existPaths.has(p)) continue;
      const ext = p.match(/\.([^.\/]+)$/)?.[1]?.toLowerCase();
      if (!ext || !SUPPORTED_EXTS.has('.' + ext)) continue;
      const name = p.split(/[\\\/]/).pop() || p;
      const fileObj = {
        id: uid(),
        path: p,
        name,
        size: extraMeta[p]?.size || 0,
        progress: 0,
        status: 'Waiting',
        output: null,
        info: null,
      };
      state.files.push(fileObj);
      existPaths.add(p);
      added++;
    }
    renderTaskList();
    if (added > 0) toast('success', 'Added ' + added + ' file(s)');
    // async fetch metadata for newly added files
    const newFiles = state.files.filter(f => !f.info);
    if (newFiles.length) enrichFilesWithMeta(newFiles);
    return added;
  }

  async function pickFilesNative() {
    try {
      if (window.__TAURI__) {
        const { invoke } = await import('@tauri-apps/api/core');
        const paths = await invoke('open_files_dialog');
        if (Array.isArray(paths) && paths.length) addFilePaths(paths);
        return;
      }
      // Fallback: try backend (may be disabled in tauri)
      const data = await api('POST', '/api/dialog/open-files');
      if (data?.files?.length) addFilePaths(data.files);
    } catch (e) {
      toast('error', '无法打开文件选择框', e.message || String(e));
    }
  }

  async function pickDirNative() {
    try {
      if (window.__TAURI__) {
        const { invoke } = await import('@tauri-apps/api/core');
        const dir = await invoke('open_dir_dialog');
        if (dir) { dom.outputDir.value = String(dir); updateOutputPathDisplay(); }
        return;
      }
      const data = await api('POST', '/api/dialog/open-dir');
      if (data?.directory) { dom.outputDir.value = data.directory; updateOutputPathDisplay(); }
    } catch (e) {
      toast('error', '无法打开目录选择框', e.message || String(e));
    }
  }

  function setDragHover(on) {
    try {
      const app = document.getElementById('app');
      if (app) app.classList.toggle('dragover', !!on);
      if (dom?.mainArea) dom.mainArea.classList.toggle('dragover', !!on);
    } catch(_) {}
  }

  async function setupDragDrop() {
    // ── Click empty area → picker ──
    if (dom?.mainArea) {
      dom.mainArea.addEventListener('click', (e) => {
        if (e.target === dom.mainArea || e.target.closest('.empty-state')) {
          if (!state.running) pickFilesNative();
        }
      });
    }

    // ══════════════════════════════════════════════════════════════
    // CHANNEL 1 — TAURI NATIVE (PRIMARY for Windows)
    // Requires tauri.conf.json: app.windows[].dragDropEnabled = true
    // Events: tauri://drag-over → drop → drag-leave/cancel
    // ══════════════════════════════════════════════════════════════
    if (window.__TAURI__) {
      try {
        const { listen } = await import('@tauri-apps/api/event');

        // Channel: Rust on_window_event(FileDrop) → emit drag://*
        // Windows 100% reliable absolute Windows paths from OS WM_DROPFILES pipeline.
        await listen('drag://hover', (ev) => {
          console.debug('[DnD] drag://hover', JSON.stringify(ev?.payload));
          setDragHover(true);
        });
        await listen('drag://cancel', () => setDragHover(false));

        await listen('drag://drop', (ev) => {
          setDragHover(false);
          const now = Date.now();
          // Dedupe vs HTML5 fallback (both may fire within same drop)
          try {
            if (window.__lastDragDropTs && now - window.__lastDragDropTs < 500) return;
            window.__lastDragDropTs = now;
            // update closure lastDropAt too
            try { (0, eval)('lastDropAt = ' + now + ';'); } catch(_) {}
          } catch(_) {}

          const payload = (ev?.payload || {});
          const paths = Array.isArray(payload.paths) ? payload.paths : [];
          console.debug('[DnD] drag://drop (Rust FileDrop) paths =', JSON.stringify(paths));

          if (state.running) {
            toast('warn', '转换中，请稍候', '当前任务完成后再添加文件');
            return;
          }
          if (!paths.length) {
            toast('warn', '没有获取到可添加的文件路径');
            return;
          }
          addFilePaths(paths);
          toast('success', '已添加 ' + paths.length + ' 个文件');
        });

        console.log('[setupDragDrop] Rust FileDrop listener attached ✅ (drag://hover/drop/cancel)');
      } catch (err) {
        console.error('[setupDragDrop] Rust drag://* events failed:', err);
        toast('warn', 'Rust 拖放监听失败', String(err?.message || err));
      }
    }

    // ══════════════════════════════════════════════════════════════
    // CHANNEL 2 — HTML5 DnD (FALLBACK + full-window hover feedback)
    // Attached to document so it works ANYWHERE on the window.
    // Skips addFilePaths if Tauri channel succeeded (avoid double-add).
    // ══════════════════════════════════════════════════════════════
    window.addEventListener('dragover', (e) => { e.preventDefault(); }, { passive: false });
    window.addEventListener('drop', (e) => { e.preventDefault(); }, { passive: false });

    let dragCounter = 0;
    const onEnter = (e) => {
      try {
        if (!e.dataTransfer) return;
        const types = Array.from(e.dataTransfer.types || []);
        if (!types.includes('Files')) return;
        dragCounter++;
        setDragHover(true);
      } catch(_) {}
    };
    const onLeave = () => {
      dragCounter = Math.max(0, dragCounter - 1);
      if (dragCounter === 0) setDragHover(false);
    };
    const onOver = (e) => {
      e.preventDefault();
      try { if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; } catch(_) {}
    };
    const onDrop = (e) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter = 0;
      setDragHover(false);
      // Shared dedupe window (Rust drag://drop also writes this key)
      const W = window;
      const now = Date.now();
      if (W.__lastDragDropTs && now - W.__lastDragDropTs < 500) return;
      W.__lastDragDropTs = now;
      handleDropItemsFallback(e.dataTransfer);
    };

    document.addEventListener('dragenter', onEnter, true);
    document.addEventListener('dragover', onOver, true);
    document.addEventListener('dragleave', onLeave, true);
    document.addEventListener('drop', onDrop, true);
  }

  function handleDropItemsFallback(dt) {
    if (state.running) {
      toast('warn', '转换中，请稍候', '当前任务完成后再添加文件');
      return;
    }
    if (!dt) return;
    const collected = [];
    const push = (p, size) => collected.push({ path: String(p || ''), size: Number(size) || 0 });

    const files = dt.files ? Array.from(dt.files) : [];
    for (const f of files) {
      const p = (f && (f.path || f.webkitRelativePath || f.name)) || '';
      if (p) push(p, f.size || 0);
    }

    if (collected.length === 0) {
      try {
        const items = dt.items ? Array.from(dt.items) : [];
        const scanOne = (it) => new Promise((res) => {
          try {
            const ent = typeof it.webkitGetAsEntry === 'function' ? it.webkitGetAsEntry() : null;
            if (!ent) return res();
            const walk = (e) => new Promise((r) => {
              if (!e) return r();
              if (e.isFile) { e.file((ff) => { push(ff.path || ff.name, ff.size); r(); }, () => r()); return; }
              if (e.isDirectory) {
                const rd = e.createReader();
                const drain = () => rd.readEntries(async (batch) => {
                  if (!batch || !batch.length) return r();
                  await Promise.all(Array.from(batch).map(walk));
                  drain();
                }, () => r());
                return drain();
              }
              r();
            });
            walk(ent).then(res);
          } catch(_) { res(); }
        });
        Promise.all(items.map(scanOne)).finally(() => {
          if (collected.length) {
            const paths = collected.map(f => f.path);
            const sizeMap = {};
            collected.forEach(f => { if (f.size) sizeMap[f.path] = { size: f.size }; });
            addFilePaths(paths, sizeMap);
            toast('success', '已添加 ' + paths.length + ' 个文件 (fallback)');
          }
        });
        return;
      } catch(_) {}
    }

    if (collected.length) {
      const paths = collected.map(f => f.path);
      const sizeMap = {};
      collected.forEach(f => { if (f.size) sizeMap[f.path] = { size: f.size }; });
      addFilePaths(paths, sizeMap);
      toast('success', '已添加 ' + paths.length + ' 个文件 (fallback)');
    }
  }

  function connectEventSource() {
    if (state.eventSource) try { state.eventSource.close(); } catch {}
    let url = API_BASE + '/api/events';
    if (state.lastEventTs > 0) url += '?since=' + state.lastEventTs;
    const es = new EventSource(url, { withCredentials: false });
    state.eventSource = es;

    es.addEventListener('message', (ev) => {
      let parsed;
      try { parsed = JSON.parse(ev.data); } catch { return; }
      if (parsed.ts) state.lastEventTs = parsed.ts;
      handleServerEvent(parsed.event, parsed.payload);
    });
  }

  function handleServerEvent(event, payload) {
    switch (event) {
      case 'progress': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) {
          f.progress = payload.percent;
          const card = dom.taskList.querySelector(`.task-card[data-id="${f.id}"]`);
          if (card) updateTaskCardProgress(card, f);
        }
        break;
      }
      case 'file_started': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) {
          f.status = 'Running...'; f.progress = 0;
          const card = dom.taskList.querySelector(`.task-card[data-id="${f.id}"]`);
          if (card) updateTaskCardProgress(card, f);
        }
        break;
      }
      case 'file_finished': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) {
          if (payload.success) {
            f.status = 'Complete';
            f.progress = 100;
            f.output = payload.output;
          } else {
            f.status = 'Failed';
          }
          const card = dom.taskList.querySelector(`.task-card[data-id="${f.id}"]`);
          if (card) updateTaskCardProgress(card, f);
        }
        break;
      }
      case 'all_done': {
        setUIRunning(false);
        stopStatusPolling();
        syncFromServerStatus().catch(() => {});
        const ok = state.files.filter(f => f.status?.includes('Complete')).length;
        const total = state.files.length;
        if (ok === total && total > 0) toast('success', 'All completed', ok + '/' + total + ' files converted');
        else if (ok > 0) toast('warn', 'Partially complete', ok + '/' + total + ' files succeeded');
        else if (total > 0) toast('error', 'Conversion failed', 'Check settings or try again');
        break;
      }
    }
  }

  function collectSettings() {
    let fpsValue = null;
    const fpsSel = dom.fpsSelect.value;
    if (fpsSel !== '__source__') fpsValue = Number(fpsSel);
    return {
      width: Number(dom.spinW.value) || 640,
      height: Number(dom.spinH.value) || 480,
      video_bitrate: Number(dom.spinVBit.value) || 800,
      audio_bitrate: Number(dom.spinABit.value) || 96,
      fps: fpsValue,
    };
  }

  async function startConvert() {
    if (state.running || state.files.length === 0) return;

    for (const f of state.files) { f.progress = 0; f.status = 'Waiting'; f.output = null; }
    renderTaskList();

    const body = {
      files: state.files.map(f => f.path),
      preset_index: state.presetIndex,
      overrides: collectSettings(),
      output_dir: dom.outputDir.value.trim() || null,
      burn_subtitles: dom.chkSubtitle.checked,
      letterbox: dom.chkLetterbox.checked,
    };
    try {
      await api('POST', '/api/convert/start', body);
      setUIRunning(true);
      startStatusPolling();
      toast('info', 'Conversion started', state.files.length + ' file(s) queued');
    } catch (e) {
      toast('error', 'Cannot start conversion', e.message);
    }
  }

  async function cancelConvert() {
    if (!state.running) return;
    try {
      await api('POST', '/api/convert/cancel');
      toast('info', 'Cancellation requested');
    } catch (e) {
      toast('error', 'Cancel failed', e.message);
    }
  }

  async function setupWindowControls() {
    if (!window.__TAURI__) return;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();

      // Init button state from window (best-effort)
      try {
        const onTop = await win.isAlwaysOnTop();
        state.alwaysOnTop = !!onTop;
        dom.btnPin.classList.toggle('active', state.alwaysOnTop);
      } catch (_) {}

      dom.btnMinimize.addEventListener('click', async (e) => {
        try { await win.minimize(); }
        catch (err) { toast('error', '最小化失败', String(err)); }
      });
      dom.btnClose.addEventListener('click', async (e) => {
        try { await win.close(); }
        catch (err) { toast('error', '关闭失败', String(err)); }
      });

      // Fix 3: always-on-top — CALL FIRST, then flip state on success
      dom.btnPin.addEventListener('click', async () => {
        const desired = !state.alwaysOnTop;
        try {
          await win.setAlwaysOnTop(desired);
          state.alwaysOnTop = desired;
          dom.btnPin.classList.toggle('active', state.alwaysOnTop);
          toast('info', state.alwaysOnTop ? '置顶已开启' : '置顶已关闭');
        } catch (err) {
          console.error('[setAlwaysOnTop]', err);
          toast('error', '置顶失败', String(err?.message || err));
        }
      });
    } catch (err) {
      console.error('[setupWindowControls]', err);
      toast('warn', '窗口控制初始化失败');
    }
  }

  function setupSettingsModal() {
    dom.btnSettings.addEventListener('click', () => {
      dom.settingsModal.classList.remove('hidden');
    });
    dom.btnCloseSettings.addEventListener('click', () => {
      dom.settingsModal.classList.add('hidden');
    });
    dom.settingsModal.addEventListener('click', (e) => {
      if (e.target === dom.settingsModal) {
        dom.settingsModal.classList.add('hidden');
      }
    });
    dom.btnSaveSettings.addEventListener('click', () => {
      dom.settingsModal.classList.add('hidden');
      toast('success', 'Settings saved');
    });
  }

  function updateScale() {
    const app = document.getElementById('app');
    if (!app) return;
    // App fills the window directly - no scale transform needed
    app.style.width = '100%';
    app.style.height = '100%';
    app.style.transform = '';
    app.style.left = '';
    app.style.top = '';
    app.style.marginLeft = '';
    app.style.marginTop = '';
  }

  async function init() {
    updateScale();
    window.addEventListener('resize', updateScale);
    
    setupDragDrop();
    setupSettingsModal();
    setupWindowControls();
    
    dom.btnBrowse.addEventListener('click', pickFilesNative);
    dom.btnConvert.addEventListener('click', startConvert);
    dom.profileSelect.addEventListener('change', () => {
      state.presetIndex = Number(dom.profileSelect.value);
      applyPresetToForm(state.presetIndex);
    });
    dom.btnPickDir.addEventListener('click', async () => {
      await pickDirNative();
      updateOutputPathDisplay();
    });
    dom.btnClearDir.addEventListener('click', () => {
      dom.outputDir.value = '';
      updateOutputPathDisplay();
    });
    dom.btnOutputDir.addEventListener('click', async () => {
      await pickDirNative();
      updateOutputPathDisplay();
    });

    try {
      const data = await api('GET', '/api/presets');
      buildPresetOptions(data);
    } catch (e) {
      toast('error', 'Failed to load presets', e.message);
    }

    try {
      const h = await api('GET', '/api/health');
      state.ffmpegOk = !!(h.ffmpeg && h.ffprobe);
      if (!state.ffmpegOk) {
        toast('warn', 'FFmpeg not found', 'Place ffmpeg.exe in ffmpeg/ subfolder', 8000);
      }
      updateConvertButton();
    } catch (e) {
      toast('error', 'Backend not responding', e.message);
    }

    try {
      connectEventSource();
    } catch (_) {}

    document.addEventListener('keydown', (e) => {
      if (state.running) return;
      const tgt = e.target?.tagName;
      if (tgt === 'INPUT' || tgt === 'SELECT' || tgt === 'TEXTAREA') return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault(); pickFilesNative();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!dom.btnConvert.disabled) startConvert();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

