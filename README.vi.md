# AstraDroid — APK Workspace cho Windows

> **Ứng dụng desktop Win32 bằng C++ để quản lý, kiểm tra, cài và chạy APK trong Android Emulator, với control plane Python và bộ cài `.bat`.**
>
> Phiên bản nguồn: **1.1.0** · GUI native dark/Fluent · thiết kế cho **Windows 10/11 x64**

AstraDroid cung cấp một cửa sổ điều khiển duy nhất: chọn APK, xem package/hash/chữ ký, kiểm tra VT-x/AMD-V, tạo AVD, khởi động Android rồi cài và mở app. Khi Android Emulator/Qt cho phép, cửa sổ Android được **nhúng thẳng vào vùng “Android Canvas”** của AstraDroid.

## Điều quan trọng: APK không chạy native trực tiếp trên Windows

APK cần Android runtime. Cách kỹ thuật ổn định và hợp pháp nhất trên Windows là dùng **Android Emulator chính thức của Android SDK**. AstraDroid không giả vờ biến APK thành `.exe`; nó điều khiển Android Emulator cục bộ và cố gắng gắn cửa sổ emulator vào app host.

- Nếu Qt/driver cho phép re-parent cửa sổ, ứng dụng Android hiện **ngay trong AstraDroid**.
- Nếu bản Emulator, GPU driver hoặc chính sách cửa sổ chặn re-parenting, emulator vẫn chạy bình thường trong **cửa sổ riêng**; AstraDroid báo rõ điều đó và vẫn cài/chạy APK được.
- Không dùng WSA: Windows Subsystem for Android đã kết thúc hỗ trợ, nên không phải nền tảng nên xây mới.

## Tính năng cao cấp có sẵn

| Nhóm | Khả năng |
|---|---|
| **GUI native đẹp** | Dark Fluent/Mica khi Windows hỗ trợ, gradient, card trạng thái thời gian thực, corner bo tròn, focus state, min-size bảo vệ layout và activity log có font mono. Không dùng Electron. |
| **Kiểm tra máy** | Đọc CPU virtualization extensions, trạng thái VT/SVM trong firmware, SLAT, Hyper-V và Windows feature state. |
| **Android canvas** | Khởi động official Emulator với GPU host, dò PID, gắn render window vào native host và tự co giãn theo cửa sổ. |
| **Trải nghiệm nhanh** | Kéo-thả APK vào app; `Ctrl+O` chọn APK; `Ctrl+Enter` cài/chạy; `Ctrl+L` lấy logcat. |
| **APK intelligence** | SHA-256 cục bộ; package id, label, version, min SDK bằng `aapt`; xác minh signing certificate bằng `apksigner` khi Build-Tools hiện diện. |
| **Lifecycle AVD** | Tự tìm system image x86_64 Google APIs mới nhất *mà SDK hiện tại hiển thị*, cài theo xác nhận của bạn và tạo AVD Pixel. |
| **Cài & chạy** | Chờ thiết bị qua `adb`, `adb install -r -g`, sau đó resolve launcher activity thay vì đoán Activity class. Có nút gỡ APK với xác nhận rõ ràng. |
| **Công cụ ADB** | Device card hiển thị model/Android/API/pin khi bấm **THÔNG TIN THIẾT BỊ**; lấy bounded `logcat` gần nhất; xóa activity log trong một cú nhấp. |
| **An toàn** | Không tải APK lên server; không root, không bypass Play Integrity, không mở khóa bootloader; toàn bộ tác vụ SDK đi qua argv (không shell-inject path APK). |
| **Vận hành** | Nhật ký cục bộ trong UI, lệnh chạy bất đồng bộ, báo lỗi có ích, không treo cửa sổ khi image lần đầu tải. |

## Yêu cầu

### Bắt buộc

1. **Windows 10/11 64-bit**.
2. CPU có **Intel VT-x** hoặc **AMD SVM** và đã bật trong **UEFI/BIOS**.
3. Tài khoản Windows được phép chạy Android Emulator.
4. **Python 3 x64** với `py.exe` (Python Launcher).
5. **Visual Studio 2022 Build Tools**, workload `Desktop development with C++` / `MSVC x64`.
6. **Android Studio** hoặc Android SDK đầy đủ, có:
   - Android Emulator
   - Android SDK Platform-Tools
   - Android SDK Command-line Tools (latest)
   - Android SDK Build-Tools (để đọc metadata/xác minh certificate)
   - Một **Google APIs x86_64 system image**

### Khuyến nghị cho trải nghiệm mượt

- 16 GB RAM (8 GB là mức tối thiểu thực tế), CPU 4 core trở lên.
- 20–35 GB trống cho Android Studio, system image, AVD và snapshot.
- GPU driver mới. AstraDroid khởi động Emulator bằng `-gpu host`.

## Cài và chạy nhanh

1. Giải nén/thả thư mục `AstraDroid` vào một nơi có quyền ghi, ví dụ `C:\Tools\AstraDroid`.
2. **Bật VT trước**: vào UEFI/BIOS, bật `Intel Virtualization Technology`, `VT-x`, `SVM Mode` hoặc tên tương đương. Lưu và restart Windows.
3. Chuột phải **`SETUP_WINDOWS.bat` → Run as normal user**. Script có thể dùng `winget` để cài Python, Android Studio và Build Tools sau khi bạn đồng ý.
4. Nếu Android Studio vừa được cài, mở nó một lần và hoàn tất SDK Setup Wizard. Vào **SDK Manager** kiểm tra đủ các mục ở phần Yêu cầu.
5. Chạy **`BUILD.bat`**. Bản thực thi sẽ nằm tại `bin\AstraDroid.exe`.
6. Chạy **`RUN.bat`** hoặc mở `bin\AstraDroid.exe`.
7. Trong app:
   - chọn **KIỂM TRA HỆ THỐNG**;
   - nếu VT/Windows acceleration chưa sẵn sàng, chọn **CHUẨN BỊ WINDOWS**, xác nhận UAC rồi restart nếu được yêu cầu;
   - chọn **TẠO ANDROID ẢO** một lần (tải image lớn và yêu cầu xác nhận SDK licenses);
   - chọn **MỞ**, chờ Android boot;
   - chọn **CHỌN APK**, sau đó **CÀI & CHẠY APK**.

## VT / ảo hóa: AstraDroid có thể và không thể làm gì

AstraDroid phát hiện và giải thích trạng thái nhưng **không thể bật VT-x/AMD-V trong firmware** — đó là giới hạn phần cứng/UEFI có chủ đích.

Nút **CHUẨN BỊ WINDOWS** chỉ chạy `scripts\Enable-Windows-Acceleration.ps1` bằng quyền Administrator để bật các Windows Optional Features sau, rồi yêu cầu restart:

- `HypervisorPlatform`
- `VirtualMachinePlatform`
- `Microsoft-Hyper-V-Hypervisor` (nếu edition Windows có feature này)
- `bcdedit /set hypervisorlaunchtype auto`

Đọc trạng thái, hoặc chạy script **không có `-Apply`**, sẽ không thay đổi hệ thống.

## Cấu trúc mã nguồn

```text
AstraDroid/
├─ src/AstraDroid.cpp                         # C++17 / Win32 native UI + emulator embedding
├─ python/engine.py                           # Python stdlib: SDK, AVD, adb, APK inspection
├─ scripts/Enable-Windows-Acceleration.ps1    # Windows optional feature preparation
├─ BUILD.bat                                  # Build C++ bằng MSVC
├─ RUN.bat                                    # Launcher
├─ SETUP_WINDOWS.bat                          # Guided prerequisite setup
└─ README.vi.md
```

### Phân công công nghệ

- **C++/Win32:** giao diện desktop không phụ thuộc Electron, file picker, native render host, async UI, resize, PID-based safe window embedding.
- **Python (chỉ standard library):** probe Windows/PowerShell, tìm SDK, chạy `sdkmanager`/`avdmanager`/`adb`, hash APK, orchestration bằng JSON một dòng.
- **Batch/PowerShell:** cài prerequisite, build, launch và thao tác Windows cần Administrator.

Không cần `pip install` bất cứ package Python nào.

## Lệnh backend hữu ích

Mở Command Prompt tại thư mục dự án:

```bat
py -3 -X utf8 python\engine.py status
py -3 -X utf8 python\engine.py inspect-apk --apk "D:\Downloads\my-app.apk"
py -3 -X utf8 python\engine.py create-avd --avd AstraDroid_Pixel --download
py -3 -X utf8 python\engine.py start --avd AstraDroid_Pixel
py -3 -X utf8 python\engine.py install --apk "D:\Downloads\my-app.apk" --package com.example.app
py -3 -X utf8 python\engine.py launch --package com.example.app
py -3 -X utf8 python\engine.py device-info
py -3 -X utf8 python\engine.py logcat --lines 350
py -3 -X utf8 python\engine.py uninstall --package com.example.app
py -3 -X utf8 python\engine.py stop
```

Mỗi lệnh backend trả về **một JSON object** để native host có thể log/hiển thị lỗi nhất quán.

## Đường dẫn SDK được tự nhận diện

Ưu tiên lần lượt: `ANDROID_SDK_ROOT`, `ANDROID_HOME`, `%LOCALAPPDATA%\Android\Sdk`, sau đó Android Studio SDK mặc định. Nếu SDK ở nơi khác, đặt biến môi trường vĩnh viễn, ví dụ:

```bat
setx ANDROID_SDK_ROOT "D:\Android\Sdk"
```

Mở cửa sổ Command Prompt/AstraDroid mới sau khi dùng `setx`.

## Khắc phục sự cố

### “VT-x / AMD-V cần bật trong UEFI”

Vào UEFI/BIOS, bật VT-x/SVM. Nếu đã bật nhưng app vẫn báo tắt:

1. Chạy **CHUẨN BỊ WINDOWS** với UAC, sau đó restart.
2. Cập nhật BIOS/UEFI nếu cần.
3. Kiểm tra Task Manager → Performance → CPU → `Virtualization: Enabled`.
4. Trên máy công ty/VM cloud, hypervisor cha có thể chưa cho nested virtualization.

### “Chưa tìm thấy Android Emulator”

Mở Android Studio → SDK Manager và cài Android Emulator + Platform-Tools + Command-line Tools. Nếu SDK không ở đường dẫn mặc định, đặt `ANDROID_SDK_ROOT` như trên.

### “Không tìm được system image x86_64”

Trong SDK Manager → SDK Platforms/SDK Tools, cài ít nhất một `Google APIs Intel x86_64 Atom System Image`. Sau đó bấm lại **TẠO ANDROID ẢO**.

### APK cài được nhưng không tự mở

APK không có launcher Activity, hoặc metadata chưa đọc được do thiếu Build-Tools. Cài Android SDK Build-Tools, chọn lại APK để AstraDroid đọc package id. App không có launcher có thể cần mở activity/service bằng lệnh `adb` chuyên biệt.

### Emulator mở nhưng không xuất hiện trong Android Canvas

Đây thường là giới hạn Qt/driver đối với child-window embedding. Cửa sổ emulator riêng vẫn hoàn toàn hoạt động. Cập nhật Android Emulator, GPU driver, rồi thử lại. AstraDroid không đóng hoặc làm hỏng emulator trong trường hợp fallback này.

### Build lỗi `cl.exe` / `py.exe` không tìm thấy

Chạy `SETUP_WINDOWS.bat`, hoặc cài thủ công Visual Studio Build Tools với C++ workload / Python x64 rồi mở một Command Prompt mới.

## Phạm vi và bảo mật

- Chỉ cài các APK bạn có quyền sử dụng và tin tưởng. Hash và certificate giúp kiểm tra, **không phải** dịch vụ antivirus.
- APK, hash và AVD đều xử lý trên máy cục bộ. AstraDroid không bao gồm telemetry, analytics hay upload nền.
- App không hỗ trợ bypass DRM, root emulator, né kiểm tra license hoặc can thiệp chống gian lận.
- `.apk` trực tiếp được hỗ trợ. `.apks` / `.xapk` cần giải nén/chuyển đổi thành APK cài được trước.

---

**Gợi ý nâng cấp tiếp theo:** profiles AVD nhiều phiên bản Android, drag-and-drop APK, báo cáo SBOM/chứng thư APK, snapshot controls, logcat viewer có lọc, hoặc plugin test automation qua `adb`. Kiến trúc native host + Python engine đã tách lớp để bổ sung các mô-đun này mà không đổi luồng an toàn hiện có.
