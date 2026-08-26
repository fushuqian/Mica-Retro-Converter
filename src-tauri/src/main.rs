// Tauri 2.x: release 构建隐藏控制台
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tauri::Manager;

// Windows UIPI: allow drag-drop messages from Explorer before Tauri inits WebView2
// Experience 1595630: process-level ChangeWindowMessageFilter works even without windows-sys crate
#[cfg(target_os = "windows")]
unsafe extern "system" {
    fn ChangeWindowMessageFilter(message: u32, flag: u32) -> i32;
}
#[cfg(target_os = "windows")]
unsafe fn allow_windows_drag_drop_messages() {
    const MSGFLT_ADD: u32 = 1;
    const WM_COPYGLOBALDATA: u32 = 0x0049;
    const WM_COPYDATA: u32         = 0x004A;
    const WM_DROPFILES: u32        = 0x0233;
    ChangeWindowMessageFilter(WM_COPYGLOBALDATA, MSGFLT_ADD);
    ChangeWindowMessageFilter(WM_COPYDATA, MSGFLT_ADD);
    ChangeWindowMessageFilter(WM_DROPFILES, MSGFLT_ADD);
}
#[cfg(not(target_os = "windows"))]
unsafe fn allow_windows_drag_drop_messages() {}


// ──────────────────────────────────────────────────────────
// 共享状态
// ──────────────────────────────────────────────────────────
struct AppState {
    sidecar: Mutex<Option<Child>>,
    port: Mutex<Option<u16>>,
}

impl AppState {
    fn new() -> Self {
        Self {
            sidecar: Mutex::new(None),
            port: Mutex::new(None),
        }
    }
}

// ──────────────────────────────────────────────────────────
// 空闲端口
// ──────────────────────────────────────────────────────────
fn find_free_port() -> Result<u16> {
    for port in 8765u16..9100 {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return Ok(port);
        }
    }
    anyhow::bail!("无可用端口 (8765-9099)")
}

// ──────────────────────────────────────────────────────────
// Commands
// ──────────────────────────────────────────────────────────
#[derive(Serialize, Deserialize, Clone)]
struct BackendInfo {
    port: u16,
    base_url: String,
}

#[tauri::command]
fn get_backend(state: tauri::State<'_, AppState>) -> Result<BackendInfo, String> {
    let port = state
        .port
        .lock()
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "后端尚未启动".to_string())?;
    Ok(BackendInfo {
        port,
        base_url: format!("http://127.0.0.1:{port}"),
    })
}

#[tauri::command]
fn open_files_dialog(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let paths = app
        .dialog()
        .file()
        .set_title("选择视频文件")
        .add_filter(
            "视频文件",
            &[
                "mp4", "mkv", "avi", "mov", "flv", "wmv", "mpg", "mpeg", "m4v",
                "webm", "ts", "m2ts", "vob", "3gp", "rm", "rmvb",
            ],
        )
        .blocking_pick_files()
        .unwrap_or_default();
    Ok(paths.into_iter().map(|p| p.to_string()).collect())
}

#[tauri::command]
fn open_dir_dialog(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let path = app
        .dialog()
        .file()
        .set_title("选择输出目录")
        .blocking_pick_folder();
    Ok(path.map(|p| p.to_string()))
}

// ──────────────────────────────────────────────────────────
// 启动 sidecar
// ──────────────────────────────────────────────────────────
fn spawn_backend(port: u16) -> Result<Child> {
    let script = locate_server_script();
    let python = which_python();
    let child = Command::new(python)
        .arg("-u")
        .arg(script)
        .env("WAC_HOST", "127.0.0.1")
        .env("WAC_PORT", port.to_string())
        .env("PYTHONUNBUFFERED", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .with_context(|| "启动 Python sidecar 失败（请确认已安装 Python 3.8+）")?;
    Ok(child)
}

fn locate_server_script() -> PathBuf {
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("server.py");
    if dev.exists() {
        return dev.canonicalize().unwrap_or(dev);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            for c in [
                exe_dir.join("resources").join("server.py"),
                exe_dir.join("server.py"),
            ] {
                if c.exists() {
                    return c;
                }
            }
        }
    }
    PathBuf::from("server.py")
}

fn which_python() -> String {
    #[cfg(windows)]
    {
        if let Ok(exe) = std::env::current_exe() {
            if let Some(exe_dir) = exe.parent() {
                let emb = exe_dir.join("resources").join("python").join("python.exe");
                if emb.exists() {
                    return emb.to_string_lossy().to_string();
                }
            }
        }
        for n in ["py.exe", "python.exe", "python3.exe"] {
            if let Ok(p) = which_in_path(n) {
                return p;
            }
        }
        "python.exe".to_string()
    }
    #[cfg(not(windows))]
    {
        for n in ["python3", "python"] {
            if let Ok(p) = which_in_path(n) {
                return p;
            }
        }
        "python3".to_string()
    }
}

fn which_in_path(name: &str) -> Result<String> {
    let env = std::env::var_os("PATH").unwrap_or_default();
    for dir in std::env::split_paths(&env) {
        let f = dir.join(name);
        if f.is_file() {
            return Ok(f.to_string_lossy().to_string());
        }
    }
    anyhow::bail!("not found in PATH: {name}")
}

// ──────────────────────────────────────────────────────────
// 健康检查
// ──────────────────────────────────────────────────────────
async fn wait_for_server(port: u16, timeout_ms: u64) -> bool {
    let start = Instant::now();
    while start.elapsed() < Duration::from_millis(timeout_ms) {
        if probe_http(port).await {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(300)).await;
    }
    false
}

async fn probe_http(port: u16) -> bool {
    tokio::task::spawn_blocking(move || -> bool {
        let addr = SocketAddr::new(Ipv4Addr::LOCALHOST.into(), port);
        let mut s = match TcpStream::connect_timeout(&addr, Duration::from_millis(400)) {
            Ok(v) => v,
            Err(_) => return false,
        };
        let _ = s.set_read_timeout(Some(Duration::from_millis(500)));
        let req = "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
        if s.write_all(req.as_bytes()).is_err() {
            return false;
        }
        let mut buf = [0u8; 256];
        let n = s.read(&mut buf).unwrap_or(0);
        let head = String::from_utf8_lossy(&buf[..n]);
        head.starts_with("HTTP/1.1 200") || head.starts_with("HTTP/1.0 200")
    })
    .await
    .unwrap_or(false)
}

// ──────────────────────────────────────────────────────────
// 入口
// ──────────────────────────────────────────────────────────
fn main() {
    // Windows: allow WM_DROPFILES/WM_COPY* messages (UIPI)
    unsafe { allow_windows_drag_drop_messages(); }
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            get_backend,
            open_files_dialog,
            open_dir_dialog
        ])
        .setup(|app| {
            let port = find_free_port().expect("无可用端口");
            match spawn_backend(port) {
                Ok(child) => {
                    {
                        let state: tauri::State<'_, AppState> = tauri::Manager::state(app);
                        *state.sidecar.lock().unwrap() = Some(child);
                        *state.port.lock().unwrap() = Some(port);
                    }
                    let handle = app.handle().clone();
                    tauri::async_runtime::spawn(async move {
                        let ready = wait_for_server(port, 30_000).await;
                        let info = BackendInfo {
                            port,
                            base_url: format!("http://127.0.0.1:{port}"),
                        };
                        let _ = tauri::Emitter::emit(&handle, "backend://ready", &info);
                        if !ready {
                            let _ = tauri::Emitter::emit(
                                &handle,
                                "backend://error",
                                "后端启动超时（30s），请检查 Python 与 ffmpeg 是否可用",
                            );
                        }
                    });
                }
                Err(e) => {
                    eprintln!("[sidecar] 启动失败: {e:#}");
                    let handle = app.handle().clone();
                    tauri::async_runtime::spawn(async move {
                        let _ = tauri::Emitter::emit(
                            &handle,
                            "backend://error",
                            format!("{e:#}"),
                        );
                    });
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // File drop (TAURI NATIVE, 100% reliable for Windows absolute paths)
            if let tauri::WindowEvent::DragDrop(fd) = event {
                use tauri::Emitter;
                match fd {
                    tauri::DragDropEvent::Enter { paths, position: _ } => {
                        let strings: Vec<String> = paths.iter().filter_map(|p| p.to_str().map(|s| s.to_string())).collect();
                        let _ = window.emit("drag://hover", &serde_json::json!({"paths": strings}));
                    }
                    tauri::DragDropEvent::Drop { paths, position: _ } => {
                        let strings: Vec<String> = paths.iter().filter_map(|p| p.to_str().map(|s| s.to_string())).collect();
                        eprintln!("[FileDrop] Dropped {} paths: {:?}", strings.len(), strings);
                        let _ = window.emit("drag://drop", &serde_json::json!({"paths": strings}));
                    }
                    tauri::DragDropEvent::Leave => {
                        let _ = window.emit("drag://cancel", &());
                    }
                    _ => {}
                }
            }
            if let tauri::WindowEvent::Destroyed = event {
                // 主窗口销毁就清理 sidecar
                let handle: tauri::AppHandle = Manager::app_handle(window).clone();
                if let Some(state) = handle.try_state::<AppState>() {
                    if let Ok(mut guard) = state.sidecar.lock() {
                        if let Some(mut child) = guard.take() {
                            #[cfg(windows)]
                            {
                                let _ = Command::new("taskkill")
                                    .args(["/F", "/T", "/PID", &child.id().to_string()])
                                    .stdout(Stdio::null())
                                    .stderr(Stdio::null())
                                    .status();
                            }
                            #[cfg(not(windows))]
                            {
                                let _ = child.kill();
                            }
                            let _ = child.wait();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("运行 Tauri 应用失败");
}
