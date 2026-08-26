"""
main.py - Win98 ASF 视频转换器主程序

使用方法:
  1. 把 ffmpeg.exe 和 ffprobe.exe 放到本程序所在目录的 ffmpeg/ 子文件夹
     (下载: https://www.gyan.dev/ffmpeg/builds/  ->  essentials build)
  2. 运行 python main.py
  3. 拖入视频文件 -> 选择输出目录 -> 点击"开始转换"
  4. 转换完成后把 .asf 文件拷贝到 Windows 98 机器用 WMP 6.4 即可播放
"""

import sys
import os
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QProgressBar,
    QComboBox, QSpinBox, QCheckBox, QLineEdit, QFileDialog, QGroupBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QFrame, QSplitter, QAbstractItemView,
)

from converter import (
    PRESETS, FPS_OPTIONS, find_ffmpeg, find_ffprobe, ConversionWorker,
)

# 支持的输入视频扩展名
SUPPORTED_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".mpg", ".mpeg",
    ".m4v", ".webm", ".ts", ".m2ts", ".vob", ".3gp", ".rm", ".rmvb",
}


class DropArea(QFrame):
    """拖拽接收区域"""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Box)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumHeight(110)
        self.setStyleSheet(
            "DropArea {"
            "  border: 2px dashed #888;"
            "  border-radius: 8px;"
            "  background-color: #f8f8f8;"
            "}"
            "DropArea:hover {"
            "  border-color: #2c7fb8;"
            "  background-color: #eaf4fb;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        title = QLabel("拖放视频文件到此处")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #444;")
        sub = QLabel("支持 MP4/MKV/AVI/MOV/FLV/MPG 等常见格式 · 可一次拖入多个")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(title)
        layout.addWidget(sub)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "DropArea {"
                "  border: 2px solid #2c7fb8;"
                "  border-radius: 8px;"
                "  background-color: #d6ebf7;"
                "}"
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "DropArea {"
            "  border: 2px dashed #888;"
            "  border-radius: 8px;"
            "  background-color: #f8f8f8;"
            "}"
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "DropArea {"
            "  border: 2px dashed #888;"
            "  border-radius: 8px;"
            "  background-color: #f8f8f8;"
            "}"
        )
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    ext = os.path.splitext(path)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        files.append(path)
                elif os.path.isdir(path):
                    # 拖入文件夹：扫描其中所有支持的视频文件
                    for fn in os.listdir(path):
                        if os.path.splitext(fn)[1].lower() in SUPPORTED_EXTS:
                            files.append(os.path.join(path, fn))
        if files:
            self.files_dropped.emit(files)
        event.acceptProposedAction()


class FileTable(QTableWidget):
    """文件列表表格，每行显示文件名、状态、进度"""
    COL_NAME = 0
    COL_STATUS = 1
    COL_PROGRESS = 2
    COL_OUTPUT = 3

    def __init__(self, parent=None):
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["文件", "状态", "进度", "输出路径"])
        self.horizontalHeader().setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(self.COL_PROGRESS, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(self.COL_OUTPUT, QHeaderView.Stretch)
        self.setColumnWidth(self.COL_PROGRESS, 200)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self._files = []   # 保存原始路径

    def add_files(self, paths):
        new_added = 0
        existing = set(self._files)
        for p in paths:
            if p in existing:
                continue
            existing.add(p)
            self._files.append(p)
            row = self.rowCount()
            self.insertRow(row)
            # 文件名
            name_item = QTableWidgetItem(os.path.basename(p))
            name_item.setToolTip(p)
            self.setItem(row, self.COL_NAME, name_item)
            # 状态
            status_item = QTableWidgetItem("待转换")
            status_item.setForeground(QColor("#666"))
            self.setItem(row, self.COL_STATUS, status_item)
            # 进度条
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setFormat("0%")
            self.setCellWidget(row, self.COL_PROGRESS, bar)
            # 输出路径（初始为空）
            self.setItem(row, self.COL_OUTPUT, QTableWidgetItem(""))
            new_added += 1
        return new_added

    def get_all_files(self):
        return list(self._files)

    def find_row_by_name(self, name):
        for r in range(self.rowCount()):
            item = self.item(r, self.COL_NAME)
            if item and item.text() == name:
                return r
        return -1

    def set_status(self, row, text, color="#333"):
        item = self.item(row, self.COL_STATUS)
        if item:
            item.setText(text)
            item.setForeground(QColor(color))

    def set_progress(self, row, percent):
        bar = self.cellWidget(row, self.COL_PROGRESS)
        if bar:
            bar.setValue(percent)
            bar.setFormat(f"{percent}%")

    def set_output(self, row, path):
        item = self.item(row, self.COL_OUTPUT)
        if item:
            item.setText(path)
            item.setToolTip(path)

    def remove_selected(self):
        rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
        for r in rows:
            self.removeRow(r)
            if 0 <= r < len(self._files):
                del self._files[r]

    def clear_all(self):
        self.setRowCount(0)
        self._files.clear()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Win98 ASF 视频转换器")
        self.resize(900, 700)

        script_dir = Path(__file__).resolve().parent
        self.script_dir = script_dir
        self.ffmpeg = find_ffmpeg(script_dir)
        self.ffprobe = find_ffprobe(script_dir)
        self.worker = None

        self._build_ui()
        self._check_ffmpeg()

    # ---------- UI 构建 ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 标题
        title = QLabel("Win98 ASF 视频转换器")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c7fb8;")
        root.addWidget(title)

        # 拖拽区
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        root.addWidget(self.drop_area)

        # 拆分: 上方文件表 + 下方日志
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # 文件表 + 设置面板 横向布局
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        # 文件表
        self.file_table = FileTable()
        top_layout.addWidget(self.file_table, stretch=3)

        # 右侧设置面板
        self.settings_group = self._build_settings_group()
        top_layout.addWidget(self.settings_group, stretch=1)

        splitter.addWidget(top_widget)

        # 日志
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        log_group.setMinimumHeight(120)
        splitter.addWidget(log_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        # 底部按钮栏
        btn_bar = QHBoxLayout()
        self.btn_add = QPushButton("+ 添加文件…")
        self.btn_remove = QPushButton("− 移除选中")
        self.btn_clear = QPushButton("✕ 清空列表")
        self.btn_convert = QPushButton("▶ 开始转换")
        self.btn_convert.setStyleSheet(
            "QPushButton { background-color: #2c7fb8; color: white; "
            "font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #1e6398; }"
            "QPushButton:disabled { background-color: #888; }"
        )
        self.btn_cancel = QPushButton("■ 取消")
        self.btn_cancel.setEnabled(False)
        for b in (self.btn_add, self.btn_remove, self.btn_clear,
                  self.btn_convert, self.btn_cancel):
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        root.addLayout(btn_bar)

        # 状态栏
        self.statusBar().showMessage("就绪")

        # 信号
        self.btn_add.clicked.connect(self.on_add_files_clicked)
        self.btn_remove.clicked.connect(self.file_table.remove_selected)
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        self.btn_convert.clicked.connect(self.on_convert_clicked)
        self.btn_cancel.clicked.connect(self.on_cancel_clicked)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)

    def _build_settings_group(self):
        group = QGroupBox("转换设置")
        v = QVBoxLayout(group)
        v.setSpacing(6)

        # 预设（分组 + 分隔符）
        v.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        prev_group = None
        for p in PRESETS:
            # 切换分组时插入分隔符
            if p["group"] != prev_group:
                if prev_group is not None:
                    self.preset_combo.insertSeparator(self.preset_combo.count())
                prev_group = p["group"]
            self.preset_combo.addItem(p["name"])
            idx = self.preset_combo.count() - 1
            self.preset_combo.setItemData(idx, p, Qt.UserRole)        # 存完整 preset
            self.preset_combo.setItemData(idx, p.get("desc", ""), Qt.ToolTipRole)
            # 不可用项（RMVB）置灰
            if p.get("disabled"):
                item = self.preset_combo.model().item(idx)
                if item:
                    item.setEnabled(False)
                    item.setForeground(QColor("#999"))
        v.addWidget(self.preset_combo)

        # 输出目录
        v.addWidget(QLabel("输出目录:"))
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("默认与源文件同目录")
        self.btn_browse = QPushButton("浏览…")
        self.btn_browse.clicked.connect(self.on_browse_output)
        out_row.addWidget(self.output_edit)
        out_row.addWidget(self.btn_browse)
        v.addLayout(out_row)

        # 分辨率
        v.addWidget(QLabel("分辨率:"))
        res_row = QHBoxLayout()
        self.spin_w = QSpinBox()
        self.spin_w.setRange(160, 1920)
        self.spin_w.setSingleStep(16)
        self.spin_h = QSpinBox()
        self.spin_h.setRange(120, 1080)
        self.spin_h.setSingleStep(16)
        res_row.addWidget(self.spin_w)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self.spin_h)
        res_row.addStretch()
        v.addLayout(res_row)

        # 视频码率
        v.addWidget(QLabel("视频码率 (kbps):"))
        self.spin_vbit = QSpinBox()
        self.spin_vbit.setRange(100, 8000)
        self.spin_vbit.setSingleStep(100)
        v.addWidget(self.spin_vbit)

        # 音频码率
        v.addWidget(QLabel("音频码率 (kbps):"))
        self.spin_abit = QSpinBox()
        self.spin_abit.setRange(16, 320)
        self.spin_abit.setSingleStep(16)
        v.addWidget(self.spin_abit)

        # 帧率（下拉，可选"保持原帧数"）
        v.addWidget(QLabel("帧率:"))
        self.fps_combo = QComboBox()
        for label, val in FPS_OPTIONS:
            self.fps_combo.addItem(label)
            self.fps_combo.setItemData(self.fps_combo.count() - 1, val, Qt.UserRole)
        v.addWidget(self.fps_combo)

        # 4:3 适配加黑边（默认勾选）
        self.chk_letterbox = QCheckBox("4:3 适配 (加黑边 letterbox)")
        self.chk_letterbox.setChecked(True)
        self.chk_letterbox.setToolTip(
            "针对 4:3 显像管电视：保持源宽高比缩放到目标矩形内，"
            "周围补黑边到目标分辨率。默认开启，避免画面被压扁。"
        )
        v.addWidget(self.chk_letterbox)

        # 字幕烧录
        self.chk_subtitle = QCheckBox("自动烧录同名字幕 (.srt/.ass)")
        self.chk_subtitle.setChecked(True)
        self.chk_subtitle.setToolTip(
            "把字幕硬编码到视频中，无需播放器支持即可显示。"
            "ASF 容器在 Win98 上软字幕支持不稳定，建议烧录。"
        )
        v.addWidget(self.chk_subtitle)

        # 应用预设初始值
        QTimer.singleShot(0, lambda: self.on_preset_changed(self.preset_combo.currentIndex()))
        return group

    # ---------- 槽函数 ----------
    def on_preset_changed(self, idx):
        if idx < 0:
            return
        p = self.preset_combo.itemData(idx, Qt.UserRole)
        if not p:
            return  # 分隔符项没有 UserRole 数据
        # 应用分辨率/码率
        self.spin_w.setValue(p["width"])
        self.spin_h.setValue(p["height"])
        self.spin_vbit.setValue(p["video_bitrate"])
        self.spin_abit.setValue(p["audio_bitrate"])
        # 帧率下拉：选最接近的项
        fps_val = p.get("fps")
        self._select_fps(fps_val)
        # 规格锁定帧率时禁用下拉
        self.fps_combo.setEnabled(not p.get("force_fps", False))

    def _select_fps(self, fps_val):
        """根据 FPS_OPTIONS 选中最匹配项；None 选'保持原帧数'"""
        for i, (_, val) in enumerate(FPS_OPTIONS):
            if val is None and fps_val is None:
                self.fps_combo.setCurrentIndex(i); return
            if val is not None and fps_val is not None and abs(val - fps_val) < 0.01:
                self.fps_combo.setCurrentIndex(i); return
        self.fps_combo.setCurrentIndex(0)

    def on_files_dropped(self, files):
        added = self.file_table.add_files(files)
        self.log(f"已添加 {added} 个文件")
        self.statusBar().showMessage(f"文件列表: {self.file_table.rowCount()} 项")

    def on_add_files_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.mpg *.mpeg "
            "*.m4v *.webm *.ts *.m2ts *.vob *.3gp *.rm *.rmvb);;所有文件 (*.*)"
        )
        if files:
            self.on_files_dropped(files)

    def on_clear_clicked(self):
        self.file_table.clear_all()
        self.statusBar().showMessage("列表已清空")

    def on_browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_edit.setText(d)

    def on_convert_clicked(self):
        files = self.file_table.get_all_files()
        if not files:
            QMessageBox.information(self, "提示", "请先添加视频文件")
            return
        if not self.ffmpeg or not os.path.exists(self.ffmpeg):
            self._check_ffmpeg()
            if not self.ffmpeg or not os.path.exists(self.ffmpeg):
                QMessageBox.critical(
                    self, "缺少 ffmpeg",
                    "未找到 ffmpeg.exe。\n请下载 FFmpeg（gyan.dev 构建），"
                    "把 ffmpeg.exe 和 ffprobe.exe 解压到本程序目录下的 "
                    f"'ffmpeg' 子文件夹:\n  {self.script_dir / 'ffmpeg'}"
                )
                return

        preset = self.preset_combo.itemData(
            self.preset_combo.currentIndex(), Qt.UserRole
        )
        if not preset:
            QMessageBox.warning(self, "提示", "请选择一个有效的转换预设")
            return
        if preset.get("disabled"):
            QMessageBox.warning(self, "预设不可用", preset.get("desc", "该预设不可用"))
            return

        # 帧率：preset 锁定则用 preset 值，否则用下拉选中的值（可能 None=保持原帧数）
        if preset.get("force_fps"):
            fps_val = preset.get("fps")
        else:
            fps_val = self.fps_combo.itemData(self.fps_combo.currentIndex(), Qt.UserRole)

        # 以 preset 为基础，用 UI 值覆盖可调字段
        settings = dict(preset)
        settings["width"] = self.spin_w.value()
        settings["height"] = self.spin_h.value()
        settings["video_bitrate"] = self.spin_vbit.value()
        settings["audio_bitrate"] = self.spin_abit.value()
        settings["fps"] = fps_val

        out_dir = self.output_edit.text().strip() or None
        burn_subs = self.chk_subtitle.isChecked()
        letterbox = self.chk_letterbox.isChecked()

        self.worker = ConversionWorker(
            files, settings, self.ffmpeg, self.ffprobe,
            out_dir, burn_subs, letterbox
        )
        self.worker.file_started.connect(self.on_file_started)
        self.worker.progress.connect(self.on_progress)
        self.worker.file_finished.connect(self.on_file_finished)
        self.worker.log_line.connect(self.log)
        self.worker.all_done.connect(self.on_all_done)
        self.worker.ffmpeg_missing.connect(self.on_ffmpeg_missing)

        # UI 切换到"运行中"状态
        self._set_running(True)
        self.log(">> 开始批量转换 <<")
        self.worker.start()

    def on_cancel_clicked(self):
        if self.worker and self.worker.isRunning():
            self.log(">> 用户请求取消 <<")
            self.worker.cancel()

    def on_file_started(self, name):
        row = self.file_table.find_row_by_name(name)
        if row >= 0:
            self.file_table.set_status(row, "转换中…", "#2c7fb8")
        self.statusBar().showMessage(f"正在转换: {name}")

    def on_progress(self, name, pct):
        row = self.file_table.find_row_by_name(name)
        if row >= 0:
            self.file_table.set_progress(row, pct)

    def on_file_finished(self, name, success, info):
        row = self.file_table.find_row_by_name(name)
        if row < 0:
            return
        if success:
            self.file_table.set_status(row, "完成 ✓", "#2e8b57")
            self.file_table.set_progress(row, 100)
            self.file_table.set_output(row, info)
        else:
            self.file_table.set_status(row, f"失败: {info}", "#c0392b")

    def on_all_done(self):
        self._set_running(False)
        self.statusBar().showMessage("全部完成")
        self.log(">> 全部任务完成 <<")
        # 统计
        ok = sum(1 for r in range(self.file_table.rowCount())
                 if self.file_table.item(r, self.file_table.COL_STATUS) and
                 self.file_table.item(r, self.file_table.COL_STATUS).text().startswith("完成"))
        total = self.file_table.rowCount()
        QMessageBox.information(self, "转换结束", f"完成 {ok}/{total}")

    def on_ffmpeg_missing(self):
        QMessageBox.critical(
            self, "缺少 ffmpeg",
            f"未找到 ffmpeg.exe。请放到:\n  {self.script_dir / 'ffmpeg' / 'ffmpeg.exe'}"
        )

    # ---------- 辅助 ----------
    def _check_ffmpeg(self):
        if not self.ffmpeg or not os.path.exists(self.ffmpeg):
            self.log("[警告] 未找到 ffmpeg.exe，请下载后放到 ./ffmpeg/ 子目录")
        else:
            self.log(f"[OK] ffmpeg: {self.ffmpeg}")
        if not self.ffprobe or not os.path.exists(self.ffprobe):
            self.log("[警告] 未找到 ffprobe.exe，进度百分比将不可用")
        else:
            self.log(f"[OK] ffprobe: {self.ffprobe}")

    def _set_running(self, running):
        for w in (self.btn_convert, self.btn_add, self.btn_clear,
                  self.btn_remove, self.drop_area,
                  self.preset_combo, self.spin_w, self.spin_h,
                  self.spin_vbit, self.spin_abit, self.fps_combo,
                  self.chk_letterbox, self.btn_browse, self.output_edit,
                  self.chk_subtitle):
            w.setEnabled(not running)
        self.btn_cancel.setEnabled(running)

    def log(self, msg):
        self.log_view.append(msg)
        # 滚到底
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Win98 ASF Converter")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
