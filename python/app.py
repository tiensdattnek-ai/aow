#!/usr/bin/env python3
"""AstraDroid PyInstaller entry point.

A dependency-free Tk GUI which calls the local engine in-process.  This lets
Windows users package a usable .exe without installing the MSVC C++ toolchain.
"""
from __future__ import annotations

import ctypes
import io
import json
import os
import queue
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from ctypes import wintypes
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Button, Frame, Label, StringVar, Tk, filedialog, font as tkfont, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable, Optional

import engine

APP_NAME = "AstraDroid"
BG = "#090D19"
SIDEBAR = "#10172A"
PANEL = "#182238"
PANEL_2 = "#202C45"
CANVAS = "#050914"
TEXT = "#F2F6FF"
MUTED = "#9DADC9"
ACCENT = "#627CFF"
PURPLE = "#9B5BFF"
GOOD = "#35CF97"
WARN = "#FFBC52"
DANGER = "#F55A6F"

IS_WINDOWS = os.name == "nt"


class EmulatorEmbedder:
    """Best-effort Windows child-window embedding for Android Emulator."""

    GWL_STYLE = -16
    WS_CHILD = 0x40000000
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000

    def __init__(self, host: Frame, report: Callable[[str], None]) -> None:
        self.host = host
        self.report = report
        self.pid = 0
        self.window: Optional[int] = None
        self.attempts = 0
        self._callback: Any = None
        if IS_WINDOWS:
            self.user32 = ctypes.windll.user32
            self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self.user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
            self.user32.SetParent.restype = wintypes.HWND
            pointer_type = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
            self.user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.GetWindowLongPtrW.restype = pointer_type
            self.user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, pointer_type]
            self.user32.SetWindowLongPtrW.restype = pointer_type

    def begin(self, pid: int) -> None:
        self.pid, self.window, self.attempts = pid, None, 0

    def _find_candidate(self) -> Optional[int]:
        if not IS_WINDOWS or not self.pid:
            return None
        found: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_window(hwnd: int, _: int) -> bool:
            if not self.user32.IsWindowVisible(hwnd) or self.user32.GetParent(hwnd):
                return True
            pid = wintypes.DWORD(0)
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.pid:
                found.append(int(hwnd))
                return False
            return True

        self._callback = enum_window
        self.user32.EnumWindows(enum_window, 0)
        return found[0] if found else None

    def try_embed(self) -> bool:
        if not IS_WINDOWS or not self.pid:
            return False
        self.attempts += 1
        candidate = self._find_candidate()
        if not candidate:
            return False
        try:
            style = self.user32.GetWindowLongPtrW(candidate, self.GWL_STYLE)
            self.user32.SetWindowLongPtrW(candidate, self.GWL_STYLE, (style & ~self.WS_POPUP) | self.WS_CHILD | self.WS_VISIBLE)
            self.user32.SetParent(candidate, self.host.winfo_id())
            self.window = candidate
            self.resize()
            return True
        except OSError:
            return False

    def resize(self) -> None:
        if not IS_WINDOWS or not self.window:
            return
        try:
            self.host.update_idletasks()
            self.user32.MoveWindow(self.window, 0, 0, self.host.winfo_width(), self.host.winfo_height(), True)
        except OSError:
            self.window = None

    def detach(self) -> None:
        if IS_WINDOWS and self.window:
            try:
                self.user32.SetParent(self.window, 0)
            except OSError:
                pass
        self.window, self.pid = None, 0


class AstraDroid(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AstraDroid · Windows APK Workspace")
        self.geometry("1420x880")
        self.minsize(1120, 760)
        self.configure(bg=BG)
        self.option_add("*Font", "Segoe UI 10")
        self._dark_title_bar()

        self.busy = False
        self.result_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.buttons: list[Button] = []
        self.apk_path = ""
        self.package = ""
        self.embedder: Optional[EmulatorEmbedder] = None

        self.vt_var = StringVar(value="Đang kiểm tra VT-x / AMD-V…")
        self.sdk_var = StringVar(value="Đang dò Android SDK…")
        self.device_var = StringVar(value="Thiết bị Android chưa online")
        self.apk_name_var = StringVar(value="Chọn APK hoặc dùng Ctrl + O")
        self.apk_package_var = StringVar(value="Chưa đọc package name")
        self.apk_meta_var = StringVar(value="SHA-256 và signature sẽ hiển thị tại đây")
        self.canvas_var = StringVar(value="Chưa khởi động Android Emulator")

        self._build_ui()
        self.bind_all("<Control-o>", lambda _event: self.pick_apk())
        self.bind_all("<Control-Return>", lambda _event: self.install_and_launch())
        self.bind_all("<Control-l>", lambda _event: self.invoke("logcat", ["logcat", "--lines", "350"]))
        self.bind("<Configure>", lambda _event: self.after_idle(self._resize_embedded))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll_results)
        self.invoke("status", ["status"])

    def _dark_title_bar(self) -> None:
        if not IS_WINDOWS:
            return
        try:
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self.winfo_id(), 20, ctypes.byref(value), ctypes.sizeof(value))
            corners = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self.winfo_id(), 33, ctypes.byref(corners), ctypes.sizeof(corners))
        except OSError:
            pass

    def _font(self, size: int, bold: bool = False, mono: bool = False) -> tkfont.Font:
        # A Font object keeps family names containing spaces (Segoe UI,
        # Cascadia Mono) as a single name. A raw tuple can be split by Tcl on
        # some Windows/Tk builds, producing: expected integer but got 'UI'.
        return tkfont.Font(family="Cascadia Mono" if mono else "Segoe UI", size=size, weight="bold" if bold else "normal")

    def _label(self, parent: Frame, text: str | StringVar, size: int = 10, color: str = TEXT, bold: bool = False, **kwargs: Any) -> Label:
        # Tk's ``text`` option does not observe StringVar; use textvariable for
        # live status cards and inspector fields.
        content = {"textvariable": text} if isinstance(text, StringVar) else {"text": text}
        return Label(parent, bg=parent.cget("bg"), fg=color, font=self._font(size, bold), **content, **kwargs)

    def _button(self, parent: Frame, text: str, command: Callable[[], None], color: str = PANEL_2, foreground: str = TEXT) -> Button:
        button = Button(parent, text=text, command=command, bg=color, fg=foreground, activebackground=color,
                        activeforeground=foreground, disabledforeground="#73809A", relief="flat", bd=0,
                        cursor="hand2", padx=12, pady=9, font=self._font(9, True), anchor="w")
        button.pack(fill=X, padx=20, pady=4)
        self.buttons.append(button)
        return button

    def _status_card(self, parent: Frame, title: str, variable: StringVar, dot_color: str) -> Frame:
        card = Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground="#263653", padx=16, pady=12)
        card.pack(side=LEFT, fill=X, expand=True, padx=6)
        title_row = Frame(card, bg=PANEL); title_row.pack(fill=X)
        Label(title_row, text="●", bg=PANEL, fg=dot_color, font=self._font(10, True)).pack(side=LEFT)
        self._label(title_row, title, 8, MUTED, True).pack(side=LEFT, padx=(7, 0))
        self._label(card, variable, 10, TEXT, True, justify=LEFT, wraplength=245).pack(anchor="w", pady=(7, 0))
        return card

    def _build_ui(self) -> None:
        sidebar = Frame(self, bg=SIDEBAR, width=256)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)
        brand = Frame(sidebar, bg=SIDEBAR); brand.pack(fill=X, padx=20, pady=(24, 30))
        badge = Label(brand, text="A", bg=ACCENT, fg="white", font=self._font(22, True), width=2, pady=2)
        badge.pack(side=LEFT)
        brand_text = Frame(brand, bg=SIDEBAR); brand_text.pack(side=LEFT, padx=11)
        self._label(brand_text, "AstraDroid", 16, TEXT, True).pack(anchor="w")
        self._label(brand_text, "ANDROID ON WINDOWS", 7, MUTED, True).pack(anchor="w", pady=(2, 0))
        self._label(sidebar, "WORKSPACE", 8, MUTED, True).pack(anchor="w", padx=20, pady=(0, 7))
        self._button(sidebar, "CHỌN APK   Ctrl+O", self.pick_apk, ACCENT)
        self._button(sidebar, "KIỂM TRA HỆ THỐNG", lambda: self.invoke("status", ["status"]))
        self._button(sidebar, "TẠO ANDROID ẢO", self.create_avd, PURPLE)
        dual = Frame(sidebar, bg=SIDEBAR); dual.pack(fill=X, padx=20, pady=4)
        start = Button(dual, text="MỞ", command=lambda: self.invoke("start", ["start", "--avd", engine.DEFAULT_AVD]), bg=GOOD, fg="#0B201A", relief="flat", bd=0, cursor="hand2", pady=9, font=self._font(9, True))
        start.pack(side=LEFT, fill=X, expand=True, padx=(0, 4)); self.buttons.append(start)
        stop = Button(dual, text="DỪNG", command=lambda: self.invoke("stop", ["stop"]), bg=DANGER, fg="white", relief="flat", bd=0, cursor="hand2", pady=9, font=self._font(9, True))
        stop.pack(side=LEFT, fill=X, expand=True, padx=(4, 0)); self.buttons.append(stop)
        self._button(sidebar, "CÀI & CHẠY APK   Ctrl+Enter", self.install_and_launch, ACCENT)
        self._button(sidebar, "THÔNG TIN THIẾT BỊ", lambda: self.invoke("device", ["device-info"]))
        self._button(sidebar, "XEM LOGCAT GẦN NHẤT", lambda: self.invoke("logcat", ["logcat", "--lines", "350"]))
        self._button(sidebar, "GỠ APK ĐANG CHỌN", self.uninstall, DANGER)
        self._button(sidebar, "CHUẨN BỊ WINDOWS", self.prepare_windows, WARN, "#362810")
        self._button(sidebar, "XÓA NHẬT KÝ", self.clear_log)
        self._label(sidebar, "LOCAL · PRIVATE · NO TELEMETRY", 7, MUTED, True, justify=LEFT, wraplength=200).pack(side="bottom", anchor="w", padx=20, pady=22)

        main = Frame(self, bg=BG)
        main.pack(side=LEFT, fill=BOTH, expand=True)
        header = Frame(main, bg=BG); header.pack(fill=X, padx=28, pady=(22, 8))
        title = Frame(header, bg=BG); title.pack(side=LEFT, fill=X, expand=True)
        self._label(title, "APK Studio", 25, TEXT, True).pack(anchor="w")
        self._label(title, "Kiểm tra, chạy và quản lý app Android hoàn toàn cục bộ.", 10, MUTED).pack(anchor="w", pady=(2, 0))
        privacy = Label(header, text="●  PRIVATE LOCAL", bg="#1C3555", fg=GOOD, font=self._font(9, True), padx=14, pady=8)
        privacy.pack(side=RIGHT, pady=8)

        status = Frame(main, bg=BG); status.pack(fill=X, padx=22, pady=(8, 13))
        self._status_card(status, "VIRTUALIZATION", self.vt_var, GOOD)
        self._status_card(status, "ANDROID SDK", self.sdk_var, ACCENT)
        self._status_card(status, "DEVICE", self.device_var, GOOD)

        workspace = Frame(main, bg=BG); workspace.pack(fill=BOTH, expand=True, padx=28, pady=(0, 12))
        workspace.grid_columnconfigure(0, weight=3, minsize=310)
        workspace.grid_columnconfigure(1, weight=5, minsize=420)
        workspace.grid_rowconfigure(0, weight=1)

        inspector = Frame(workspace, bg=PANEL, highlightthickness=1, highlightbackground="#263653", padx=19, pady=18)
        inspector.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._label(inspector, "APK INSPECTOR", 9, MUTED, True).pack(anchor="w")
        self._label(inspector, self.apk_name_var, 12, TEXT, True, justify=LEFT, wraplength=300).pack(anchor="w", pady=(24, 8))
        self._label(inspector, self.apk_package_var, 10, ACCENT, justify=LEFT, wraplength=300).pack(anchor="w", pady=4)
        self._label(inspector, self.apk_meta_var, 9, MUTED, justify=LEFT, wraplength=300).pack(anchor="w", pady=(11, 0))
        self._label(inspector, "Mẹo: chọn APK đáng tin cậy. SHA-256 và signing certificate chỉ là tín hiệu xác minh, không thay thế antivirus.", 9, MUTED, justify=LEFT, wraplength=300).pack(side="bottom", anchor="w")

        emulator_panel = Frame(workspace, bg=PANEL, highlightthickness=1, highlightbackground="#263653", padx=15, pady=14)
        emulator_panel.grid(row=0, column=1, sticky="nsew")
        panel_header = Frame(emulator_panel, bg=PANEL); panel_header.pack(fill=X, pady=(0, 10))
        self._label(panel_header, "ANDROID CANVAS", 9, MUTED, True).pack(side=LEFT)
        self._label(panel_header, self.canvas_var, 9, TEXT).pack(side=RIGHT)
        self.emulator_host = Frame(emulator_panel, bg=CANVAS, highlightthickness=1, highlightbackground="#31466E")
        self.emulator_host.pack(fill=BOTH, expand=True)
        self._label(self.emulator_host, "ANDROID EMULATOR", 16, "#4D6088", True).place(relx=0.5, rely=0.46, anchor="center")
        self._label(self.emulator_host, "Khởi động AVD để chạy ứng dụng trong canvas này", 9, "#4D6088").place(relx=0.5, rely=0.53, anchor="center")
        self.embedder = EmulatorEmbedder(self.emulator_host, self.log)

        logs = Frame(main, bg=PANEL, highlightthickness=1, highlightbackground="#263653")
        logs.pack(fill=X, padx=28, pady=(0, 24))
        log_head = Frame(logs, bg=PANEL); log_head.pack(fill=X, padx=14, pady=(10, 4))
        self._label(log_head, "ACTIVITY LOG", 8, MUTED, True).pack(side=LEFT)
        self._label(log_head, "Ctrl+L logcat  •  Ctrl+Enter install & run", 8, MUTED).pack(side=RIGHT)
        self.log_box = ScrolledText(logs, height=7, bg=CANVAS, fg="#CCD8ED", insertbackground=TEXT, relief="flat", bd=0, wrap="word", font=self._font(9, mono=True), padx=12, pady=10)
        self.log_box.pack(fill=X, padx=10, pady=(0, 10))
        self.log_box.configure(state="disabled")
        self.log("AstraDroid PyInstaller GUI đang khởi tạo…")

    def log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert(END, f"[{timestamp}] {text.rstrip()}\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 420:
            self.log_box.delete("1.0", "120.0")
        self.log_box.see(END)
        self.log_box.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", END)
        self.log_box.configure(state="disabled")
        self.log("Nhật ký đã được xóa.")

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in self.buttons:
            button.configure(state="disabled" if busy else "normal")

    def invoke(self, action: str, argv: list[str]) -> None:
        if self.busy:
            self.log("Một tác vụ đang chạy; vui lòng chờ hoàn tất.")
            return
        self.set_busy(True)
        self.log("→ " + " ".join(argv))

        def worker() -> None:
            buffer = io.StringIO()
            response: dict[str, Any] = {"ok": False, "message": "Backend không trả về phản hồi."}
            try:
                args = engine.build_parser().parse_args(argv)
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    args.func(args)
            except SystemExit:
                pass
            except Exception as exc:  # Engine functions are normally CLI-safe; GUI keeps errors visible too.
                response = {"ok": False, "message": f"Lỗi nội bộ: {exc.__class__.__name__}: {exc}"}
            else:
                response = {"ok": False, "message": "Backend không trả về phản hồi."}
            raw_lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
            for line in reversed(raw_lines):
                try:
                    response = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            self.result_queue.put((action, response))

        threading.Thread(target=worker, name=f"astradroid-{action}", daemon=True).start()

    def poll_results(self) -> None:
        try:
            while True:
                action, response = self.result_queue.get_nowait()
                self.finish_action(action, response)
        except queue.Empty:
            pass
        self.after(100, self.poll_results)

    def finish_action(self, action: str, response: dict[str, Any]) -> None:
        self.set_busy(False)
        ok = bool(response.get("ok"))
        message = str(response.get("message") or ("Hoàn tất." if ok else "Tác vụ không thành công."))
        self.log(("✓ " if ok else "✕ ") + message)
        output = str(response.get("output") or "").strip()
        if output:
            self.log(output)

        if action == "status":
            vt = response.get("virtualization") or {}
            self.vt_var.set("VT-x / AMD-V sẵn sàng" if vt.get("firmware_enabled") else "VT-x / AMD-V cần bật trong UEFI")
            self.sdk_var.set("Emulator sẵn sàng" if response.get("sdk_ready") else "Chưa tìm thấy Android Emulator")
        elif action == "inspect" and ok:
            self.package = str(response.get("package") or "")
            label = str(response.get("label") or "")
            name = str(response.get("name") or Path(self.apk_path).name)
            self.apk_name_var.set(f"{label}  ·  {name}" if label else name)
            self.apk_package_var.set(self.package or "Không đọc được package — kiểm tra Android Build-Tools")
            version = str(response.get("version_name") or "")
            signing = str(response.get("signing") or "Chưa xác minh signature")
            self.apk_meta_var.set((f"v{version}  •  " if version else "") + signing)
            digest = str(response.get("sha256") or "")
            if digest:
                self.log("SHA-256: " + digest)
        elif action == "start" and ok:
            pid = int(response.get("pid") or 0)
            self.canvas_var.set("Đang boot Android Emulator…")
            if self.embedder and pid:
                self.embedder.begin(pid)
                self.after(1000, self.try_embed)
        elif action == "install" and ok:
            if self.package:
                self.log("APK đã cài. Đang mở launcher activity…")
                self.invoke("launch", ["launch", "--package", self.package])
            else:
                self.log("Đã cài APK nhưng chưa có package name để tự mở.")
        elif action == "launch" and ok:
            self.canvas_var.set("Ứng dụng Android đang chạy")
        elif action == "device" and ok:
            model = str(response.get("model") or "Android Emulator")
            android = str(response.get("android") or "?")
            api = str(response.get("api") or "?")
            battery = str(response.get("battery") or "?")
            self.device_var.set(f"{model} · Android {android} · API {api} · {battery}")
        elif action == "stop":
            if self.embedder:
                self.embedder.detach()
            self.canvas_var.set("Máy ảo đã nhận lệnh dừng")
            self.device_var.set("Thiết bị Android chưa online")
        elif action == "uninstall" and ok:
            self.log("Ứng dụng đã được gỡ khỏi Android Emulator.")

    def try_embed(self) -> None:
        if not self.embedder or not self.embedder.pid:
            return
        if self.embedder.try_embed():
            self.canvas_var.set("Emulator đã được nhúng vào AstraDroid")
            self.log("✓ Android Emulator đang hiển thị trong Android Canvas.")
            return
        if self.embedder.attempts >= 55:
            self.canvas_var.set("Emulator chạy ở cửa sổ riêng (Qt/driver không cho nhúng)")
            self.log("! Không thể nhúng cửa sổ sau 55 giây; Emulator vẫn dùng bình thường ở cửa sổ riêng.")
            return
        self.after(1000, self.try_embed)

    def _resize_embedded(self) -> None:
        if self.embedder:
            self.embedder.resize()

    def pick_apk(self) -> None:
        path = filedialog.askopenfilename(title="Chọn APK để kiểm tra và cài", filetypes=[("Android package", "*.apk"), ("All files", "*.*")])
        if path:
            self.select_apk(path)

    def select_apk(self, path: str) -> None:
        if Path(path).suffix.lower() != ".apk":
            messagebox.showinfo(APP_NAME, "AstraDroid hiện hỗ trợ APK trực tiếp (.apk). Hãy giải nén APKS/XAPK trước.")
            return
        self.apk_path, self.package = path, ""
        self.apk_name_var.set(Path(path).name)
        self.apk_package_var.set("Đang đọc package, SHA-256 và signing certificate…")
        self.apk_meta_var.set("Đang kiểm tra cục bộ")
        self.invoke("inspect", ["inspect-apk", "--apk", path])

    def create_avd(self) -> None:
        if messagebox.askokcancel("Tạo Android ảo", "Lần đầu sẽ tải Android Emulator, Build-Tools và system image từ Google. Dung lượng có thể lớn; bạn đồng ý Android SDK licenses?"):
            self.invoke("create", ["create-avd", "--avd", engine.DEFAULT_AVD, "--download"])

    def install_and_launch(self) -> None:
        if not self.apk_path:
            messagebox.showinfo(APP_NAME, "Hãy chọn một APK trước.")
            return
        argv = ["install", "--apk", self.apk_path]
        if self.package:
            argv.extend(["--package", self.package])
        self.invoke("install", argv)

    def uninstall(self) -> None:
        if not self.package:
            messagebox.showinfo(APP_NAME, "Hãy kiểm tra APK để lấy package name trước khi gỡ.")
            return
        if messagebox.askokcancel("Xác nhận gỡ APK", f"Gỡ package '{self.package}' khỏi Android Emulator?\n\nAPK trên Windows sẽ không bị xóa.", icon="warning"):
            self.invoke("uninstall", ["uninstall", "--package", self.package])

    def prepare_windows(self) -> None:
        if not messagebox.askokcancel("Chuẩn bị Windows", "Lệnh này yêu cầu Administrator, bật Windows Hypervisor Platform / Virtual Machine Platform và có thể yêu cầu restart. Nó không thể bật VT-x/AMD-V trong BIOS. Tiếp tục?", icon="warning"):
            return
        script = engine.APP_ROOT / "scripts" / "Enable-Windows-Acceleration.ps1"
        if not script.exists():
            messagebox.showerror(APP_NAME, "Không tìm thấy PowerShell helper trong bundle.")
            return
        params = f'-NoProfile -ExecutionPolicy Bypass -File "{script}" -Apply'
        if IS_WINDOWS:
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, str(engine.APP_ROOT), 1)
            if result <= 32:
                messagebox.showerror(APP_NAME, "Không thể mở PowerShell Administrator. Hãy thử Run as administrator.")
            else:
                self.log("Đã mở Windows acceleration helper bằng quyền Administrator.")

    def close(self) -> None:
        if self.busy and not messagebox.askyesno(APP_NAME, "Một tác vụ đang chạy. Đóng AstraDroid? Android Emulator đang chạy sẽ không tự dừng."):
            return
        self.destroy()


def main() -> None:
    if not IS_WINDOWS:
        raise SystemExit("AstraDroid GUI chỉ chạy trên Windows.")
    AstraDroid().mainloop()


if __name__ == "__main__":
    main()
