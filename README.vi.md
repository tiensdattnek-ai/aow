# AstraDroid — APK Workspace cho Windows

> **Bản build mặc định dùng Python GUI + PyInstaller để tạo `dist\AstraDroid.exe`, không yêu cầu Visual Studio hoặc MSVC C++ Build Tools.**

AstraDroid là workspace cục bộ để kiểm tra, cài và chạy APK trong Android Emulator trên Windows 10/11 x64. App có giao diện dark, kiểm tra VT, tạo AVD, kiểm tra hash/chữ ký APK, cài/chạy app, xem thiết bị và logcat.

## APK chạy như thế nào?

APK cần Android runtime, nên AstraDroid dùng **Android Emulator chính thức** từ Android SDK. Nó không biến APK thành `.exe` giả.

- Nếu Android Emulator/Qt/GPU driver cho phép: AstraDroid nhúng cửa sổ Emulator vào **Android Canvas**.
- Nếu không thể nhúng: Emulator chạy ở cửa sổ riêng, còn AstraDroid vẫn quản lý cài/chạy/log bằng ADB.

## Tính năng

- GUI Windows dark, activity log, status cards và phím tắt.
- Kiểm tra Intel VT-x / AMD SVM, SLAT, Windows Hypervisor features.
- Tạo AVD Pixel với Google APIs x86_64 system image mà SDK đang hỗ trợ.
- SHA-256 cục bộ; package, label, version, min SDK qua `aapt`; certificate qua `apksigner`.
- `adb install -r -g`, resolve launcher Activity rồi mở app.
- Thông tin Android device: model, Android version, API, pin.
- Bounded logcat dump, gỡ APK có xác nhận, dừng AVD.
- Không upload APK, không telemetry, không root/bypass DRM/Play Integrity.

## Yêu cầu

1. Windows 10/11 **64-bit**.
2. CPU có **Intel VT-x** hoặc **AMD SVM**; đã bật trong UEFI/BIOS.
3. Python 3 x64 với `py.exe`.
4. Internet ở lần build đầu để pip tải PyInstaller.
5. Android Studio hoặc Android SDK có đủ:
   - Android Emulator
   - Android SDK Platform-Tools
   - Android SDK Command-line Tools (latest)
   - Android SDK Build-Tools
   - Google APIs x86_64 system image

> Không cần Visual Studio, MSVC hoặc Windows C++ SDK để build bản mặc định.

Khuyến nghị: 16 GB RAM, CPU 4 core, 20–35 GB trống và GPU driver mới.

## Cài nhanh

1. Bật `Intel Virtualization Technology`, `VT-x` hoặc `SVM Mode` trong UEFI/BIOS, lưu rồi restart Windows.
2. Chạy:

```bat
SETUP_WINDOWS.bat
```

3. Nếu Android Studio mới cài: mở Android Studio một lần, hoàn tất SDK Setup Wizard; kiểm tra đủ các mục Android SDK ở trên.
4. Build GUI EXE:

```bat
BUILD.bat
```

5. Kết quả:

```text
dist\AstraDroid.exe
```

6. Mở bằng:

```bat
RUN.bat
```

hoặc mở trực tiếp `dist\AstraDroid.exe`.

`BUILD.bat` tự cài/cập nhật PyInstaller và giữ cửa sổ mở sau build. Log đầy đủ nằm ở:

```text
logs\build.log
```

## Sử dụng app

1. Bấm **KIỂM TRA HỆ THỐNG**.
2. Nếu VT chưa sẵn sàng: bật trong BIOS; sau đó bấm **CHUẨN BỊ WINDOWS** để bật Windows Hypervisor Platform / Virtual Machine Platform bằng Administrator rồi restart.
3. Bấm **TẠO ANDROID ẢO** lần đầu; thao tác này tải image lớn và cần bạn đồng ý Android SDK licenses.
4. Bấm **MỞ**, chờ Android boot.
5. Bấm **CHỌN APK**, chờ APK Inspector đọc thông tin.
6. Bấm **CÀI & CHẠY APK**.

### Phím tắt

| Phím | Tác vụ |
|---|---|
| `Ctrl + O` | Chọn APK |
| `Ctrl + Enter` | Cài và chạy APK đang chọn |
| `Ctrl + L` | Lấy logcat gần nhất |

## VT và Windows virtualization

AstraDroid có thể phát hiện VT nhưng không thể bật nó trong UEFI/BIOS — đó là cài đặt firmware do chủ máy kiểm soát.

Nút **CHUẨN BỊ WINDOWS** chạy `scripts\Enable-Windows-Acceleration.ps1` bằng quyền Administrator để bật các optional feature có sẵn:

- `HypervisorPlatform`
- `VirtualMachinePlatform`
- `Microsoft-Hyper-V-Hypervisor`
- `bcdedit /set hypervisorlaunchtype auto`

Sau đó Windows có thể yêu cầu restart.

## Khắc phục lỗi

### BUILD.bat báo không có `py.exe`

Cài Python 3 x64 và bật **Python Launcher** trong installer, mở Command Prompt mới rồi chạy lại. `SETUP_WINDOWS.bat` có thể cài Python qua `winget`.

### BUILD.bat báo lỗi PyInstaller / pip

Kiểm tra Internet, proxy/antivirus doanh nghiệp, sau đó chạy thủ công:

```bat
py -3 -m pip install --upgrade pyinstaller
BUILD.bat
```

Gửi nội dung `logs\build.log` nếu vẫn lỗi.

### Android SDK/Emulator không tìm thấy

Mở Android Studio → SDK Manager, cài Emulator, Platform-Tools, Command-line Tools, Build-Tools và Google APIs x86_64 image. Nếu SDK ở đường dẫn khác, đặt biến môi trường:

```bat
setx ANDROID_SDK_ROOT "D:\Android\Sdk"
```

Mở terminal mới sau lệnh `setx`.

### Emulator không nhúng vào Android Canvas

Một số bản Qt/Emulator/GPU driver không cho chuyển top-level window thành child window. Đây là fallback có chủ đích: app chạy trong cửa sổ Emulator riêng, còn AstraDroid vẫn điều khiển ADB bình thường.

## Kiến trúc

```text
python/app.py       Dark Tk GUI + best-effort Emulator embedding
python/engine.py    SDK / AVD / APK metadata / ADB control plane
BUILD.bat           PyInstaller one-file package → dist\AstraDroid.exe
RUN.bat             Launch packaged GUI
src/AstraDroid.cpp  Native C++ host reference, không dùng trong default build
```

Không có Python dependency runtime ngoài standard library; PyInstaller chỉ là dependency ở thời điểm build.

## Bảo mật và phạm vi

- Chỉ xử lý dữ liệu trên máy cục bộ.
- Chỉ cài APK bạn có quyền sử dụng và tin tưởng.
- Hash/chứng thư không thay thế antivirus.
- Chỉ hỗ trợ `.apk` trực tiếp; `.apks`/`.xapk` cần chuyển đổi/giải nén trước.
- Không hỗ trợ root, bypass DRM, bypass license hoặc can thiệp anti-cheat.
