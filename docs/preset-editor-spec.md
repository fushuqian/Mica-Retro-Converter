# 预设编辑器 · 方案设计文档 (Preset Editor Design Spec)

> 版本：v1.0  ·  日期：2026-08-28  ·  目标版本：v3.1

---

## 1. 背景与目标

### 1.1 现状

当前 **WPF 版（v3.0 / `wpf/` 目录）** 的预设全部**硬编码**在 `wpf/Core/Presets.cs` 里（共 15 条，来自 `Win98Converter.Core.Presets.All` 静态列表）：

| 分组 | 预设数 |
|---|---|
| Win98 流媒体 (WMV2+WMA2/ASF) | 3 |
| VCD/SVCD (MPEG-1/2) | 4 |
| DVD (MPEG-2 + AC-3) | 2 |
| MPEG-4 AVI (DivX / XviD) | 2 |
| RealNetworks (RM) | 2 |
| Disabled / 不可用（占位） | 1 |

**存在的问题：**
1. 用户无法**新建/修改/删除**自定义预设
2. 无法调整 WMV2 码率/分辨率等参数的极限值（必须改源码+重新编译）
3. 无法把个人常用预设**分享给朋友**（无导入/导出）
4. 禁用预设（如 RMVB）只存在于代码注释里，UI 上无法恢复
5. 无法标记"默认预设"快速启动

### 1.2 目标

| # | 目标 | 验收标准 |
|---|---|---|
| P0 | 可增删改查预设 | 新建/重命名/复制/删除 100% 不崩溃 |
| P0 | 持久化到磁盘 | 关闭程序再打开自定义预设仍存在 |
| P0 | 与现有硬编码预设 **无冲突并存** | 内置预设只读显示+可复制副本编辑，用户预设可读写 |
| P1 | 导入导出 JSON | 单预设 / 全量预设 两种方式，文件格式可被他人直接打开 |
| P1 | 标记默认预设 | 启动时默认选中该预设 |
| P1 | 预设分组管理 | 按 "Win98 流媒体 / VCD / DVD / 我的预设" 分组显示 |
| P2 | 参数校验器 | 防止用户把码率设成 0k / 分辨率 > 4096 这类明显会导致 ffmpeg 失败的输入 |
| P2 | "从当前预设复制" 快捷入口 | 点击现有预设 → 复制一份可编辑 |

---

## 2. 数据模型 (Schema)

### 2.1 单个预设对象 (`PresetRecord`)

> **基准**：已完全对齐现有 `wpf/Core/Preset.cs` C# record 的字段，保持 JSON 序列化后双方可互通（方便未来 WPF 端直接读取同一文件）。

```ts
interface PresetRecord {
    /** UUID v4，唯一标识，不可变 */
    id: string;
    /** 显示名，如 "我的自定义 低码率 Win98" */
    name: string;
    /** 分组名（分类），如 "Win98 流媒体" / "我的预设" */
    group: string;
    /** 是否为 BUILT-IN（内置预设 = 只读，编辑器中显示锁图标 🔒） */
    builtIn: boolean;

    /* ---------- 编码核心参数 ---------- */
    /** ffmpeg -c:v，如 wmv2 / mpeg2video / libxvid */
    videoCodec: string;
    /** ffmpeg -c:a，如 wmav2 / mp2 / libmp3lame / ac3_fixed */
    audioCodec: string;
    /** ffmpeg -f ，容器/封装格式，如 asf / vcd / dvd / avi / rm */
    container: string;
    /** 输出文件扩展名（不含点），如 asf / mpg / vob / avi / rm */
    outputExt: string;
    /** 文件名后缀，输出 = 原名_`{suffix}`.ext，默认值参考内置 */
    suffix: string;

    /* ---------- 视频参数 ---------- */
    /** 宽度（px）。0 或 <0 表示"保持源"。 */
    width: number;
    /** 高度（px）。0 或 <0 表示"保持源"。 */
    height: number;
    /** 视频码率（kbps）。注意是 k 值（不带 k 单位字符）。 */
    videoBitrateKbps: number;
    /** 强制帧率。null = 保持源帧率。精度到 3 位小数（23.976）。 */
    fps: number | null;
    /** 是否在 ffmpeg 里强制 -r (即便源 fps 相同也写) */
    forceFps: boolean;
    /** 四字符码 FourCC，如 DX50 / XVID；留空 = 不写 -vtag */
    videoTag: string;

    /* ---------- 音频参数 ---------- */
    /** 音频码率（kbps） */
    audioBitrateKbps: number;
    /** 音频采样率 Hz，常用 44100 / 48000 / 22050 / 8000 */
    audioSampleRateHz: number;

    /* ---------- 高级 ---------- */
    /** 附加 ffmpeg 命令参数数组（字符串一条一个）。例：["-g","18"] */
    extraArgs: string[];
    /** 描述（会显示在预设卡片下方小字 / tooltip），中文可空。 */
    description: string;
    /** 禁用 = true。禁止出现在主界面预设下拉（但编辑器里可见）。用于 RMVB 这种明确无法生成的。 */
    disabled: boolean;

    /* ---------- 元数据 ---------- */
    createdAt: number;   // unix ms
    updatedAt: number;   // unix ms
    /** 上次修改人/来源. 预设导入时写 "imported:/path/xxx.json" */
    source?: string;
}
```

### 2.2 内置预设列表资源文件（`presets.builtin.json`）

> 把原来硬编码在 `Presets.cs` 的 15 条预设**抽出来做静态 JSON 资源**，未来两边都从同一份资源加载。
> 内置预设的 `id` 固定写死（不是随机 UUID），便于跨版本识别。

```json
{
  "_formatVersion": 1,
  "_comment": "BUILT-IN PRESETS · 只读，不要手工编辑本文件。用户自定义预设写在 presets.user.json",
  "presets": [
    {
      "id": "builtin-win98-recommended",
      "name": "推荐 (Win98 兼容)",
      "group": "Win98 流媒体",
      "builtIn": true,
      "videoCodec": "wmv2", "audioCodec": "wmav2",
      "container": "asf", "outputExt": "asf", "suffix": "win98",
      "width": 640, "height": 480, "videoBitrateKbps": 800,
      "fps": null, "forceFps": false, "videoTag": "",
      "audioBitrateKbps": 96, "audioSampleRateHz": 44100,
      "extraArgs": [],
      "description": "640×480 · WMV2+WMA2 in ASF · Pentium 2/3 流畅播放",
      "disabled": false,
      "createdAt": 1750000000000, "updatedAt": 1750000000000,
      "source": "builtin:v3.1"
    },
    {
      "id": "builtin-vcd-pal",
      "name": "VCD - PAL",
      "group": "VCD/SVCD 光盘 (MPEG-1/2)",
      "builtIn": true,
      "videoCodec": "mpeg1video", "audioCodec": "mp2",
      "container": "vcd", "outputExt": "mpg", "suffix": "vcd",
      "width": 352, "height": 288, "videoBitrateKbps": 1150,
      "fps": 25, "forceFps": true,
      "audioBitrateKbps": 224, "audioSampleRateHz": 44100,
      "extraArgs": ["-g", "18"],
      "description": "352×288@25fps · 1150k MPEG-1 + 224k MP2 · PAL 标准",
      "disabled": false,
      "createdAt": 1750000000000, "updatedAt": 1750000000000,
      "source": "builtin:v3.1"
    }
    /* ... 其余 13 条按现有 Presets.cs 逐字段转换 ... */
  ]
}
```

### 2.3 用户预设文件（`presets.user.json`）

格式与内置相同，只是 `builtIn = false`，编辑器只**写入本文件**，内置文件永不改动。

```json
{
  "_formatVersion": 1,
  "_comment": "USER PRESETS · 可读写。WPF 和 Tauri 双端共享同一路径。",
  "defaultPresetId": "user-my-watch-party-001",
  "presets": [
    {
      "id": "user-my-watch-party-001",
      "name": "我的·低流量观看派对",
      "group": "我的预设",
      "builtIn": false,
      "videoCodec": "wmv2", "audioCodec": "wmav2",
      "container": "asf", "outputExt": "asf", "suffix": "win98",
      "width": 400, "height": 300, "videoBitrateKbps": 450,
      "fps": 24, "forceFps": false, "videoTag": "",
      "audioBitrateKbps": 64, "audioSampleRateHz": 44100,
      "extraArgs": [],
      "description": "朋友电脑非常老的机器使用",
      "disabled": false,
      "createdAt": 1756320000000,
      "updatedAt": 1756320000000,
      "source": "manual"
    }
  ]
}
```

---

## 3. 磁盘布局与跨端共享

### 3.1 持久化路径

统一存在 Tauri/WPF 各自的 `app_data_dir`，但**允许用户手动选择 "同步目录" 放到 Syncthing 文件夹里**。

| 端 | 默认路径 |
|---|---|
| **Tauri (Rust)** | `%APPDATA%\app.mica.retro.converter\presets\` |
| **WPF (.NET)** | `%APPDATA%\Win98Converter\presets\`（可迁移合并到上条 ← P1） |
| **文件** | `presets.builtin.json`（与 exe 同级，嵌入资源或打包分发）<br>`presets.user.json`（可读写，用户级）<br>`presets.imported-<timestamp>.backup.json`（每次覆盖写前自动备份） |

### 3.2 Rust 文件位置参考（app_data_dir 获取方式）

```rust
// src-tauri/Cargo.toml 已经有 tauri 2.0, 直接用：
use tauri::{Manager, path::BaseDirectory};

fn presets_dir(app: &tauri::AppHandle) -> std::path::PathBuf {
    app.path()
        .resolve(Path::new("presets"), BaseDirectory::AppData)
        .expect("failed to resolve app data presets dir")
}
```

---

## 4. 前后端 API 契约

### 4.1 Rust 侧新增的 Tauri Commands（`src-tauri/src/main.rs`）

```rust
// ---------- 读 ----------
#[tauri::command]
async fn presets_list_all() -> Result<Vec<PresetRecord>, String>;
// 返回内置 + 用户预设的并集。内置预设 builtIn=true, UI 上显示 🔒

#[tauri::command]
async fn presets_get(id: String) -> Result<PresetRecord, String>;

#[tauri::command]
async fn presets_get_default() -> Result<Option<String>, String>;
// 返回 defaultPresetId（用户上次选的默认预设 id）。None = 第一个内置推荐。

// ---------- 写 ----------
#[tauri::command]
async fn presets_upsert(preset: PresetRecord) -> Result<String, String>;
// Create / Update 二合一。id = "" / null 时新建并分配 uuid；
// 已有 id 时若 builtIn=true → 报错 "无法覆盖内置预设"；
// 返回新/更新的 id。

#[tauri::command]
async fn presets_delete(id: String) -> Result<(), String>;
// 删除 user preset。删除前检查是否是 builtIn → 拒绝。

#[tauri::command]
async fn presets_duplicate(src_id: String, new_name: String) -> Result<String, String>;
// 快速复制。新 preset builtIn=false，id = uuid，name = new_name。
// **这是 built-in 预设被用户编辑的唯一合法通道**。

#[tauri::command]
async fn presets_set_default(id: String) -> Result<(), String>;

// ---------- 导入 / 导出 ----------
#[tauri::command]
async fn presets_export_to_file(ids: Vec<String>, dst_path: String) -> Result<usize, String>;
// ids = [] 表示导出全量（内置+用户？或仅用户？→ 本方案：仅用户预设）
// dst_path 由前端 dialog 选。文件格式 = 2.3 节 presets.user.json 同形。
// 返回导出条数。

#[tauri::command]
async fn presets_import_from_file(src_path: String, mode: ImportMode) -> Result<ImportReport, String>;
// mode = "merge"(默认, 同 id 冲突保留现有 | 冲突改名 " (冲突 1)") / "replace"(清空 user 预设后整体覆盖)
// ImportReport = { imported: n, skipped: n, conflicts: [ {old_id, conflict_name} ] }

// ---------- 校验 ----------
#[tauri::command]
async fn presets_validate(preset: PresetRecord) -> Result<Vec<PresetIssue>, ()>;
// 非阻塞校验，返回 warnings + errors 列表。见 §5.3 校验规则。
```

### 4.2 前端侧 (`src/app.js` → `window.__TAURI__`)

```js
// 初始化：读取 presets_list_all() 并替换 state.presets
// 下拉渲染时按 group 字段分組 <optgroup label="Win98 流媒体">

// UI 结构：
//  - 现有 <select id="presetSelect"> 保持不变，继续用预设列表
//  - 齿轮⚙️ modal → 新增一个 Tab: "预设编辑器"
//     ├── 左侧：预设树（按 group 分组，🔒 图标标记内置）
//     └── 右侧：参数编辑器表单（保存/复制/删除/设默认/导入导出按钮）
```

---

## 5. 预设编辑器 UI 设计

### 5.1 形式（方案 A，最轻集成）

**不新建独立窗口**。直接放进现有"⚙️ 设置"模态框，增加第三个 Tab：

```
┌───────────── 设置 ─────────────┐
│ Tab: 通用  │ 预设编辑器 │ 关于 │
├────────────────────────────────┤
│                                │
│ 左侧列表 (45%)   │ 右侧表单    │
│ ┌────────────┐   │ ┌────────┐  │
│ │ 🔒 Win98.. │   │ 参数编辑│  │
│ │ 🔒 高质量.. │   │ 表单    │  │
│ │ 🔒 最小体积 │   │         │  │
│ │ 我的预设   │   │         │  │
│ │   🟢 低流量│   │         │  │
│ │   · 自定义│   │ [保存][删]│  │
│ │ [+新建] [复制]│   │ [设默认]  │  │
│ │ [导入] [导出]│   │ [导入/导]│  │
│ └────────────┘   │ └────────┘  │
└────────────────────────────────┘
```

**宽度调整**：模态框从现在 300px → 临时扩展到 **580px**（设置宽就够用），关闭模态后不影响主窗口宽度 320px。

### 5.2 右侧表单分区

#### ① 基础信息（Basic）
- `name`（输入框）
- `group`（下拉，可新建分组：输入时自动补全现有的 "Win98 流媒体"、"VCD/SVCD"、"DVD"、"我的预设"）
- `id`（只读，灰色显示 UUID）
- `description`（多行 textarea，4 行）
- 复选框：`disabled`（禁用预设）
- 若 `builtIn=true` → 整个表单加灰色遮罩 + 顶部提示 **"内置预设 · 不可编辑，请点 [复制为副本] 新建"**

#### ② 视频参数（Video）
| 字段 | 控件 |
|---|---|
| `videoCodec` | 预置下拉（wmv2 / mpeg1video / mpeg2video / mpeg4 / libxvid / rv10 / **自定义输入**） |
| `width × height` | 两个 number input，单位 px；旁边有快捷按钮 `320×240 / 640×480 / 800×600 / 720×480` |
| `videoBitrateKbps` | number input（单位 kbps），旁边快捷 `300 / 800 / 1500 / 2500 / 6000` |
| `fps` | 下拉：`保持原帧 / 23.976 / 24 / 25 / 29.97 / 30 / 自定义数字` |
| `forceFps` | checkbox（强制写 -r） |
| `videoTag` | 4 字符输入（DX50 / XVID） |

#### ③ 音频参数（Audio）
| 字段 | 控件 |
|---|---|
| `audioCodec` | 预置下拉 + 自定义 |
| `audioBitrateKbps` | 数字 + 快捷 `32 / 64 / 96 / 128 / 224 / 448` |
| `audioSampleRateHz` | 下拉：`8000 / 22050 / 44100 / 48000 / 自定义` |

#### ④ 封装与输出（Container）
- `container`（ffmpeg `-f`）：下拉 + 自定义
- `outputExt`（扩展名）：联动自动填（用户可改）
- `suffix`（文件名后缀）：3~16 字符输入

#### ⑤ 高级（Advanced）
- `extraArgs`：每一行一个参数（可动态增行 `+ -`），类似 Dockerfile ARG 数组。显示预览：
  ```
  extraArgs 预览：-g 18 -bf 2
  ```
- 下面加一行红色小字提示："参数会被直接拼到 ffmpeg 命令末尾，错误会导致转换失败"

### 5.3 参数校验器（保存前自动触发）

| 规则 | 级别 | 说明 |
|---|---|---|
| `name` 非空且 ≤ 32 字符 | ❌ Error | |
| `group` 非空且 ≤ 32 字符 | ❌ Error | |
| `videoCodec` 非空 | ❌ Error | |
| `container` 非空 | ❌ Error | |
| `outputExt` 非空且纯字母 | ❌ Error | |
| `width/height` 范围 ∈ [0, 1, 4096]（0=保持源） | ❌ Error | |
| `videoBitrateKbps` ∈ [16, 50000] | ❌ Error | |
| `audioBitrateKbps` ∈ [8, 6144] | ❌ Error | |
| `fps` ∈ (0, 240] | ❌ Error | |
| `audioSampleRateHz` ∈ [4000, 384000] | ❌ Error | |
| 同一组内有重名预设 | ⚠️ Warning | 不阻止保存，仅提示 |
| `container=asf` 且 `videoCodec != wmv2/wmv1` | ⚠️ Warning | 告知"这组搭配兼容性非常低" |
| `container=dvd/vcd/svcd` 但 fps 未强制 | ⚠️ Warning | 建议 forceFps=true 否则刻录会出错 |
| `width/height` 奇数（非 2 倍数） | ⚠️ Warning | 很多编码器要求偶数分辨率 |

保存按钮上方显示：`❌ 3 个错误 · ⚠️ 1 个警告`，错误存在时按钮 disabled。

---

## 6. 内置预设的 "只读策略"

为了避免用户不小心改坏官方默认预设，采用**锁 + 复制**模型：

```
┌────────────────────────────────────────────────────┐
│ 用户点击 "推荐 (Win98 兼容)" 内置预设                │
│   → 右侧全灰遮罩 + 顶部：🔒 内置预设（只读）          │
│                 [ 复制为副本 ➕ ]                    │
│                                                      │
│ 用户点 [复制为副本]                                   │
│   → 弹框 "新名称：推荐 (Win98 兼容) - 副本"（可编辑） │
│     "分组：我的预设"（默认）                         │
│   → 确定后调用 presets_duplicate()                   │
│   → 左侧自动跳到新副本，表单解锁可编辑 ✅             │
└────────────────────────────────────────────────────┘
```

内置预设的删除按钮永远 disabled。删除用户预设时二次确认：`"确定删除预设 [xxx] 吗？此操作不可恢复"`。

---

## 7. 导入 / 导出文件格式

### 7.1 单预设导出（小文件）

文件：`My Low Bitrate Party.preset.json`
```json
{
  "_formatVersion": 1,
  "_kind": "single-preset",
  "_exportedAt": 1756320000000,
  "preset": { ...PresetRecord... }
}
```

### 7.2 全量预设导出（备份 / 分享）

文件：`my-presets-bundle.json`
```json
{
  "_formatVersion": 1,
  "_kind": "bundle",
  "_exportedAt": 1756320000000,
  "_note": "User's personal Mica Retro Converter preset bundle",
  "defaultPresetId": "...",
  "presets": [ /* 只包含 builtIn=false 的用户预设，不重复导出内置 */ ]
}
```

### 7.3 导入冲突处理策略

```rust
enum ImportMode {
    /// 合并（默认）
    Merge,
    /// 覆盖（先清空所有用户预设再导入）
    Replace,
}
```

**Merge 模式下 id 冲突处理**：
- 保留本地已有（不动）
- 在 ImportReport.conflicts 里告诉前端冲突条数
- UI 上再问用户："是否覆盖本地已存在的 N 个预设？" 再走一遍 Replace-these-N API

---

## 8. 转换核心集成改动

### 8.1 WPF 端（`wpf/Core/Presets.cs` 要改成 "混合加载"）

```diff
- public static IReadOnlyList<Preset> All { get; } = new List<Preset> { ...hardcoded 15... };
+ public static PresetRegistry Load()
+ {
+     // 1. 读取嵌入资源 presets.builtin.json（15 条内置）
+     // 2. 读取 %APPDATA%\...\presets.user.json（用户自定义）
+     // 3. 合并 + 按 Id 去重 + builtIn 标记保持内置不被覆盖
+     // 4. 保留 defaultPresetId
+ }
```

*注：`ConversionEngine.BuildFfmpegCommand` 本身**完全不用改**，因为字段和 `PresetRecord` 一一对应，只是把 C# `record Preset` 的字段从硬编码列表改为 `PresetRecord` 映射即可。*

### 8.2 Tauri / Python FastAPI 端（server.py + converter_core.py）

FastAPI 的 `POST /api/convert` 参数 `preset` 直接改成 `PresetRecord` 整个对象（或把对应字段拆开传），而不是现在的 `selectedProfile` 字符串索引。`converter_core.py` 内部不再查全局预设列表，直接用传入的 preset 对象构造 ffmpeg 命令。

---

## 9. 实施阶段与里程碑（Roadmap）

### Phase 1 · 基础可读写（MVP，预计 1~2 天）

```
1. 抽离 presets.builtin.json（15 条硬编码 → JSON）
2. WPF Presets.cs 改为从 JSON 加载
3. Rust 侧 Commands：list / get / upsert / delete / duplicate / set_default
4. 持久化 presets.user.json（读写）
5. 前端⚙️设置 Tab "预设编辑器"：左侧树 + 右侧表单 + 保存/删除
6. 内置预设只读策略 + 复制副本
```

**验收**：可以新建一个用户预设 → 关程序再打开 → 主界面下拉里能看到 → 用它转换一次视频成功。

### Phase 2 · 导入导出 + 校验（3~5 天）

```
7. presets_validate() + 校验规则实现
8. Export File（单/全量）
9. Import File（Merge / Replace 两种 mode + 冲突报告）
10. "从当前预设复制"主界面快捷按钮（可选）
```

### Phase 3 · 体验打磨（2 天）

```
11. 分组折叠/展开
12. 预设图标（按 container 显示 📼ASF / 💿VCD / 📀DVD / 🎞️AVI / 📻RM）
13. 搜索预设（按 name/codec/group）
14. 快捷键：Ctrl+S 保存、Del 删除
```

---

## 10. 风险与回退

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 用户编辑的参数组合导致 ffmpeg 必失败（例：wmv2 码率=30000k） | 转换 100% 报错，用户觉得是 bug | **Phase 1 先不做**，靠 Phase 2 的 presets_validate + ⚠️ 警告面板 |
| 内置和用户预设 id 重复 | 列表错乱 | 用户预设 id 前缀统一 `user-{uuid}`；内置前缀固定 `builtin-*`；upsert 时强校验 |
| JSON 文件格式升级（未来加字段） | 老版本读取崩溃 | `_formatVersion` 字段 + 迁移函数链，从 v1→v2→... 升级 |
| WPF 和 Tauri 两端写同一份 user.json | 并发文件损坏 | 每次 upsert 前先 `.backup.json` 自动备份；加文件锁（或采用写入 temp + rename 原子写入） |

**回退方案**：如果预设编辑器上线出现大规模崩溃，只需把 `presets.user.json` 移走，重启后自动回到只有内置预设的"干净状态"，因为内置预设是打包进 exe 的 JSON 资源，不会损坏。

---

## 11. 不做清单 (Out of Scope)

- ❌ 实时预览 ffmpeg 参数（需要调用 ffprobe / ffmpeg dry-run，太复杂，后期再议）
- ❌ 预设之间的参数 diff 比较工具
- ❌ 云端同步 / 多端自动同步（留给用户 Syncthing / 云盘覆盖 JSON 解决）
- ❌ 预设市场 / 社区分享（未来有独立后端服务再说）
