"""
server.py - Win98 ASF 视频转换器后端服务
运行: python server.py
然后浏览器打开 http://127.0.0.1:8765
安装 Tauri 工具链后: npm run tauri dev 即可作为桌面应用运行
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import converter_core as core

SCRIPT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = SCRIPT_DIR / "frontend"

# ────────── 全局转换会话管理 ──────────

class ConvertSession:
    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.queue: list[dict] = []          # 待处理文件列表
        self.current_file: str | None = None
        self.progress: dict[str, int] = {}    # filename -> percent
        self.status: dict[str, str] = {}      # filename -> 状态文本
        self.outputs: dict[str, str] = {}     # filename -> 输出路径
        self.log_lines: list[str] = []
        self.listeners: list[asyncio.Queue] = []
        self.cancel_flag = False
        self.worker_thread: threading.Thread | None = None
        self.subprocess: subprocess.Popen | None = None

    async def broadcast(self, event: str, payload: Any = None):
        msg = json.dumps({"event": event, "payload": payload, "ts": time.time()}, ensure_ascii=False)
        self.log_lines.append(msg)
        if len(self.log_lines) > 2000:
            self.log_lines = self.log_lines[-1000:]
        dead = []
        for q in self.listeners:
            try:
                await q.put(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            self.listeners.remove(q)

    def sync_broadcast(self, event: str, payload: Any = None):
        """供同步 worker 线程调用（通过 loop.call_soon_threadsafe）"""
        msg = json.dumps({"event": event, "payload": payload, "ts": time.time()}, ensure_ascii=False)
        self.log_lines.append(msg)
        if len(self.log_lines) > 2000:
            self.log_lines = self.log_lines[-1000:]

        async def _emit():
            dead = []
            for q in self.listeners:
                try:
                    await q.put(msg)
                except Exception:
                    dead.append(q)
            for q in dead:
                self.listeners.remove(q)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = getattr(SERVER_STATE, "loop", None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_emit(), loop)


class ServerState:
    def __init__(self):
        self.ffmpeg: str | None = None
        self.ffprobe: str | None = None
        self.session: ConvertSession | None = None
        self.loop: asyncio.AbstractEventLoop | None = None


SERVER_STATE = ServerState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SERVER_STATE.ffmpeg = core.find_ffmpeg(SCRIPT_DIR)
    SERVER_STATE.ffprobe = core.find_ffprobe(SCRIPT_DIR)
    SERVER_STATE.loop = asyncio.get_running_loop()
    print(f"[OK] ffmpeg: {SERVER_STATE.ffmpeg}")
    print(f"[OK] ffprobe: {SERVER_STATE.ffprobe}")
    yield


app = FastAPI(title="Win98 ASF Converter", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────── Pydantic Schemas ──────────

class ConvertRequest(BaseModel):
    files: list[str] = Field(..., description="输入文件绝对路径列表")
    preset_index: int = Field(0, description="预设索引")
    overrides: dict = Field(default_factory=dict, description="preset 字段覆盖（分辨率/码率等）")
    output_dir: str | None = Field(None, description="输出目录，None 表示源文件同目录")
    burn_subtitles: bool = Field(True, description="是否自动烧录同名字幕")
    letterbox: bool = Field(True, description="是否 4:3 适配加黑边")


class PresetInfo(BaseModel):
    index: int
    name: str
    group: str
    desc: str = ""
    disabled: bool = False


# ────────── API 路由 ──────────

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ffmpeg": SERVER_STATE.ffmpeg,
        "ffprobe": SERVER_STATE.ffprobe,
        "has_session": SERVER_STATE.session is not None,
        "session_id": SERVER_STATE.session.id if SERVER_STATE.session else None,
    }


@app.get("/api/presets")
def get_presets():
    """返回所有预设列表（含分组信息）"""
    groups: dict[str, list[PresetInfo]] = {}
    flat: list[dict] = []
    for i, p in enumerate(core.PRESETS):
        entry = {
            "index": i,
            "name": p["name"],
            "group": p["group"],
            "desc": p.get("desc", ""),
            "disabled": p.get("disabled", False),
            "values": {
                "width": p["width"],
                "height": p["height"],
                "video_bitrate": p["video_bitrate"],
                "audio_bitrate": p["audio_bitrate"],
                "fps": p.get("fps"),
                "force_fps": p.get("force_fps", False),
                "output_ext": p.get("output_ext"),
                "suffix": p.get("suffix"),
            },
        }
        flat.append(entry)
        groups.setdefault(p["group"], []).append(entry)
    return {
        "flat": flat,
        "groups": {k: [{"index": x["index"], "name": x["name"], "desc": x["desc"], "disabled": x["disabled"]} for x in v] for k, v in groups.items()},
        "fps_options": core.FPS_OPTIONS,
    }


@app.get("/api/presets/{idx}")
def get_preset_detail(idx: int):
    if idx < 0 or idx >= len(core.PRESETS):
        raise HTTPException(404, "preset index out of range")
    return {"index": idx, **core.PRESETS[idx]}


@app.post("/api/convert/start")
def start_conversion(req: ConvertRequest):
    """启动一次批量转换。如果上一次任务还在运行，返回 409。"""
    sess = SERVER_STATE.session
    if sess and sess.worker_thread and sess.worker_thread.is_alive():
        raise HTTPException(409, "当前有转换任务在运行，请先取消或等待完成")

    # 校验 preset
    if req.preset_index < 0 or req.preset_index >= len(core.PRESETS):
        raise HTTPException(400, "preset_index 无效")
    preset = dict(core.PRESETS[req.preset_index])
    if preset.get("disabled"):
        raise HTTPException(400, preset.get("desc", "该预设不可用"))
    # 应用 overrides
    if req.overrides:
        for k, v in req.overrides.items():
            preset[k] = v

    # 校验 ffmpeg
    if not SERVER_STATE.ffmpeg or not os.path.exists(SERVER_STATE.ffmpeg):
        raise HTTPException(503, f"ffmpeg 未找到，期望位置: {SCRIPT_DIR / 'ffmpeg' / 'ffmpeg.exe'}")

    # 校验文件
    valid_files = []
    for p in req.files:
        if os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if ext in core.SUPPORTED_EXTS:
                valid_files.append(p)
    if not valid_files:
        raise HTTPException(400, "没有有效的输入视频文件")

    # 创建会话并启动 worker
    sess = ConvertSession()
    SERVER_STATE.session = sess

    sess.queue = [{"path": p} for p in valid_files]
    for f in sess.queue:
        name = os.path.basename(f["path"])
        sess.progress[name] = 0
        sess.status[name] = "等待中"

    worker = threading.Thread(
        target=_run_conversion_worker,
        args=(sess, preset, SERVER_STATE.ffmpeg, SERVER_STATE.ffprobe,
              req.output_dir, req.burn_subtitles, req.letterbox),
        daemon=True,
    )
    sess.worker_thread = worker
    worker.start()

    return {
        "session_id": sess.id,
        "file_count": len(valid_files),
        "preset": preset["name"],
    }


@app.post("/api/convert/cancel")
def cancel_conversion():
    sess = SERVER_STATE.session
    if not sess:
        return {"ok": False, "msg": "无进行中的任务"}
    sess.cancel_flag = True
    if sess.subprocess:
        try:
            sess.subprocess.kill()
        except Exception:
            pass
    sess.sync_broadcast("log", ">> 用户请求取消 <<")
    return {"ok": True}


@app.get("/api/convert/status")
def convert_status():
    sess = SERVER_STATE.session
    if not sess:
        return {"session_id": None, "running": False, "queue": [], "progress": {}, "status": {}}
    running = bool(sess.worker_thread and sess.worker_thread.is_alive())
    return {
        "session_id": sess.id,
        "running": running,
        "current_file": sess.current_file,
        "queue": [{"path": f["path"], "name": os.path.basename(f["path"])} for f in sess.queue],
        "progress": sess.progress,
        "status": sess.status,
        "outputs": sess.outputs,
    }


@app.get("/api/events")
async def event_stream(since: str | None = None):
    """SSE 事件流。客户端建立长连接后，立即发送一次回放，之后实时推送。
    since 参数兼容：缺失 / None / 空字符串 / 非数字 都视为“从头（或最近 200 条）回放”。"""
    # 兼容：?since=（空字符串）也要视为 None，避免 FastAPI 解析失败
    since_val: float | None = None
    if isinstance(since, str) and since.strip():
        try:
            since_val = float(since.strip())
        except (ValueError, TypeError):
            since_val = None
    sess = SERVER_STATE.session
    if sess is None:
        # 创建空会话，确保后续有地方挂 listener
        sess = ConvertSession()
        SERVER_STATE.session = sess

    q: asyncio.Queue[str] = asyncio.Queue()
    sess.listeners.append(q)

    async def generate():
        try:
            # 先发 replay（recent logs）
            yield "retry: 3000\n\n"
            for line in sess.log_lines[-200:]:
                if since_val is None or json.loads(line).get("ts", 0) >= since_val:
                    yield f"data: {line}\n\n"
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        except asyncio.CancelledError:
            try:
                sess.listeners.remove(q)
            except ValueError:
                pass
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/dialog/open-files")
def dialog_open_files():
    """打开系统文件选择对话框。返回选中文件路径列表。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise HTTPException(500, f"无法打开文件对话框: {e}")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    files = filedialog.askopenfilenames(
        title="选择视频文件",
        filetypes=[
            ("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.mpg *.mpeg *.m4v *.webm *.ts *.m2ts *.vob *.3gp *.rm *.rmvb"),
            ("所有文件", "*.*"),
        ],
    )
    root.destroy()
    # 过滤非支持扩展名
    valid = [f for f in files if os.path.splitext(f)[1].lower() in core.SUPPORTED_EXTS]
    return {"files": valid}


@app.post("/api/dialog/open-dir")
def dialog_open_dir():
    """打开系统目录选择对话框。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise HTTPException(500, f"无法打开目录对话框: {e}")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    d = filedialog.askdirectory(title="选择输出目录")
    root.destroy()
    return {"directory": d if d else None}


@app.get("/api/files/validate")
def validate_files(paths: str):
    """GET ?paths=p1|p2|p3 批量校验文件是否存在且为支持的视频格式，同时返回元数据"""
    result = []
    for p in paths.split("|"):
        p = p.strip()
        if not p:
            continue
        exists = os.path.isfile(p)
        ext_ok = os.path.splitext(p)[1].lower() in core.SUPPORTED_EXTS
        item = {"path": p, "exists": exists, "supported": ext_ok, "size": os.path.getsize(p) if exists else 0}
        if exists and ext_ok and SERVER_STATE.ffprobe:
            try:
                info = core.probe_video_info(SERVER_STATE.ffprobe, p)
                if "error" not in info:
                    item["info"] = info
            except Exception:
                pass
        result.append(item)
    return {"items": result}


@app.get("/api/files/info")
def get_file_info(path: str):
    """GET ?path=<filepath> 返回单个文件的视频元数据"""
    if not path:
        raise HTTPException(400, "path is required")
    if not os.path.isfile(path):
        raise HTTPException(404, "file not found")
    if not SERVER_STATE.ffprobe:
        raise HTTPException(503, "ffprobe not available")
    info = core.probe_video_info(SERVER_STATE.ffprobe, path)
    if "error" in info:
        raise HTTPException(500, info["error"])
    return info


# ────────── 前端静态文件 ──────────

@app.get("/")
def index_html():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/app.js")
def app_js():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")

@app.get("/styles.css")
def styles_css():
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")

@app.get("/assets/{name}")
def static_asset(name: str):
    f = FRONTEND_DIR / "assets" / name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


# ────────── Worker ──────────

def _run_conversion_worker(sess: ConvertSession, preset: dict,
                          ffmpeg: str, ffprobe: str | None,
                          output_dir: str | None, burn_subs: bool, letterbox: bool):
    """在独立线程中顺序处理队列中的文件。通过 sync_broadcast 推送事件。"""

    def log(msg: str):
        sess.sync_broadcast("log", msg)

    log(">> 开始批量转换 <<")
    log(f"   预设: {preset['name']}")

    try:
        for entry in sess.queue:
            if sess.cancel_flag:
                break
            input_file = entry["path"]
            name = os.path.basename(input_file)
            sess.current_file = name

            sess.status[name] = "转换中…"
            sess.sync_broadcast("file_started", {"name": name, "path": input_file})
            log(f"=== 开始转换: {name} ===")

            # 1. 时长
            duration = core.get_media_duration(ffprobe, input_file)
            if duration:
                log(f"  时长: {duration:.1f} 秒")

            # 2. 字幕
            subtitle = None
            if burn_subs:
                subtitle = core.find_subtitle_for_video(input_file)
                if subtitle:
                    log(f"  发现字幕: {os.path.basename(subtitle)}")

            # 3. 输出路径
            output_file = core.resolve_output_path(input_file, preset, output_dir)

            # 4. 命令
            cmd = core.build_ffmpeg_command(ffmpeg, input_file, output_file, preset, subtitle, letterbox)
            log("  命令: " + " ".join(shlex.quote(c) for c in cmd))

            # 5. 启动子进程（合并 stderr/stdout，ffmpeg 进度在 stderr）
            try:
                sess.subprocess = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except Exception as e:
                sess.status[name] = f"失败: 无法启动 ffmpeg ({e})"
                sess.sync_broadcast("file_finished", {"name": name, "success": False, "info": f"启动失败: {e}"})
                log(f"=== 失败: {name} (启动失败 {e}) ===")
                continue

            last_pct = -1
            assert sess.subprocess.stdout is not None
            for raw_line in sess.subprocess.stdout:
                if sess.cancel_flag:
                    try:
                        sess.subprocess.kill()
                    except Exception:
                        pass
                    break
                line = raw_line.strip()
                if not line:
                    continue
                log(line)
                pct = core.parse_ffmpeg_progress(line, duration)
                if pct is not None and pct != last_pct:
                    last_pct = pct
                    sess.progress[name] = pct
                    sess.sync_broadcast("progress", {"name": name, "percent": pct})

            sess.subprocess.wait()
            exit_code = sess.subprocess.returncode
            sess.subprocess = None

            if sess.cancel_flag:
                sess.status[name] = "已取消"
                sess.sync_broadcast("file_finished", {"name": name, "success": False, "info": "已取消"})
                try:
                    if os.path.exists(output_file):
                        os.remove(output_file)
                except OSError:
                    pass
                log(f"=== 已取消: {name} ===")
                continue

            if exit_code == 0 and os.path.exists(output_file):
                sess.progress[name] = 100
                sess.status[name] = "完成 ✓"
                sess.outputs[name] = output_file
                sess.sync_broadcast("progress", {"name": name, "percent": 100})
                sess.sync_broadcast("file_finished", {"name": name, "success": True, "output": output_file})
                log(f"=== 完成: {os.path.basename(output_file)} ===")
            else:
                sess.status[name] = f"失败: ffmpeg 退出码 {exit_code}"
                sess.sync_broadcast("file_finished", {"name": name, "success": False, "info": f"ffmpeg 退出码 {exit_code}"})
                log(f"=== 失败: {name} (exit={exit_code}) ===")

    except Exception as exc:  # 顶级兜底
        log(f"[FATAL] worker 异常: {exc!r}")
        sess.sync_broadcast("error", {"type": "worker_exception", "info": repr(exc)})

    finally:
        sess.current_file = None
        sess.sync_broadcast("all_done", {"cancelled": sess.cancel_flag})
        log(">> 全部任务完成 <<")


# ────────── 入口 ──────────

def main():
    import uvicorn
    host = os.environ.get("WAC_HOST", "127.0.0.1")
    port = int(os.environ.get("WAC_PORT", "8765"))
    print(f"→ Win98 ASF 转换器启动: http://{host}:{port}")
    print(f"→ 按 Ctrl+C 停止")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
