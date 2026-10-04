// AstraDroid - native Win32 APK workspace host
// Build: MSVC /std:c++17 /DUNICODE /D_UNICODE /EHsc
// The Python control plane owns Android SDK calls; this binary owns the UI and
// optionally reparents the Android Emulator window into the "Android canvas".

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <commdlg.h>
#include <shellapi.h>
#include <dwmapi.h>
#include <filesystem>
#include <string>
#include <thread>
#include <atomic>
#include <vector>
#include <algorithm>
#include <iterator>

#pragma comment(lib, "Comdlg32.lib")
#pragma comment(lib, "Shell32.lib")
#pragma comment(lib, "Dwmapi.lib")
#pragma comment(lib, "Msimg32.lib")

constexpr UINT WM_ENGINE_RESULT = WM_APP + 41;
constexpr UINT ID_TIMER_EMBED = 71;
constexpr int ID_PICK = 1001;
constexpr int ID_DIAG = 1002;
constexpr int ID_CREATE = 1003;
constexpr int ID_START = 1004;
constexpr int ID_INSTALL = 1005;
constexpr int ID_STOP = 1006;
constexpr int ID_ACCEL = 1007;
constexpr int ID_DEVICE = 1008;
constexpr int ID_LOGCAT = 1009;
constexpr int ID_UNINSTALL = 1010;
constexpr int ID_CLEAR_LOG = 1011;

enum Action { ACT_STATUS, ACT_INSPECT, ACT_CREATE, ACT_START, ACT_INSTALL, ACT_LAUNCH, ACT_STOP, ACT_DEVICE, ACT_LOGCAT, ACT_UNINSTALL };
struct EngineResult { Action action; std::wstring text; };

HWND gWindow = nullptr, gCanvas = nullptr, gLog = nullptr;
HWND gButtons[12]{};
HFONT gFont = nullptr, gFontTitle = nullptr, gFontHero = nullptr, gFontMono = nullptr;
std::wstring gRoot, gApk, gPackage, gApkLabel = L"Kéo thả APK vào đây hoặc bấm CHỌN APK";
std::wstring gVt = L"Đang kiểm tra Virtualization Technology…";
std::wstring gSdk = L"Đang dò Android SDK…";
std::wstring gCanvasState = L"Chưa khởi động emulator";
std::wstring gDeviceState = L"Thiết bị Android chưa online";
std::wstring gApkMeta = L"Chưa có thông tin package / signature";
bool gDropActive = false;
DWORD gEmulatorPid = 0;
HWND gEmulatorWindow = nullptr;
int gEmbedAttempts = 0;
std::atomic_bool gBusy{ false };

const COLORREF C_BG = RGB(9, 13, 25);
const COLORREF C_SIDEBAR = RGB(15, 20, 37);
const COLORREF C_PANEL = RGB(26, 34, 55);
const COLORREF C_PANEL_2 = RGB(35, 46, 72);
const COLORREF C_CANVAS = RGB(6, 10, 19);
const COLORREF C_TEXT = RGB(240, 244, 255);
const COLORREF C_MUTED = RGB(154, 170, 201);
const COLORREF C_ACCENT = RGB(92, 123, 255);
const COLORREF C_PURPLE = RGB(155, 91, 255);
const COLORREF C_GOOD = RGB(47, 207, 151);
const COLORREF C_WARN = RGB(255, 185, 70);
const COLORREF C_DANGER = RGB(245, 90, 111);

std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
    if (!n) return L"[Không thể đọc UTF-8 từ engine]";
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), w.data(), n);
    return w;
}

std::wstring Quote(const std::wstring& value) {
    // Windows file names cannot contain a double quote. All values reaching
    // cmd.exe here are either app-generated or selected from the file picker.
    return L"\"" + value + L"\"";
}

std::wstring JsonString(const std::wstring& json, const std::wstring& key) {
    std::wstring needle = L"\"" + key + L"\":\"";
    size_t start = json.find(needle);
    if (start == std::wstring::npos) return L"";
    start += needle.size();
    std::wstring out;
    bool escape = false;
    for (size_t i = start; i < json.size(); ++i) {
        wchar_t c = json[i];
        if (escape) {
            switch (c) {
            case L'n': out += L'\n'; break;
            case L'r': out += L'\r'; break;
            case L't': out += L'\t'; break;
            case L'\\': out += L'\\'; break;
            case L'\"': out += L'\"'; break;
            default: out += c; break;
            }
            escape = false;
        } else if (c == L'\\') {
            escape = true;
        } else if (c == L'\"') {
            return out;
        } else {
            out += c;
        }
    }
    return out;
}

bool JsonTrue(const std::wstring& json, const std::wstring& key) {
    return json.find(L"\"" + key + L"\":true") != std::wstring::npos;
}

DWORD JsonNumber(const std::wstring& json, const std::wstring& key) {
    std::wstring needle = L"\"" + key + L"\":";
    size_t p = json.find(needle);
    if (p == std::wstring::npos) return 0;
    p += needle.size();
    try { return (DWORD)std::stoul(json.substr(p)); }
    catch (...) { return 0; }
}

std::string ReadPipe(HANDLE pipe) {
    std::string all;
    char buffer[4096];
    DWORD bytes = 0;
    while (ReadFile(pipe, buffer, sizeof(buffer), &bytes, nullptr) && bytes > 0) all.append(buffer, bytes);
    return all;
}

std::wstring ExecuteEngine(const std::wstring& args) {
    std::wstring python = L"py -3 -X utf8 ";
    std::wstring command = python + Quote(gRoot + L"\\python\\engine.py") + L" " + args;
    std::vector<wchar_t> cmd(command.begin(), command.end());
    cmd.push_back(L'\0');

    SECURITY_ATTRIBUTES security{ sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE };
    HANDLE readPipe = nullptr, writePipe = nullptr;
    if (!CreatePipe(&readPipe, &writePipe, &security, 0)) return L"{\"ok\":false,\"message\":\"Không tạo được output pipe.\"}";
    SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
    si.wShowWindow = SW_HIDE;
    si.hStdOutput = writePipe;
    si.hStdError = writePipe;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    PROCESS_INFORMATION pi{};

    // Direct CreateProcess runs py.exe without invoking cmd.exe, keeping paths
    // with spaces and APK names safe from shell expansion.
    BOOL created = CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, TRUE,
        CREATE_NO_WINDOW, nullptr, gRoot.c_str(), &si, &pi);
    CloseHandle(writePipe);
    if (!created) {
        CloseHandle(readPipe);
        return L"{\"ok\":false,\"message\":\"Không mở được Python Launcher. Hãy cài Python 3 (py.exe).\"}";
    }
    std::string raw = ReadPipe(readPipe);
    CloseHandle(readPipe);
    WaitForSingleObject(pi.hProcess, INFINITE);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return Utf8ToWide(raw);
}

void AppendLog(const std::wstring& line) {
    if (!gLog) return;
    SYSTEMTIME st{}; GetLocalTime(&st);
    wchar_t prefix[32]{};
    wsprintfW(prefix, L"[%02d:%02d:%02d] ", st.wHour, st.wMinute, st.wSecond);
    std::wstring entry = std::wstring(prefix) + line + L"\r\n";
    int current = GetWindowTextLengthW(gLog);
    if (current > 28000) SetWindowTextW(gLog, L"");
    SendMessageW(gLog, EM_SETSEL, (WPARAM)-1, (LPARAM)-1);
    SendMessageW(gLog, EM_REPLACESEL, FALSE, (LPARAM)entry.c_str());
    SendMessageW(gLog, EM_SCROLLCARET, 0, 0);
}

void UpdateControls(bool enabled) {
    int ids[] = { ID_PICK, ID_DIAG, ID_CREATE, ID_START, ID_INSTALL, ID_STOP, ID_ACCEL, ID_DEVICE, ID_LOGCAT, ID_UNINSTALL };
    for (int id : ids) if (gButtons[id - ID_PICK]) EnableWindow(gButtons[id - ID_PICK], enabled);
}

void Invoke(Action action, const std::wstring& arguments) {
    if (gBusy.exchange(true)) {
        AppendLog(L"Một tác vụ đang chạy. Vui lòng chờ hoàn tất.");
        return;
    }
    UpdateControls(false);
    AppendLog(L"→ " + arguments);
    std::thread([action, arguments]() {
        auto* result = new EngineResult{ action, ExecuteEngine(arguments) };
        PostMessageW(gWindow, WM_ENGINE_RESULT, 0, (LPARAM)result);
    }).detach();
}

BOOL CALLBACK FindEmulatorWindowProc(HWND candidate, LPARAM) {
    if (!IsWindowVisible(candidate) || candidate == gWindow || GetParent(candidate)) return TRUE;
    DWORD pid = 0; GetWindowThreadProcessId(candidate, &pid);
    if (pid != gEmulatorPid) return TRUE;
    // Android Emulator's first visible, unowned top-level Qt window is the
    // render surface. It is deliberately identified by PID, never title text.
    gEmulatorWindow = candidate;
    return FALSE;
}

void ResizeEmbedded() {
    if (!gCanvas || !gEmulatorWindow || !IsWindow(gEmulatorWindow)) return;
    RECT r{}; GetClientRect(gCanvas, &r);
    SetWindowPos(gEmulatorWindow, HWND_TOP, 0, 0, r.right, r.bottom, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
}

void AttemptEmbed() {
    if (gEmulatorWindow && IsWindow(gEmulatorWindow)) { ResizeEmbedded(); KillTimer(gWindow, ID_TIMER_EMBED); return; }
    EnumWindows(FindEmulatorWindowProc, 0);
    ++gEmbedAttempts;
    if (gEmulatorWindow) {
        LONG_PTR style = GetWindowLongPtrW(gEmulatorWindow, GWL_STYLE);
        SetWindowLongPtrW(gEmulatorWindow, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD | WS_VISIBLE);
        SetParent(gEmulatorWindow, gCanvas);
        ResizeEmbedded();
        gCanvasState = L"Emulator đã được gắn vào cửa sổ AstraDroid";
        AppendLog(L"✓ Android Emulator đã chạy bên trong Android canvas.");
        KillTimer(gWindow, ID_TIMER_EMBED);
        InvalidateRect(gWindow, nullptr, FALSE);
    } else if (gEmbedAttempts > 55) {
        gCanvasState = L"Emulator đang chạy trong cửa sổ riêng (Qt không cho nhúng ở cấu hình này)";
        AppendLog(L"! Không thể nhúng cửa sổ sau 55 giây. Emulator vẫn có thể dùng ở cửa sổ riêng.");
        KillTimer(gWindow, ID_TIMER_EMBED);
        InvalidateRect(gWindow, nullptr, FALSE);
    }
}

void VerticalGradient(HDC hdc, const RECT& r, COLORREF top, COLORREF bottom) {
    TRIVERTEX vertex[2]{};
    vertex[0].x = r.left;  vertex[0].y = r.top;
    vertex[0].Red = (COLOR16)(GetRValue(top) << 8); vertex[0].Green = (COLOR16)(GetGValue(top) << 8); vertex[0].Blue = (COLOR16)(GetBValue(top) << 8); vertex[0].Alpha = 0xFF00;
    vertex[1].x = r.right; vertex[1].y = r.bottom;
    vertex[1].Red = (COLOR16)(GetRValue(bottom) << 8); vertex[1].Green = (COLOR16)(GetGValue(bottom) << 8); vertex[1].Blue = (COLOR16)(GetBValue(bottom) << 8); vertex[1].Alpha = 0xFF00;
    GRADIENT_RECT gradient{ 0, 1 };
    GradientFill(hdc, vertex, 2, &gradient, 1, GRADIENT_FILL_RECT_V);
}

void Rounded(HDC hdc, const RECT& r, COLORREF fill, int radius = 16) {
    HBRUSH brush = CreateSolidBrush(fill);
    HPEN pen = CreatePen(PS_SOLID, 1, fill);
    HGDIOBJ oldB = SelectObject(hdc, brush), oldP = SelectObject(hdc, pen);
    RoundRect(hdc, r.left, r.top, r.right, r.bottom, radius, radius);
    SelectObject(hdc, oldB); SelectObject(hdc, oldP);
    DeleteObject(brush); DeleteObject(pen);
}

void Text(HDC hdc, const std::wstring& text, RECT r, HFONT font, COLORREF color, UINT flags = DT_LEFT | DT_TOP) {
    HGDIOBJ old = SelectObject(hdc, font);
    SetBkMode(hdc, TRANSPARENT); SetTextColor(hdc, color);
    DrawTextW(hdc, text.c_str(), -1, &r, flags);
    SelectObject(hdc, old);
}

void DrawDashboard(HDC hdc, const RECT& client) {
    VerticalGradient(hdc, client, C_BG, RGB(18, 21, 43));
    RECT side{ 0, 0, 250, client.bottom }; VerticalGradient(hdc, side, C_SIDEBAR, RGB(11, 16, 31));
    RECT accent{ 0, 0, 5, client.bottom }; HBRUSH accentBrush = CreateSolidBrush(C_ACCENT); FillRect(hdc, &accent, accentBrush); DeleteObject(accentBrush);

    RECT logo{ 26, 28, 72, 74 }; Rounded(hdc, logo, C_ACCENT, 14);
    Text(hdc, L"A", logo, gFontTitle, RGB(255, 255, 255), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    Text(hdc, L"AstraDroid", { 84, 30, 230, 58 }, gFontTitle, C_TEXT);
    Text(hdc, L"ANDROID ON WINDOWS", { 86, 61, 230, 80 }, gFont, C_MUTED);
    Text(hdc, L"LOCAL • PRIVATE • HARDWARE ACCELERATED", { 27, 105, 229, 127 }, gFont, C_MUTED, DT_LEFT | DT_WORDBREAK);
    Text(hdc, L"WORKSPACE", { 27, 200, 210, 220 }, gFont, C_MUTED);

    int x = 278, right = client.right - 26;
    Text(hdc, L"APK Studio", { x, 24, right, 67 }, gFontHero, C_TEXT);
    Text(hdc, L"Một workspace cục bộ để kiểm tra, cài đặt và chạy Android app an toàn trên Windows.", { x, 70, right - 230, 96 }, gFont, C_MUTED);
    RECT privacy{ right - 184, 34, right, 69 }; Rounded(hdc, privacy, RGB(31, 55, 84), 17);
    Text(hdc, L"●  PRIVATE LOCAL", { privacy.left + 12, privacy.top + 9, privacy.right - 8, privacy.bottom }, gFont, C_GOOD, DT_LEFT | DT_SINGLELINE);

    int gap = 12, cardW = std::max(175, (right - x - gap * 2) / 3);
    RECT cards[3] = { {x, 118, x + cardW, 185}, {x + cardW + gap, 118, x + cardW * 2 + gap, 185}, {x + (cardW + gap) * 2, 118, right, 185} };
    const std::wstring heads[3] = { L"VIRTUALIZATION", L"ANDROID SDK", L"DEVICE" };
    const std::wstring values[3] = { gVt, gSdk, gDeviceState };
    for (int i = 0; i < 3; ++i) {
        Rounded(hdc, cards[i], C_PANEL, 16);
        bool deviceOnline = gDeviceState.find(L"online") != std::wstring::npos && gDeviceState.find(L"chưa online") == std::wstring::npos;
        COLORREF dot = i == 0 ? (gVt.find(L"sẵn sàng") != std::wstring::npos ? C_GOOD : C_WARN) : (i == 1 ? (gSdk.find(L"sẵn sàng") != std::wstring::npos ? C_GOOD : C_WARN) : (deviceOnline ? C_GOOD : C_MUTED));
        // Ellipse uses the currently selected brush; select explicitly to avoid inheriting a stale GDI object.
        HBRUSH dotBrush = CreateSolidBrush(dot); HGDIOBJ oldBrush = SelectObject(hdc, dotBrush); HPEN dotPen = CreatePen(PS_SOLID, 1, dot); HGDIOBJ oldPen = SelectObject(hdc, dotPen);
        Ellipse(hdc, cards[i].left + 16, cards[i].top + 15, cards[i].left + 25, cards[i].top + 24);
        SelectObject(hdc, oldBrush); SelectObject(hdc, oldPen); DeleteObject(dotBrush); DeleteObject(dotPen);
        Text(hdc, heads[i], { cards[i].left + 33, cards[i].top + 11, cards[i].right - 12, cards[i].top + 31 }, gFont, C_MUTED, DT_LEFT | DT_SINGLELINE);
        Text(hdc, values[i], { cards[i].left + 16, cards[i].top + 36, cards[i].right - 14, cards[i].bottom - 9 }, gFont, dot, DT_LEFT | DT_WORDBREAK | DT_END_ELLIPSIS);
    }

    RECT apkCard{ x, 208, 540, 332 }; Rounded(hdc, apkCard, gDropActive ? RGB(39, 57, 102) : C_PANEL, 18);
    Text(hdc, gDropActive ? L"THẢ APK ĐỂ KIỂM TRA" : L"APK INSPECTOR", { x + 18, 222, 523, 243 }, gFont, gDropActive ? C_ACCENT : C_MUTED);
    Text(hdc, gApkLabel, { x + 18, 252, 523, 278 }, gFont, C_TEXT, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    std::wstring packageText = gPackage.empty() ? L"Kéo APK vào cửa sổ hoặc dùng Ctrl + O" : gPackage;
    Text(hdc, packageText, { x + 18, 279, 523, 300 }, gFont, C_ACCENT, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    Text(hdc, gApkMeta, { x + 18, 303, 523, 324 }, gFont, C_MUTED, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);

    int canvasLeft = 566;
    Text(hdc, L"ANDROID CANVAS", { canvasLeft, 208, right, 229 }, gFont, C_MUTED);
    Text(hdc, gCanvasState, { canvasLeft, 231, right, 251 }, gFont, C_TEXT, DT_LEFT | DT_SINGLELINE | DT_END_ELLIPSIS);
    RECT canvasFrame{ canvasLeft - 4, 260, right + 4, std::max(480, client.bottom - 232) }; Rounded(hdc, canvasFrame, C_PANEL_2, 18);

    int logTop = std::max(550, client.bottom - 218);
    Text(hdc, L"ACTIVITY LOG", { x, logTop - 25, right, logTop - 5 }, gFont, C_MUTED);
    Text(hdc, L"Ctrl+L: logcat  •  Ctrl+Enter: cài & chạy  •  Ctrl+O: chọn APK", { x + 120, logTop - 25, right, logTop - 5 }, gFont, C_MUTED, DT_RIGHT | DT_SINGLELINE);

    int footerY = client.bottom - 28;
    Text(hdc, L"AstraDroid v1.1  •  Android SDK Emulator  •  Không upload dữ liệu APK", { 27, footerY, 240, client.bottom - 6 }, gFont, C_MUTED, DT_LEFT | DT_WORDBREAK);
}

void Layout(HWND hwnd) {
    RECT r{}; GetClientRect(hwnd, &r);
    int width = r.right, height = r.bottom;
    int canvasLeft = 570;
    int logTop = std::max(550, height - 218);
    int canvasBottom = logTop - 14;
    MoveWindow(gButtons[ID_PICK - ID_PICK], 26, 232, 198, 36, TRUE);
    MoveWindow(gButtons[ID_DIAG - ID_PICK], 26, 276, 198, 36, TRUE);
    MoveWindow(gButtons[ID_CREATE - ID_PICK], 26, 320, 198, 36, TRUE);
    MoveWindow(gButtons[ID_START - ID_PICK], 26, 364, 95, 36, TRUE);
    MoveWindow(gButtons[ID_STOP - ID_PICK], 129, 364, 95, 36, TRUE);
    MoveWindow(gButtons[ID_INSTALL - ID_PICK], 26, 408, 198, 36, TRUE);
    MoveWindow(gButtons[ID_DEVICE - ID_PICK], 26, 452, 198, 36, TRUE);
    MoveWindow(gButtons[ID_LOGCAT - ID_PICK], 26, 496, 198, 36, TRUE);
    MoveWindow(gButtons[ID_UNINSTALL - ID_PICK], 26, 540, 198, 36, TRUE);
    MoveWindow(gButtons[ID_ACCEL - ID_PICK], 26, 584, 198, 36, TRUE);
    MoveWindow(gButtons[ID_CLEAR_LOG - ID_PICK], 26, 628, 198, 32, TRUE);
    MoveWindow(gCanvas, canvasLeft, 264, std::max(160, width - canvasLeft - 30), std::max(210, canvasBottom - 264), TRUE);
    MoveWindow(gLog, 278, logTop, std::max(200, width - 304), std::max(100, height - logTop - 32), TRUE);
    ResizeEmbedded();
}

HWND AddButton(HWND parent, int id, const wchar_t* label) {
    HWND b = CreateWindowExW(0, L"BUTTON", label, WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 100, 38, parent, (HMENU)(INT_PTR)id, GetModuleHandleW(nullptr), nullptr);
    SendMessageW(b, WM_SETFONT, (WPARAM)gFont, TRUE);
    return b;
}

void SelectApk(const std::wstring& file) {
    std::filesystem::path selected(file);
    if (selected.extension() != L".apk" && selected.extension() != L".APK") {
        MessageBoxW(gWindow, L"AstraDroid hiện nhận APK trực tiếp (.apk). Hãy giải nén APKS/XAPK trước.", L"Định dạng chưa hỗ trợ", MB_ICONINFORMATION);
        return;
    }
    gApk = selected.wstring();
    gPackage.clear();
    gApkLabel = selected.filename().wstring();
    gApkMeta = L"Đang đọc package, hash SHA-256 và certificate…";
    InvalidateRect(gWindow, nullptr, FALSE);
    Invoke(ACT_INSPECT, L"inspect-apk --apk " + Quote(gApk));
}

void PickApk(HWND hwnd) {
    wchar_t file[MAX_PATH * 4]{};
    OPENFILENAMEW dialog{};
    dialog.lStructSize = sizeof(dialog); dialog.hwndOwner = hwnd; dialog.lpstrFile = file; dialog.nMaxFile = (DWORD)std::size(file);
    dialog.lpstrFilter = L"Android package (*.apk)\0*.apk\0All files\0*.*\0";
    dialog.lpstrTitle = L"Chọn APK để kiểm tra và cài";
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY;
    if (!GetOpenFileNameW(&dialog)) return;
    SelectApk(file);
}

void ReceiveResult(EngineResult* result) {
    gBusy = false; UpdateControls(true);
    const std::wstring& json = result->text;
    bool ok = JsonTrue(json, L"ok");
    std::wstring message = JsonString(json, L"message");
    std::wstring output = JsonString(json, L"output");
    if (message.empty()) message = ok ? L"Hoàn tất." : L"Tác vụ không thành công.";
    AppendLog((ok ? L"✓ " : L"✕ ") + message);
    if (!output.empty()) AppendLog(output);

    if (result->action == ACT_STATUS) {
        gVt = JsonTrue(json, L"firmware_enabled") ? L"VT-x / AMD-V sẵn sàng" : L"VT-x / AMD-V cần bật trong UEFI";
        gSdk = JsonTrue(json, L"sdk_ready") ? L"Emulator sẵn sàng" : L"Chưa tìm thấy Emulator";
        InvalidateRect(gWindow, nullptr, FALSE);
    } else if (result->action == ACT_INSPECT && ok) {
        std::wstring name = JsonString(json, L"name");
        std::wstring label = JsonString(json, L"label");
        gPackage = JsonString(json, L"package");
        if (!name.empty()) gApkLabel = label.empty() ? name : label + L"  ·  " + name;
        std::wstring signing = JsonString(json, L"signing");
        std::wstring hash = JsonString(json, L"sha256");
        std::wstring version = JsonString(json, L"version_name");
        gApkMeta = (version.empty() ? L"" : L"v" + version + L"  •  ") + (signing.empty() ? L"Chưa xác minh signature" : signing);
        AppendLog(L"Package: " + (gPackage.empty() ? L"không đọc được (thiếu build-tools/aapt)" : gPackage));
        if (!signing.empty()) AppendLog(L"Chữ ký: " + signing);
        if (!hash.empty()) AppendLog(L"SHA-256: " + hash);
        InvalidateRect(gWindow, nullptr, FALSE);
    } else if (result->action == ACT_START && ok) {
        gEmulatorPid = JsonNumber(json, L"pid");
        gEmulatorWindow = nullptr; gEmbedAttempts = 0;
        gCanvasState = L"Đang khởi động Android… đang chờ render surface";
        SetTimer(gWindow, ID_TIMER_EMBED, 1000, nullptr);
        InvalidateRect(gWindow, nullptr, FALSE);
    } else if (result->action == ACT_INSTALL && ok) {
        if (!gPackage.empty()) {
            AppendLog(L"APK đã cài. Đang mở launcher activity…");
            Invoke(ACT_LAUNCH, L"launch --package " + Quote(gPackage));
        } else {
            AppendLog(L"Đã cài APK, nhưng chưa có package name để tự mở. Cài Android Build-Tools rồi chọn lại APK.");
        }
    } else if (result->action == ACT_LAUNCH && ok) {
        AppendLog(L"✓ Ứng dụng đang hiển thị trong Android canvas.");
    } else if (result->action == ACT_DEVICE && ok) {
        std::wstring model = JsonString(json, L"model");
        std::wstring android = JsonString(json, L"android");
        std::wstring api = JsonString(json, L"api");
        std::wstring battery = JsonString(json, L"battery");
        gDeviceState = (model.empty() ? L"Android online" : model + L" online") + (android.empty() ? L"" : L" · Android " + android + L" / API " + api);
        AppendLog(L"Thiết bị: " + gDeviceState + (battery.empty() ? L"" : L" · Pin " + battery));
        InvalidateRect(gWindow, nullptr, FALSE);
    } else if (result->action == ACT_UNINSTALL && ok) {
        AppendLog(L"Ứng dụng đã được gỡ khỏi AVD.");
    } else if (result->action == ACT_STOP) {
        if (gEmulatorWindow && IsWindow(gEmulatorWindow)) SetParent(gEmulatorWindow, nullptr);
        gEmulatorWindow = nullptr; gEmulatorPid = 0;
        gCanvasState = L"Máy ảo đã nhận lệnh dừng";
        gDeviceState = L"Thiết bị Android chưa online";
        KillTimer(gWindow, ID_TIMER_EMBED); InvalidateRect(gWindow, nullptr, FALSE);
    }
    delete result;
}

LRESULT CALLBACK WindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_CREATE: {
        gFont = CreateFontW(-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI Variable Text");
        gFontTitle = CreateFontW(-27, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI Variable Display");
        gFontHero = CreateFontW(-36, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI Variable Display");
        gFontMono = CreateFontW(-14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, FIXED_PITCH, L"Cascadia Mono");
        gButtons[ID_PICK - ID_PICK] = AddButton(hwnd, ID_PICK, L"CHỌN APK  ⌘");
        gButtons[ID_DIAG - ID_PICK] = AddButton(hwnd, ID_DIAG, L"KIỂM TRA HỆ THỐNG");
        gButtons[ID_CREATE - ID_PICK] = AddButton(hwnd, ID_CREATE, L"TẠO ANDROID ẢO");
        gButtons[ID_START - ID_PICK] = AddButton(hwnd, ID_START, L"MỞ");
        gButtons[ID_STOP - ID_PICK] = AddButton(hwnd, ID_STOP, L"DỪNG");
        gButtons[ID_INSTALL - ID_PICK] = AddButton(hwnd, ID_INSTALL, L"CÀI & CHẠY APK");
        gButtons[ID_DEVICE - ID_PICK] = AddButton(hwnd, ID_DEVICE, L"THÔNG TIN THIẾT BỊ");
        gButtons[ID_LOGCAT - ID_PICK] = AddButton(hwnd, ID_LOGCAT, L"XEM LOGCAT GẦN NHẤT");
        gButtons[ID_UNINSTALL - ID_PICK] = AddButton(hwnd, ID_UNINSTALL, L"GỠ APK ĐANG CHỌN");
        gButtons[ID_ACCEL - ID_PICK] = AddButton(hwnd, ID_ACCEL, L"CHUẨN BỊ WINDOWS");
        gButtons[ID_CLEAR_LOG - ID_PICK] = AddButton(hwnd, ID_CLEAR_LOG, L"XÓA NHẬT KÝ");
        gCanvas = CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | SS_BLACKRECT, 0, 0, 1, 1, hwnd, nullptr, GetModuleHandleW(nullptr), nullptr);
        gLog = CreateWindowExW(0, L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
            0, 0, 1, 1, hwnd, nullptr, GetModuleHandleW(nullptr), nullptr);
        SendMessageW(gLog, WM_SETFONT, (WPARAM)gFontMono, TRUE);
        DragAcceptFiles(hwnd, TRUE);
        RegisterHotKey(hwnd, 1, MOD_CONTROL, 'O');
        RegisterHotKey(hwnd, 2, MOD_CONTROL, VK_RETURN);
        RegisterHotKey(hwnd, 3, MOD_CONTROL, 'L');
        int dark = 1, corners = 2, backdrop = 2;
        DwmSetWindowAttribute(hwnd, 20, &dark, sizeof(dark));
        DwmSetWindowAttribute(hwnd, 33, &corners, sizeof(corners));
        DwmSetWindowAttribute(hwnd, 38, &backdrop, sizeof(backdrop));
        AppendLog(L"AstraDroid khởi tạo. Kiểm tra VT, Android SDK và device bridge…");
        Invoke(ACT_STATUS, L"status");
        return 0;
    }
    case WM_GETMINMAXINFO: {
        auto* info = reinterpret_cast<MINMAXINFO*>(lParam);
        info->ptMinTrackSize.x = 1120; info->ptMinTrackSize.y = 760;
        return 0;
    }
    case WM_SIZE: Layout(hwnd); InvalidateRect(hwnd, nullptr, FALSE); return 0;
    case WM_TIMER: if (wParam == ID_TIMER_EMBED) AttemptEmbed(); return 0;
    case WM_DROPFILES: {
        HDROP drop = reinterpret_cast<HDROP>(wParam);
        wchar_t path[MAX_PATH * 4]{};
        if (DragQueryFileW(drop, 0, path, (UINT)std::size(path))) SelectApk(path);
        DragFinish(drop); gDropActive = false; InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }
    case WM_HOTKEY:
        if (wParam == 1) PickApk(hwnd);
        else if (wParam == 2) {
            if (gApk.empty()) PickApk(hwnd);
            else Invoke(ACT_INSTALL, L"install --apk " + Quote(gApk) + (gPackage.empty() ? L"" : L" --package " + Quote(gPackage)));
        } else if (wParam == 3) Invoke(ACT_LOGCAT, L"logcat --lines 350");
        return 0;
    case WM_ENGINE_RESULT: ReceiveResult(reinterpret_cast<EngineResult*>(lParam)); return 0;
    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case ID_PICK: PickApk(hwnd); break;
        case ID_DIAG: Invoke(ACT_STATUS, L"status"); break;
        case ID_CREATE:
            if (MessageBoxW(hwnd, L"Lần đầu sẽ tải Android Emulator và system image từ Google (dung lượng lớn) và xác nhận Android SDK licenses. Bạn đồng ý tiếp tục?", L"Tạo Android ảo", MB_ICONQUESTION | MB_OKCANCEL) == IDOK)
                Invoke(ACT_CREATE, L"create-avd --avd AstraDroid_Pixel --download");
            break;
        case ID_START: Invoke(ACT_START, L"start --avd AstraDroid_Pixel"); break;
        case ID_INSTALL:
            if (gApk.empty()) MessageBoxW(hwnd, L"Hãy chọn một APK trước.", L"AstraDroid", MB_ICONINFORMATION);
            else Invoke(ACT_INSTALL, L"install --apk " + Quote(gApk) + (gPackage.empty() ? L"" : L" --package " + Quote(gPackage)));
            break;
        case ID_STOP: Invoke(ACT_STOP, L"stop"); break;
        case ID_DEVICE: Invoke(ACT_DEVICE, L"device-info"); break;
        case ID_LOGCAT: Invoke(ACT_LOGCAT, L"logcat --lines 350"); break;
        case ID_UNINSTALL:
            if (gPackage.empty()) MessageBoxW(hwnd, L"Hãy kiểm tra APK để lấy package name trước khi gỡ.", L"AstraDroid", MB_ICONINFORMATION);
            else if (MessageBoxW(hwnd, (L"Gỡ package '" + gPackage + L"' khỏi Android Emulator? Thao tác này không xóa APK trên Windows.").c_str(), L"Xác nhận gỡ APK", MB_ICONWARNING | MB_OKCANCEL) == IDOK)
                Invoke(ACT_UNINSTALL, L"uninstall --package " + Quote(gPackage));
            break;
        case ID_CLEAR_LOG: SetWindowTextW(gLog, L""); AppendLog(L"Nhật ký đã được xóa."); break;
        case ID_ACCEL:
            if (MessageBoxW(hwnd, L"Lệnh này yêu cầu Administrator, bật Windows Hypervisor Platform / Virtual Machine Platform và yêu cầu khởi động lại. Nó KHÔNG thể bật VT-x/AMD-V trong BIOS. Tiếp tục?", L"Chuẩn bị tăng tốc", MB_ICONWARNING | MB_OKCANCEL) == IDOK) {
                std::wstring script = gRoot + L"\\scripts\\Enable-Windows-Acceleration.ps1";
                ShellExecuteW(hwnd, L"runas", L"powershell.exe", (L"-NoProfile -ExecutionPolicy Bypass -File " + Quote(script) + L" -Apply").c_str(), gRoot.c_str(), SW_SHOWNORMAL);
            }
            break;
        }
        return 0;
    case WM_DRAWITEM: {
        auto* d = reinterpret_cast<DRAWITEMSTRUCT*>(lParam);
        if (d->CtlType != ODT_BUTTON) break;
        bool disabled = (d->itemState & ODS_DISABLED) != 0;
        bool pressed = (d->itemState & ODS_SELECTED) != 0;
        bool focused = (d->itemState & ODS_FOCUS) != 0;
        COLORREF base = C_PANEL_2;
        if (d->CtlID == ID_PICK || d->CtlID == ID_INSTALL) base = C_ACCENT;
        else if (d->CtlID == ID_CREATE) base = C_PURPLE;
        else if (d->CtlID == ID_START || d->CtlID == ID_DEVICE) base = C_GOOD;
        else if (d->CtlID == ID_STOP || d->CtlID == ID_UNINSTALL) base = C_DANGER;
        else if (d->CtlID == ID_ACCEL) base = C_WARN;
        if (disabled) base = RGB(61, 69, 89);
        if (pressed) base = RGB(std::max(0, GetRValue(base) - 25), std::max(0, GetGValue(base) - 25), std::max(0, GetBValue(base) - 25));
        RECT r = d->rcItem; Rounded(d->hDC, r, base, 11);
        if (focused) { HPEN pen = CreatePen(PS_SOLID, 2, RGB(210, 222, 255)); HGDIOBJ old = SelectObject(d->hDC, pen); HGDIOBJ b = SelectObject(d->hDC, GetStockObject(HOLLOW_BRUSH)); RoundRect(d->hDC, r.left + 1, r.top + 1, r.right - 1, r.bottom - 1, 10, 10); SelectObject(d->hDC, b); SelectObject(d->hDC, old); DeleteObject(pen); }
        wchar_t label[80]{}; GetWindowTextW(d->hwndItem, label, 80);
        COLORREF textColor = (d->CtlID == ID_ACCEL && !disabled) ? RGB(35, 30, 20) : RGB(255, 255, 255);
        Text(d->hDC, label, r, gFont, textColor, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS);
        return TRUE;
    }
    case WM_CTLCOLORSTATIC:
        if ((HWND)lParam == gCanvas) { SetBkColor((HDC)wParam, C_CANVAS); static HBRUSH canvas = CreateSolidBrush(C_CANVAS); return (LRESULT)canvas; }
        break;
    case WM_CTLCOLOREDIT:
        if ((HWND)lParam == gLog) { SetTextColor((HDC)wParam, RGB(205, 219, 237)); SetBkColor((HDC)wParam, C_CANVAS); static HBRUSH h = CreateSolidBrush(C_CANVAS); return (LRESULT)h; }
        break;
    case WM_PAINT: {
        PAINTSTRUCT ps{}; HDC hdc = BeginPaint(hwnd, &ps); RECT client{}; GetClientRect(hwnd, &client); DrawDashboard(hdc, client); EndPaint(hwnd, &ps); return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_DESTROY:
        KillTimer(hwnd, ID_TIMER_EMBED); DragAcceptFiles(hwnd, FALSE);
        UnregisterHotKey(hwnd, 1); UnregisterHotKey(hwnd, 2); UnregisterHotKey(hwnd, 3);
        if (gFont) DeleteObject(gFont); if (gFontTitle) DeleteObject(gFontTitle); if (gFontHero) DeleteObject(gFontHero); if (gFontMono) DeleteObject(gFontMono);
        PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, message, wParam, lParam);
}

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int show) {
    wchar_t module[MAX_PATH]{}; GetModuleFileNameW(nullptr, module, MAX_PATH);
    std::filesystem::path executable(module);
    gRoot = executable.parent_path().parent_path().wstring(); // bin\AstraDroid.exe → project root
    if (!std::filesystem::exists(gRoot + L"\\python\\engine.py")) gRoot = std::filesystem::current_path().wstring();
    SetCurrentDirectoryW(gRoot.c_str());

    WNDCLASSEXW wc{}; wc.cbSize = sizeof(wc); wc.hInstance = instance; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.lpfnWndProc = WindowProc; wc.lpszClassName = L"AstraDroidNativeHost"; wc.hIcon = LoadIcon(nullptr, IDI_APPLICATION);
    RegisterClassExW(&wc);
    gWindow = CreateWindowExW(0, wc.lpszClassName, L"AstraDroid · Windows APK Workspace", WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN,
        CW_USEDEFAULT, CW_USEDEFAULT, 1280, 800, nullptr, nullptr, instance, nullptr);
    ShowWindow(gWindow, show); UpdateWindow(gWindow);
    MSG msg{}; while (GetMessageW(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    return (int)msg.wParam;
}
