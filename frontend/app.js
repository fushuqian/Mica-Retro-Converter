/* ============================================================
   Win98 ASF Converter - 前端逻辑
   纯原生 JS，零依赖；SSE 事件推送 + REST API
   ============================================================ */

(() => {
  'use strict';

  // ────────── 配置 ──────────
  const API_BASE = (location.protocol === 'file:' || window.__TAURI__)
    ? (window.__WAC_API_BASE__ || 'http://127.0.0.1:8765')
    : '';

  const SUPPORTED_EXTS = new Set([
    '.mp4','.mkv','.avi','.mov','.flv','.wmv','.mpg','.mpeg',
    '.m4v','.webm','.ts','.m2ts','.vob','.3gp','.rm','.rmvb'
  ]);

  // ────────── DOM 引用 ──────────
  const $ = (id) => document.getElementById(id);
  const dom = {
    statusDot: $('statusDot'),
    statusText: $('statusText'),
    dropZone: $('dropZone'),
    fileTable: $('fileTable'),
    emptyHint: $('emptyHint'),
    queueCount: $('queueCount'),

    presetSelect: $('presetSelect'),
    presetDesc: $('presetDesc'),
    outputDir: $('outputDir'),
    outDirHint: $('outDirHint'),
    btnPickDir: $('btnPickDir'),
    btnClearDir: $('btnClearDir'),
    spinW: $('spinW'),
    spinH: $('spinH'),
    spinVBit: $('spinVBit'),
    spinABit: $('spinABit'),
    fpsSelect: $('fpsSelect'),
    chkLetterbox: $('chkLetterbox'),
    chkSubtitle: $('chkSubtitle'),

    logBody: $('logBody'),
    btnClearLog: $('btnClearLog'),

    btnAddFiles: $('btnAddFiles'),
    btnRemoveSel: $('btnRemoveSel'),
    btnClearAll: $('btnClearAll'),
    btnCancel: $('btnCancel'),
    btnConvert: $('btnConvert'),

    toastContainer: $('toastContainer'),
  };

  // ────────── 应用状态 ──────────
  const state = {
    files: [],                  // { id, path, name, size, progress, status, output, selected }
    presets: [],                // 预设列表 (presets API 返回的 flat)
    presetIndex: 0,
    fpsOptions: [],
    forceFps: false,
    ffmpegOk: false,
    running: false,
    eventSource: null,
    counters: { fileId: 0 },
    lastEventTs: 0,
  };

  const uid = () => `f_${++state.counters.fileId}`;

  // ────────── HTTP 工具 ──────────
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
      const msg = (data && data.detail) ? data.detail : `${resp.status} ${resp.statusText}`;
      throw new Error(msg);
    }
    return data;
  }

  // ────────── Toast ──────────
  function toast(kind, title, msg, ms = 3600) {
    const icons = {
      info: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
      success: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      error: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warn: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    };
    const el = document.createElement('div');
    el.className = `toast toast-${kind}`;
    el.innerHTML = `${icons[kind] || icons.info}<div class="toast-text"><strong>${title}</strong>${msg ? `<div>${msg}</div>` : ''}</div>`;
    dom.toastContainer.appendChild(el);
    setTimeout(() => {
      el.classList.add('toast-out');
      setTimeout(() => el.remove(), 280);
    }, ms);
  }

  // ────────── 日志面板 ──────────
  function appendLog(kind, text) {
    const line = document.createElement('div');
    line.className = `log-line log-ev-${kind}`;
    const d = new Date();
    const ts = `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
    line.innerHTML = `<span class="ts">${ts}</span>` + escapeHtml(text);
    dom.logBody.appendChild(line);
    // 限制条数
    const overflow = dom.logBody.children.length - 600;
    if (overflow > 0) {
      for (let i = 0; i < overflow; i++) dom.logBody.firstElementChild?.remove();
    }
    dom.logBody.scrollTop = dom.logBody.scrollHeight;
  }
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function classifyLog(text) {
    const t = String(text);
    if (/^\[警告\]|failed|error|fail/i.test(t)) return 'warn';
    if (/\[OK\]|完成|success|===\s*完成/.test(t)) return 'ok';
    if (/失败|exit=\d+|ffmpeg 退出码/.test(t)) return 'err';
    if (/^>> |===\s*开始/.test(t)) return 'info';
    return 'log';
  }

  // ────────── 预设 UI ──────────
  function buildPresetOptions(data) {
    state.presets = data.flat;
    state.fpsOptions = data.fps_options;

    // FPS 下拉
    dom.fpsSelect.innerHTML = '';
    for (const [label, val] of state.fpsOptions) {
      const o = document.createElement('option');
      o.value = val === null ? '__source__' : String(val);
      o.textContent = label;
      dom.fpsSelect.appendChild(o);
    }

    // Preset 下拉（带分组 + 分隔）
    dom.presetSelect.innerHTML = '';
    let lastGroup = null;
    for (const p of state.presets) {
      if (lastGroup !== null && p.group !== lastGroup) {
        const sep = document.createElement('option');
        sep.disabled = true;
        sep.textContent = '─── ' + ' '.repeat(40);
        sep.style.color = 'var(--border-normal)';
        dom.presetSelect.appendChild(sep);
      }
      const o = document.createElement('option');
      o.value = String(p.index);
      o.textContent = (p.disabled ? '✕  ' : '   ') + p.name;
      if (p.disabled) {
        o.disabled = true;
        o.style.color = 'var(--text-tertiary)';
      }
      dom.presetSelect.appendChild(o);
      lastGroup = p.group;
    }

    // 默认选第一个
    const defaultIdx = state.presets.findIndex(p => !p.disabled);
    state.presetIndex = Math.max(0, defaultIdx);
    dom.presetSelect.value = String(state.presetIndex);
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
    state.forceFps = v.force_fps;

    // fps
    if (v.force_fps && v.fps !== null && v.fps !== undefined) {
      const match = state.fpsOptions.findIndex(([, val]) => val !== null && Math.abs(val - Number(v.fps)) < 0.01);
      if (match >= 0) dom.fpsSelect.selectedIndex = match;
      dom.fpsSelect.disabled = true;
    } else {
      dom.fpsSelect.disabled = false;
      dom.fpsSelect.value = '__source__';
    }

    dom.presetDesc.textContent = p.desc || '';
  }

  // ────────── 队列渲染 ──────────
  function renderQueue() {
    const files = state.files;
    dom.queueCount.textContent = `${files.length} 项`;

    if (files.length === 0) {
      dom.emptyHint.style.display = '';
      // 清空所有 file-row
      [...dom.fileTable.querySelectorAll('.file-row')].forEach(n => n.remove());
      updateConvertButton();
      return;
    }
    dom.emptyHint.style.display = 'none';

    // 以 id 为 key 做最小增量更新
    const existingRows = new Map();
    dom.fileTable.querySelectorAll('.file-row').forEach(row => {
      existingRows.set(row.dataset.id, row);
    });
    const newIds = new Set(files.map(f => f.id));

    // 移除已不存在的
    for (const [id, row] of existingRows) {
      if (!newIds.has(id)) row.remove();
    }

    // 按顺序生成/更新
    let order = 0;
    for (const f of files) {
      let row = existingRows.get(f.id);
      if (!row) {
        row = createFileRow(f);
        dom.fileTable.appendChild(row);
      } else {
        updateFileRow(row, f);
      }
      row.style.order = String(order++);
    }
    updateConvertButton();
  }

  function humanSize(bytes) {
    if (!bytes) return '';
    const units = ['B','KB','MB','GB'];
    let i = 0, v = bytes;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function statusCls(status) {
    if (!status) return 'state-pending';
    const s = String(status);
    if (s.includes('完成')) return 'state-success';
    if (s.includes('失败') || s.includes('取消')) return 'state-error';
    if (s.includes('转换中')) return 'state-running';
    return 'state-pending';
  }
  function statusBarCls(status) {
    if (!status) return '';
    const s = String(status);
    if (s.includes('完成')) return 'success';
    if (s.includes('失败') || s.includes('取消')) return 'error';
    return '';
  }

  function createFileRow(f) {
    const row = document.createElement('div');
    row.className = 'file-row';
    row.dataset.id = f.id;
    row.addEventListener('click', () => {
      if (state.running) return;
      f.selected = !f.selected;
      row.classList.toggle('selected', f.selected);
    });
    const FILM = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg>`;
    const X = `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
    row.innerHTML = `
      <div class="file-icon">${FILM}</div>
      <div class="file-info">
        <div class="file-name" title=""></div>
        <div class="file-meta">
          <span class="file-size"></span>
          <span class="file-path-tip"></span>
        </div>
      </div>
      <div class="progress-col">
        <div class="progress-bar"><div class="bar-fill"></div></div>
        <div class="progress-meta">
          <span class="progress-pct">0%</span>
          <span class="progress-state state-pending">等待中</span>
        </div>
      </div>
      <button type="button" class="btn-remove" title="移除">${X}</button>
    `;
    row.querySelector('.btn-remove').addEventListener('click', (e) => {
      e.stopPropagation();
      if (state.running) return;
      const i = state.files.findIndex(x => x.id === f.id);
      if (i >= 0) { state.files.splice(i, 1); renderQueue(); }
    });
    updateFileRow(row, f);
    return row;
  }

  function updateFileRow(row, f) {
    row.classList.toggle('selected', !!f.selected);
    const qName = row.querySelector('.file-name');
    qName.textContent = f.name;
    qName.title = f.path;
    row.querySelector('.file-size').textContent = humanSize(f.size) || '未知大小';
    const dir = f.path ? f.path.replace(/[\\/][^\\/]*$/, '') : '';
    row.querySelector('.file-path-tip').textContent = dir.length > 45 ? '…' + dir.slice(-45) : dir;

    const fill = row.querySelector('.bar-fill');
    fill.style.width = `${f.progress || 0}%`;
    row.querySelector('.progress-pct').textContent = `${f.progress || 0}%`;
    const pState = row.querySelector('.progress-state');
    pState.textContent = f.status || '等待中';
    pState.className = 'progress-state ' + statusCls(f.status);
    const bar = row.querySelector('.progress-bar');
    bar.className = 'progress-bar ' + statusBarCls(f.status);
  }

  function setUIRunning(running) {
    state.running = running;
    dom.statusDot.className = 'status-dot ' + (running ? 'busy' : (state.ffmpegOk ? '' : 'idle'));
    dom.statusText.textContent = running ? '转换进行中…' : (state.ffmpegOk ? '就绪' : 'FFmpeg 未就绪');

    dom.btnConvert.disabled = running || state.files.length === 0 || !state.ffmpegOk;
    dom.btnCancel.disabled = !running;

    for (const el of [dom.btnAddFiles, dom.btnRemoveSel, dom.btnClearAll,
      dom.presetSelect, dom.spinW, dom.spinH, dom.spinVBit, dom.spinABit,
      dom.fpsSelect, dom.chkLetterbox, dom.chkSubtitle, dom.outputDir,
      dom.btnPickDir, dom.btnClearDir, dom.dropZone]) {
      if (el) el.style.pointerEvents = running ? 'none' : '';
      if (el && (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'SELECT')) {
        if (el.id === 'btnCancel') continue;
        el.disabled = running;
      }
    }
  }
  function updateConvertButton() {
    dom.btnConvert.disabled = state.running || state.files.length === 0 || !state.ffmpegOk;
  }

  // ────────── 添加文件 ──────────
  function addFilePaths(paths, extraMeta = {}) {
    let added = 0;
    const existPaths = new Set(state.files.map(f => f.path));
    for (const p of paths) {
      if (!p || existPaths.has(p)) continue;
      const ext = p.match(/\.([^.\\/]+)$/)?.[1]?.toLowerCase();
      if (!ext || !SUPPORTED_EXTS.has('.' + ext)) continue;
      const name = p.split(/[\\/]/).pop() || p;
      state.files.push({
        id: uid(),
        path: p,
        name,
        size: extraMeta[p]?.size || 0,
        progress: 0,
        status: '等待中',
        output: null,
        selected: false,
      });
      existPaths.add(p);
      added++;
    }
    renderQueue();
    if (added > 0) toast('success', `已添加 ${added} 个文件`, added < paths.length ? `（跳过了 ${paths.length - added} 个不支持或重复项）` : '');
    else if (paths.length > 0) toast('warn', '没有添加任何文件', '文件不被支持或已在队列中');
    return added;
  }

  async function pickFilesNative() {
    try {
      const data = await api('POST', '/api/dialog/open-files');
      if (data?.files?.length) {
        addFilePaths(data.files);
      }
    } catch (e) {
      toast('error', '无法打开文件对话框', e.message);
    }
  }

  async function pickDirNative() {
    try {
      const data = await api('POST', '/api/dialog/open-dir');
      if (data?.directory) {
        dom.outputDir.value = data.directory;
      }
    } catch (e) {
      toast('error', '无法打开目录对话框', e.message);
    }
  }

  function scanFilesFromEntries(items, cb) {
    // DataTransferItem / File API 递归文件夹。返回 list of File
    const all = [];
    const walkers = [];
    function walk(ent, path) {
      return new Promise((resolve) => {
        if (ent.isFile) {
          ent.file((file) => {
            file.__webkitRelativePath = (path ? path + '/' : '') + file.name;
            all.push(file);
            resolve();
          }, () => resolve());
        } else if (ent.isDirectory) {
          const reader = ent.createReader();
          const allEntries = [];
          function readBatch() {
            reader.readEntries((batch) => {
              if (!batch.length) {
                Promise.all(allEntries.map(e => walk(e, (path ? path + '/' : '') + ent.name))).then(resolve);
              } else {
                allEntries.push(...batch);
                readBatch();
              }
            }, () => resolve());
          }
          readBatch();
        } else resolve();
      });
    }
    for (const it of items) {
      const ent = it.webkitGetAsEntry?.() || null;
      if (ent) walkers.push(walk(ent, ''));
      else {
        const f = it.getAsFile?.();
        if (f) all.push(f);
      }
    }
    Promise.all(walkers).then(() => cb(all));
  }

  // ────────── 拖放事件（dropZone） ──────────
  function setupDropZone() {
    const dz = dom.dropZone;
    dz.addEventListener('click', () => { if (!state.running) pickFilesNative(); });

    let dragCounter = 0;
    const enter = (e) => { e.preventDefault(); dragCounter++; dz.classList.add('dragover'); };
    const leave = (e) => { e.preventDefault(); dragCounter--; if (dragCounter <= 0) { dragCounter = 0; dz.classList.remove('dragover'); } };
    const over  = (e) => { e.preventDefault(); };
    dz.addEventListener('dragenter', enter);
    dz.addEventListener('dragover', over);
    dz.addEventListener('dragleave', leave);
    dz.addEventListener('drop', (e) => {
      e.preventDefault();
      dragCounter = 0;
      dz.classList.remove('dragover');
      handleDropItems(e.dataTransfer);
    });

    // 整页拖入时显示大遮罩
    let winMask = null;
    let winCounter = 0;
    window.addEventListener('dragenter', (e) => {
      if (!e.dataTransfer || !Array.from(e.dataTransfer.types).includes('Files')) return;
      e.preventDefault();
      winCounter++;
      if (!winMask) {
        winMask = document.createElement('div');
        winMask.className = 'window-drop-mask';
        winMask.innerHTML = `<div class="inner">
          <svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#22aee6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
          <h2>释放鼠标以添加文件</h2>
          <p>支持视频文件与包含视频的文件夹</p>
        </div>`;
        document.body.appendChild(winMask);
      }
    });
    window.addEventListener('dragover', (e) => {
      if (Array.from(e.dataTransfer?.types || []).includes('Files')) e.preventDefault();
    });
    const clearMask = () => {
      winCounter--;
      if (winCounter <= 0) {
        winCounter = 0;
        if (winMask) { winMask.remove(); winMask = null; }
      }
    };
    window.addEventListener('dragleave', (e) => { if (e.dataTransfer) clearMask(); });
    window.addEventListener('drop', (e) => {
      if (!Array.from(e.dataTransfer?.types || []).includes('Files')) return;
      if (winMask) { winMask.remove(); winMask = null; winCounter = 0; }
      if (e.target.closest('#dropZone')) return; // dropZone 自己处理
      e.preventDefault();
      handleDropItems(e.dataTransfer);
    });

    function handleDropItems(dt) {
      if (state.running) { toast('warn', '转换进行中', '请等待当前任务完成后再添加文件'); return; }
      if (dt.items && dt.items.length && dt.items[0].webkitGetAsEntry) {
        scanFilesFromEntries(dt.items, (files) => {
          const paths = files.map(f => f.path || f.webkitRelativePath || (f.__webkitRelativePath || f.name));
          // 非 Tauri 环境浏览器下无法拿到真实本地路径；使用服务端验证兜底
          addViaLocalValidation(files, paths);
        });
      } else if (dt.files) {
        addViaLocalValidation(Array.from(dt.files), Array.from(dt.files).map(f => f.path || f.name));
      }
    }

    function addViaLocalValidation(fileObjs, hintedPaths) {
      // 浏览器沙箱下 file.path 可能为空；Tauri 环境下 file.path 为真实路径
      const realPaths = fileObjs.map(f => f.path).filter(Boolean);
      if (realPaths.length === fileObjs.length && realPaths.length > 0) {
        const sizeMap = {};
        fileObjs.forEach((f, i) => { sizeMap[realPaths[i]] = { size: f.size }; });
        addFilePaths(realPaths, sizeMap);
        return;
      }
      // 浏览器（无 Tauri）：path 拿不到；提示用户用「添加文件」按钮
      if (realPaths.length === 0) {
        toast('warn', '浏览器无法获取真实路径', '检测到您使用的是纯浏览器模式。请改用「添加文件」按钮通过系统对话框选择，这样才能知道文件路径进行转换。');
        pickFilesNative();
      } else {
        addFilePaths(realPaths);
      }
    }
  }

  // ────────── SSE 事件源 ──────────
  function connectEventSource() {
    if (state.eventSource) try { state.eventSource.close(); } catch {}
    const url = `${API_BASE}/api/events?since=${state.lastEventTs || ''}`;
    const es = new EventSource(url, { withCredentials: false });
    state.eventSource = es;

    es.addEventListener('open', () => {
      appendLog('info', '[SSE] 事件连接已建立');
    });
    es.addEventListener('error', () => {
      appendLog('warn', '[SSE] 连接中断，3 秒后重试…');
    });
    es.addEventListener('message', (ev) => {
      let parsed;
      try { parsed = JSON.parse(ev.data); } catch { return; }
      if (parsed.ts) state.lastEventTs = parsed.ts;
      handleServerEvent(parsed.event, parsed.payload);
    });
  }

  function handleServerEvent(event, payload) {
    switch (event) {
      case 'log': {
        const level = classifyLog(payload);
        appendLog(level, String(payload));
        break;
      }
      case 'progress': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) { f.progress = payload.percent; renderQueue(); }
        break;
      }
      case 'file_started': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) { f.status = '转换中…'; f.progress = 0; renderQueue(); }
        break;
      }
      case 'file_finished': {
        const f = state.files.find(x => x.name === payload.name);
        if (f) {
          if (payload.success) {
            f.status = '完成 ✓';
            f.progress = 100;
            f.output = payload.output;
          } else {
            f.status = `失败: ${payload.info || '未知'}`;
          }
          renderQueue();
        }
        break;
      }
      case 'all_done': {
        setUIRunning(false);
        const ok = state.files.filter(f => f.status?.includes('完成')).length;
        const total = state.files.length;
        if (ok === total && total > 0) toast('success', `全部完成 ✓`, `${ok}/${total} 个文件转换成功`);
        else if (ok > 0) toast('warn', `部分完成`, `${ok}/${total} 个文件成功`);
        else if (total > 0) toast('error', '转换失败', '所有文件均未成功，请查看日志');
        break;
      }
      case 'error': {
        appendLog('err', `[服务器错误] ${payload?.type}: ${payload?.info}`);
        break;
      }
    }
  }

  // ────────── 开始转换 / 取消 ──────────
  function collectSettings() {
    let fpsValue = null;
    const fpsSel = dom.fpsSelect.value;
    if (fpsSel !== '__source__') fpsValue = Number(fpsSel);
    else {
      // 若 forceFps，从 preset 取
      const p = state.presets[state.presetIndex];
      if (p?.values.force_fps) fpsValue = Number(p.values.fps);
    }
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

    // 重置每个文件的进度与状态
    for (const f of state.files) { f.progress = 0; f.status = '等待中'; f.output = null; }
    renderQueue();

    const body = {
      files: state.files.map(f => f.path),
      preset_index: state.presetIndex,
      overrides: collectSettings(),
      output_dir: dom.outputDir.value.trim() || null,
      burn_subtitles: dom.chkSubtitle.checked,
      letterbox: dom.chkLetterbox.checked,
    };
    try {
      const res = await api('POST', '/api/convert/start', body);
      setUIRunning(true);
      appendLog('info', `已启动会话 ${res.session_id}，共 ${res.file_count} 个文件（${res.preset}）`);
    } catch (e) {
      toast('error', '无法启动转换', e.message);
    }
  }

  async function cancelConvert() {
    if (!state.running) return;
    try {
      await api('POST', '/api/convert/cancel');
      toast('info', '已发送取消请求', '正在中断 ffmpeg…');
    } catch (e) {
      toast('error', '取消失败', e.message);
    }
  }

  // ────────── 启动初始化 ──────────
  async function init() {
    // 1. 绑定按钮/控件事件
    setupDropZone();

    dom.btnAddFiles.addEventListener('click', pickFilesNative);
    dom.btnRemoveSel.addEventListener('click', () => {
      state.files = state.files.filter(f => !f.selected);
      renderQueue();
    });
    dom.btnClearAll.addEventListener('click', () => {
      if (state.running) return;
      if (state.files.length === 0) return;
      state.files = [];
      renderQueue();
      toast('info', '列表已清空', '', 1800);
    });
    dom.btnConvert.addEventListener('click', startConvert);
    dom.btnCancel.addEventListener('click', cancelConvert);
    dom.btnClearLog.addEventListener('click', () => {
      dom.logBody.innerHTML = '<div class="log-line log-ev-warn"><span class="ts">—</span>日志已清空</div>';
    });
    dom.btnPickDir.addEventListener('click', pickDirNative);
    dom.btnClearDir.addEventListener('click', () => {
      dom.outputDir.value = '';
    });

    dom.presetSelect.addEventListener('change', () => {
      state.presetIndex = Number(dom.presetSelect.value);
      applyPresetToForm(state.presetIndex);
    });

    // 2. 拉取预设列表
    try {
      const data = await api('GET', '/api/presets');
      buildPresetOptions(data);
    } catch (e) {
      appendLog('err', `获取预设失败: ${e.message}`);
      toast('error', '无法加载预设列表', e.message);
    }

    // 3. 健康检查
    try {
      const h = await api('GET', '/api/health');
      state.ffmpegOk = !!(h.ffmpeg && h.ffprobe);
      if (state.ffmpegOk) {
        dom.statusDot.className = 'status-dot';
        dom.statusText.textContent = '就绪';
        appendLog('ok', `FFmpeg: ${h.ffmpeg}`);
        appendLog('ok', `FFprobe: ${h.ffprobe}`);
      } else {
        dom.statusDot.className = 'status-dot idle';
        dom.statusText.textContent = '缺少 FFmpeg';
        appendLog('err', '未找到 ffmpeg.exe / ffprobe.exe。请放到 ./ffmpeg/ 子目录。');
        toast('warn', '未检测到 FFmpeg', '请把 ffmpeg.exe 与 ffprobe.exe 放到项目目录下的 ffmpeg/ 子文件夹中', 8000);
      }
      updateConvertButton();
    } catch (e) {
      dom.statusDot.className = 'status-dot idle';
      dom.statusText.textContent = '服务器未连接';
      appendLog('err', `无法连接后端: ${e.message}`);
    }

    // 4. 连接 SSE
    try {
      connectEventSource();
    } catch (e) {
      appendLog('warn', `SSE 连接失败: ${e.message}`);
    }

    // 5. 键盘快捷键
    document.addEventListener('keydown', (e) => {
      if (state.running) return;
      const tgt = e.target?.tagName;
      if (tgt === 'INPUT' || tgt === 'SELECT' || tgt === 'TEXTAREA') return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault(); pickFilesNative();
      }
      if (e.key === 'Delete') {
        const anySel = state.files.some(f => f.selected);
        if (anySel) { state.files = state.files.filter(f => !f.selected); renderQueue(); }
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!dom.btnConvert.disabled) startConvert();
      }
    });
  }

  // boot
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
