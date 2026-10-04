<div align="center">

# ✦ AstraDroid

### Native Windows APK Workspace

**Kiểm tra · cài đặt · chạy ứng dụng Android APK trong một desktop app Windows hiện đại**

`C++ Win32 GUI` &nbsp;•&nbsp; `Python control plane` &nbsp;•&nbsp; `Android SDK Emulator` &nbsp;•&nbsp; `VT-x / AMD-V`

</div>

---

## AstraDroid là gì?

**AstraDroid** là ứng dụng desktop native dành cho Windows 10/11 x64. Nó giúp bạn chọn APK, kiểm tra thông tin/chữ ký, tạo Android Virtual Device, khởi động Android Emulator, cài APK và mở ứng dụng từ cùng một giao diện.

> APK cần Android runtime nên không thể biến thành `.exe` native một cách đáng tin cậy. AstraDroid dùng **Android Emulator chính thức của Android SDK**, sau đó tự động thử nhúng cửa sổ Emulator vào vùng **Android Canvas** trong app.

- Khi Qt/driver cho phép nhúng: ứng dụng Android chạy ngay trong cửa sổ AstraDroid.
- Khi môi trường chặn re-parenting: Emulator vẫn chạy an toàn ở cửa sổ riêng, còn AstraDroid vẫn quản lý toàn bộ flow cài/chạy/log.

## Điểm nổi bật

| | Tính năng |
|---|---|
| 🎨 | **Native dark GUI** — giao diện Win32 hiện đại với Fluent/Mica khi Windows hỗ trợ, gradient, status cards, corner bo tròn, phím tắt và activity log. |
| ⚡ | **Hardware-aware** — kiểm tra VT-x/AMD-V, SLAT, Hyper-V/Windows virtualization features trước khi khởi động Emulator. |
| 📦 | **APK Inspector** — đọc package, label, version, min SDK; tính SHA-256 cục bộ; xác minh signing certificate khi Android Build-Tools sẵn sàng. |
| 📱 | **Android Canvas** — khởi động AVD Pixel, tăng tốc GPU host và thử nhúng Emulator theo PID thay vì nhận diện title không an toàn. |
| 🚀 | **Install & Launch** — `adb install -r -g`, resolve launcher Activity, tự mở app mà không đoán Activity class. |
| 🛠️ | **Device tools** — xem model/Android/API/pin, logcat có giới hạn, gỡ APK với xác nhận, dừng AVD. |
| 🔒 | **Local-first** — không upload APK, không analytics, không root, không bypass DRM / Play Integrity / cơ chế bảo vệ Android. |

## Giao diện & thao tác

```text
┌────────────────────────────────── AstraDroid ──────────────────────────────────┐
│  ASTRA DROID                     APK Studio              ● PRIVATE LOCAL       │
│  [ Chọn APK ]                    [ VT ] [ SDK ] [ Device ]                     │
│  [ Kiểm tra hệ thống ]                                                      │
│  [ Tạo Android ảo ]          APK Inspector       Android Canvas                │
│  [ Mở ] [ Dừng ]              package · hash      ┌───────────────────────┐    │
│  [ Cài & chạy APK ]                               │   Android Emulator    │    │
│  [ Thông tin thiết bị ]                            │    (embedded when     │    │
│  [ Xem logcat gần nhất ]                           │       supported)      │    │
│  [ Gỡ APK đang chọn ]                              └───────────────────────┘    │
│  [ Chuẩn bị Windows ]      Activity log                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Shortcut | Hành động |
|---|---|
| `Ctrl + O` | Chọn APK |
| `Ctrl + Enter` | Cài và chạy APK đang chọn |
| `Ctrl + L` | Lấy logcat gần nhất |
| Kéo thả `.apk` | Chọn và kiểm tra APK ngay trong cửa sổ |

## Điều kiện bắt buộc

- **Windows 10/11 64-bit**.
- CPU hỗ trợ **Intel VT-x** hoặc **AMD SVM**, đã bật trong UEFI/BIOS.
- Python 3 x64 với `py.exe`.
- Visual Studio 2022 Build Tools — C++ workload.
- Android Studio / Android SDK với: Emulator, Platform-Tools, Command-line Tools, Build-Tools và Google APIs x86_64 system image.

Khuyến nghị: CPU 4 core trở lên, **16 GB RAM**, 20–35 GB ổ đĩa trống, GPU driver mới.

## Bắt đầu nhanh

```bat
:: 1. Cài prerequisite hướng dẫn qua winget (tùy chọn)
SETUP_WINDOWS.bat

:: 2. Build native Windows app
BUILD.bat

:: 3. Mở GUI
RUN.bat
```

Nếu build thành công, file ứng dụng được tạo tại:

```text
bin\AstraDroid.exe
```

Trong GUI: **KIỂM TRA HỆ THỐNG → TẠO ANDROID ẢO → MỞ → CHỌN APK → CÀI & CHẠY APK**.

> **Lưu ý về VT:** Không có script nào có thể tự bật VT-x/AMD-V trong firmware. Bạn cần bật Intel Virtualization Technology / SVM Mode trong UEFI/BIOS, sau đó restart. Nút **CHUẨN BỊ WINDOWS** chỉ bật Windows Hypervisor Platform / Virtual Machine Platform bằng quyền Administrator.

## Kiến trúc

```text
┌───────────────────┐        JSON over stdout        ┌──────────────────────────┐
│ C++17 Win32 GUI   │ ──────────────────────────────▶ │ Python standard library  │
│ - Fluent UI       │                                  │ - SDK / AVD lifecycle    │
│ - Drag & drop     │ ◀────────────────────────────── │ - adb / aapt / apksigner │
│ - Emulator embed  │                                  │ - VT / Windows probes    │
└─────────┬─────────┘                                  └────────────┬─────────────┘
          │ native child window                                      │
          ▼                                                          ▼
┌───────────────────┐                                  ┌──────────────────────────┐
│ Android Canvas    │                                  │ Android SDK Emulator     │
│ embedded fallback │                                  │ + ADB local device       │
└───────────────────┘                                  └──────────────────────────┘
```

```text
AstraDroid/
├── src/AstraDroid.cpp                      # C++17 native UI + embedding
├── python/engine.py                        # SDK, AVD, APK & ADB orchestration
├── scripts/Enable-Windows-Acceleration.ps1
├── SETUP_WINDOWS.bat                       # Prerequisite installer flow
├── BUILD.bat                               # Produces bin\AstraDroid.exe
├── RUN.bat                                 # Launcher
└── README.vi.md                            # Hướng dẫn chi tiết tiếng Việt
```

## Privacy & phạm vi an toàn

- APK, hash và log được xử lý **trên máy cục bộ**.
- Chỉ cài APK mà bạn có quyền sử dụng và tin tưởng.
- SHA-256/chứng thư là tín hiệu kiểm tra, **không thay thế antivirus**.
- Không hỗ trợ root, bypass DRM, bypass license, can thiệp anti-cheat hay sideload `.apks`/`.xapk` trực tiếp.

## Hướng dẫn đầy đủ

Xem **[README.vi.md](README.vi.md)** để có cài đặt chi tiết, xử lý lỗi VT/SDK/AVD, các lệnh backend và giới hạn kỹ thuật.

---

<sub>AstraDroid — local Android application workspace for Windows.</sub>
