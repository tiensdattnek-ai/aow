#!/usr/bin/env python3
"""AstraDroid local Android Emulator control plane.

This module deliberately uses only the Python standard library.  It does not
ship or download Android binaries; it orchestrates a locally installed Android
SDK after the owner has accepted its licences.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

APP_ROOT = Path(__file__).resolve().parents[1]
APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(APP_ROOT / ".data"))) / "AstraDroid"
STATE_FILE = APP_DATA / "session.json"
DEFAULT_AVD = "AstraDroid_Pixel"


def emit(payload: dict[str, Any], code: int = 0) -> None:
    """Emit a single machine-readable response for the native host."""
    payload.setdefault("ok", code == 0)
    payload.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(code)


def compact(text: str, maximum: int = 7000) -> str:
    text = text.strip()
    return text if len(text) <= maximum else text[-maximum:] + "\n[output truncated]"


def run(argv: list[str], timeout: int = 45, stdin: Optional[str] = None, maximum: int = 7000) -> dict[str, Any]:
    """Run an SDK command without shell interpolation.

    ``maximum`` only limits returned diagnostic text; a larger value is used for
    SDK package discovery, where truncating the list would hide valid images.
    """
    try:
        complete = subprocess.run(
            argv,
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {"code": complete.returncode, "output": compact(complete.stdout, maximum)}
    except FileNotFoundError:
        return {"code": 127, "output": f"Executable not found: {argv[0]}"}
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return {"code": 124, "output": compact(str(out) + "\nTimed out.", maximum)}
    except OSError as exc:
        return {"code": 126, "output": str(exc)}


def powershell(script: str, timeout: int = 20) -> str:
    exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not exe:
        return ""
    response = run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)
    return response["output"] if response["code"] == 0 else ""


def candidate_sdks() -> Iterable[Path]:
    for value in (os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME")):
        if value:
            yield Path(value)
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", ""))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", ""))
    for path in (
        local / "Android" / "Sdk",
        Path.home() / "AppData" / "Local" / "Android" / "Sdk",
        program_files / "Android" / "Android Studio" / "sdk",
        program_files_x86 / "Android" / "Android Studio" / "sdk",
    ):
        yield path


def sdk_root() -> Optional[Path]:
    for root in candidate_sdks():
        if root and (root / "platform-tools").exists():
            return root
    return None


def sdk_tool(root: Optional[Path], name: str) -> Optional[Path]:
    if not root:
        return None
    suffix = ".exe" if name in {"adb", "emulator", "aapt", "apksigner"} else ".bat"
    fixed = {
        "adb": [root / "platform-tools" / "adb.exe"],
        "emulator": [root / "emulator" / "emulator.exe"],
        "sdkmanager": [
            root / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat",
            root / "tools" / "bin" / "sdkmanager.bat",
        ],
        "avdmanager": [
            root / "cmdline-tools" / "latest" / "bin" / "avdmanager.bat",
            root / "tools" / "bin" / "avdmanager.bat",
        ],
    }
    for path in fixed.get(name, []):
        if path.exists():
            return path
    # New build-tools versions are not known in advance.  Use the highest one.
    if name in {"aapt", "apksigner"}:
        choices = sorted((root / "build-tools").glob("*/" + name + ".exe"), key=lambda p: p.parent.name, reverse=True)
        return choices[0] if choices else None
    return None


def tools() -> dict[str, Optional[Path]]:
    root = sdk_root()
    return {"sdk": root, **{name: sdk_tool(root, name) for name in ("adb", "emulator", "sdkmanager", "avdmanager", "aapt", "apksigner")}}


def firmware_virtualization() -> dict[str, Any]:
    if os.name != "nt":
        return {"supported": False, "firmware_enabled": False, "message": "AstraDroid requires Windows 10/11 x64."}
    raw = powershell("$p=Get-CimInstance Win32_Processor | Select-Object -First 1; [pscustomobject]@{vm=$p.VMMonitorModeExtensions;fw=$p.VirtualizationFirmwareEnabled;slat=$p.SecondLevelAddressTranslationExtensions}|ConvertTo-Json -Compress")
    try:
        info = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        info = {}
    hypervisor = powershell("(Get-CimInstance Win32_ComputerSystem).HypervisorPresent")
    bcd = powershell("(bcdedit /enum '{current}' | Select-String 'hypervisorlaunchtype').ToString()")
    return {
        "supported": bool(info.get("vm")),
        "firmware_enabled": bool(info.get("fw")),
        "slat": bool(info.get("slat")),
        "hypervisor_present": hypervisor.strip().lower() == "true",
        "hypervisor_launch": "auto" in bcd.lower(),
        "message": "Sẵn sàng" if info.get("fw") else "VT-x / AMD-V chưa được Windows nhận diện",
    }


def windows_features() -> dict[str, str]:
    if os.name != "nt":
        return {}
    names = ["Microsoft-Hyper-V-All", "HypervisorPlatform", "VirtualMachinePlatform"]
    result = {}
    for name in names:
        out = powershell(f"(Get-WindowsOptionalFeature -Online -FeatureName {name}).State")
        result[name] = out.strip() or "Unknown"
    return result


def list_avds(root: Optional[Path] = None) -> list[str]:
    emulator = sdk_tool(root or sdk_root(), "emulator")
    if not emulator:
        return []
    completed = run([str(emulator), "-list-avds"])
    if completed["code"] != 0:
        return []
    return [line.strip() for line in completed["output"].splitlines() if line.strip()]


def adb_ready(toolset: dict[str, Optional[Path]], timeout: int = 100) -> tuple[bool, str]:
    adb = toolset["adb"]
    if not adb:
        return False, "Không tìm thấy adb.exe"
    run([str(adb), "start-server"], timeout=20)
    deadline = time.time() + timeout
    latest = ""
    while time.time() < deadline:
        current = run([str(adb), "devices"], timeout=12)
        latest = current["output"]
        for line in latest.splitlines():
            if "\tdevice" in line and not line.startswith("List of"):
                return True, line.split("\t", 1)[0]
        time.sleep(2)
    return False, compact(latest)


def available_sdk_packages(root: Path) -> str:
    """Return the complete SDK package listing; it can be much larger than logs."""
    manager = sdk_tool(root, "sdkmanager")
    if not manager:
        return ""
    listing = run([str(manager), "--sdk_root=" + str(root), "--list"], timeout=120, maximum=800_000)
    return listing["output"] if listing["code"] == 0 else ""


def android_image(root: Path, listing: Optional[str] = None) -> Optional[str]:
    listing = listing if listing is not None else available_sdk_packages(root)
    # Prefer Google APIs x86_64. Choose the largest API number actually exposed
    # by the installed command-line tools; no hard-coded stale Android release.
    images = re.findall(r"(system-images;android-(\d+);google_apis(?:_playstore)?;x86_64)", listing)
    if not images:
        images = re.findall(r"(system-images;android-(\d+);default;x86_64)", listing)
    if not images:
        return None
    return max(images, key=lambda pair: int(pair[1]))[0]


def latest_build_tools(listing: str) -> Optional[str]:
    versions = re.findall(r"(build-tools;(\d+(?:\.\d+)+))", listing)
    if not versions:
        return None
    def version_key(entry: tuple[str, str]) -> tuple[int, ...]:
        return tuple(int(part) for part in entry[1].split("."))
    return max(versions, key=version_key)[0]


def inspect_apk(path: Path, toolset: dict[str, Optional[Path]]) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ValueError("Tệp APK không tồn tại.")
    if path.suffix.lower() not in {".apk", ".apks", ".xapk"}:
        raise ValueError("Chỉ hỗ trợ tệp .apk trực tiếp. APKS/XAPK cần được giải nén trước.")
    digest = hashlib.sha256()
    with path.open("rb") as package:
        while block := package.read(1024 * 1024):
            digest.update(block)
    result: dict[str, Any] = {
        "file": str(path), "name": path.name, "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(), "package": None, "label": None,
        "version_name": None, "version_code": None, "min_sdk": None,
        "signing": "Không kiểm tra (thiếu apksigner)",
    }
    aapt = toolset.get("aapt")
    if aapt and path.suffix.lower() == ".apk":
        details = run([str(aapt), "dump", "badging", str(path)], timeout=30)
        if details["code"] == 0:
            package_line = next((line for line in details["output"].splitlines() if line.startswith("package:")), "")
            app_line = next((line for line in details["output"].splitlines() if line.startswith("application-label:")), "")
            sdk_line = next((line for line in details["output"].splitlines() if line.startswith("sdkVersion:")), "")
            for field, pattern in (("package", r"name='([^']+)'"), ("version_code", r"versionCode='([^']+)'"), ("version_name", r"versionName='([^']+)'") ):
                hit = re.search(pattern, package_line)
                if hit:
                    result[field] = hit.group(1)
            label = re.search(r"application-label:'([^']*)'", app_line)
            sdk = re.search(r"sdkVersion:'([^']+)'", sdk_line)
            result["label"] = label.group(1) if label else result["label"]
            result["min_sdk"] = sdk.group(1) if sdk else result["min_sdk"]
    signer = toolset.get("apksigner")
    if signer and path.suffix.lower() == ".apk":
        verified = run([str(signer), "verify", "--print-certs", str(path)], timeout=40)
        if verified["code"] == 0:
            cert = re.search(r"certificate SHA-256 digest:\s*([0-9a-fA-F:]+)", verified["output"])
            result["signing"] = "Đã xác minh" + (" · " + cert.group(1) if cert else "")
        else:
            result["signing"] = "Chữ ký không hợp lệ hoặc không thể xác minh"
    return result


def install_apk(apk: Path, package: Optional[str]) -> dict[str, Any]:
    toolset = tools()
    ready, device = adb_ready(toolset, 100)
    if not ready:
        return {"ok": False, "stage": "device", "message": "Thiết bị ảo chưa sẵn sàng: " + device}
    response = run([str(toolset["adb"]), "-s", device, "install", "-r", "-g", str(apk)], timeout=240)
    return {"ok": response["code"] == 0 and "Success" in response["output"], "stage": "install", "device": device, "package": package, "output": response["output"]}


def launch_package(package: str) -> dict[str, Any]:
    toolset = tools()
    ready, device = adb_ready(toolset, 30)
    if not ready:
        return {"ok": False, "stage": "device", "message": "Thiết bị ảo chưa sẵn sàng: " + device}
    # cmd package resolve-activity supports launcher aliases and does not guess
    # the app's main Activity.
    resolve = run([str(toolset["adb"]), "-s", device, "shell", "cmd", "package", "resolve-activity", "--brief", package], timeout=30)
    component = next((line.strip() for line in resolve["output"].splitlines() if "/" in line), "")
    if not component:
        return {"ok": False, "stage": "resolve", "message": f"Không tìm thấy launcher activity cho {package}.", "output": resolve["output"]}
    started = run([str(toolset["adb"]), "-s", device, "shell", "am", "start", "-n", component], timeout=30)
    return {"ok": started["code"] == 0, "stage": "launch", "component": component, "output": started["output"]}


def save_session(data: dict[str, Any]) -> None:
    APP_DATA.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def command_status(_: argparse.Namespace) -> None:
    ts = tools()
    root = ts["sdk"]
    vt = firmware_virtualization()
    status = {
        "windows": platform.platform(), "architecture": platform.machine(),
        "virtualization": vt, "features": windows_features(),
        "sdk_root": str(root) if root else None,
        "sdk_ready": bool(root and ts["adb"] and ts["emulator"]),
        "tools": {name: str(path) if path else None for name, path in ts.items() if name != "sdk"},
        "avds": list_avds(root),
        "blocking_reason": None,
    }
    if not vt.get("supported"):
        status["blocking_reason"] = "CPU/Windows không báo hỗ trợ ảo hóa phần cứng."
    elif not vt.get("firmware_enabled"):
        status["blocking_reason"] = "Bật Intel VT-x hoặc AMD SVM trong UEFI/BIOS, sau đó khởi động lại."
    elif not status["sdk_ready"]:
        status["blocking_reason"] = "Chưa tìm thấy Android SDK Emulator. Chạy SETUP_WINDOWS.bat hoặc cài Android Studio."
    emit(status)


def command_inspect(args: argparse.Namespace) -> None:
    try:
        result = inspect_apk(Path(args.apk).expanduser().resolve(), tools())
        emit(result)
    except (ValueError, OSError) as exc:
        emit({"message": str(exc)}, 2)


def command_create_avd(args: argparse.Namespace) -> None:
    ts = tools()
    root = ts["sdk"]
    vt = firmware_virtualization()
    if not root or not ts["sdkmanager"] or not ts["avdmanager"]:
        emit({"message": "Thiếu Android SDK Command-line Tools. Cài Android Studio rồi mở SDK Manager."}, 2)
    if not vt.get("firmware_enabled"):
        emit({"message": "Không tạo máy ảo: " + vt["message"]}, 2)
    listing = available_sdk_packages(root)
    image = args.image if args.image != "auto" else android_image(root, listing)
    if not image:
        emit({"message": "Không tìm được system image x86_64 từ sdkmanager. Hãy cài một Google APIs system image trong Android Studio."}, 2)
    # The same first-run action provisions the inspection toolchain when the
    # current SDK exposes it, rather than leaving a newly created AVD unable to
    # report APK package/certificate metadata.
    packages = ["platform-tools", "emulator", image]
    api = re.search(r"system-images;android-(\d+);", image)
    if api:
        packages.append("platforms;android-" + api.group(1))
    build_tools = latest_build_tools(listing)
    if build_tools:
        packages.append(build_tools)
    if args.download:
        licences = run([str(ts["sdkmanager"]), "--sdk_root=" + str(root), "--licenses"], timeout=300, stdin="y\n" * 200)
        if licences["code"] != 0:
            emit({"message": "Không thể xác nhận Android SDK licenses.", "output": licences["output"]}, 2)
        downloaded = run([str(ts["sdkmanager"]), "--sdk_root=" + str(root), "--install", *packages], timeout=1800, stdin="y\n" * 200)
        if downloaded["code"] != 0:
            emit({"message": "Tải Android system image không thành công.", "output": downloaded["output"]}, 2)
    existing = list_avds(root)
    if args.avd not in existing:
        create = run([str(ts["avdmanager"]), "create", "avd", "--force", "--name", args.avd, "--package", image, "--device", args.device], timeout=180, stdin="no\n")
        if create["code"] != 0:
            emit({"message": "Tạo AVD không thành công.", "image": image, "output": create["output"]}, 2)
    emit({"message": "AVD đã sẵn sàng.", "avd": args.avd, "image": image, "avds": list_avds(root)})


def command_start(args: argparse.Namespace) -> None:
    ts = tools()
    vt = firmware_virtualization()
    emulator = ts["emulator"]
    if not emulator:
        emit({"message": "Không tìm thấy Android Emulator."}, 2)
    if not vt.get("firmware_enabled"):
        emit({"message": "Không thể khởi động: " + vt["message"]}, 2)
    if args.avd not in list_avds(ts["sdk"]):
        emit({"message": f"Không tìm thấy AVD '{args.avd}'. Hãy tạo AVD trước."}, 2)
    command = [str(emulator), "-avd", args.avd, "-gpu", "host", "-no-snapshot-save", "-no-boot-anim"]
    # -no-window deliberately is not used: AstraDroid embeds the normal emulator
    # window in its native host when Windows/Qt allows it.
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    except OSError as exc:
        emit({"message": f"Không thể mở emulator: {exc}"}, 2)
    save_session({"emulator_pid": proc.pid, "avd": args.avd, "started": time.time()})
    emit({"message": "Đang khởi động Android Emulator. Lần đầu có thể mất vài phút.", "pid": proc.pid, "avd": args.avd})


def command_stop(_: argparse.Namespace) -> None:
    ts = tools()
    if not ts["adb"]:
        emit({"message": "Không tìm thấy adb."}, 2)
    response = run([str(ts["adb"]), "emu", "kill"], timeout=20)
    emit({"message": "Đã gửi lệnh dừng máy ảo.", "output": response["output"]}, 0 if response["code"] == 0 else 2)


def command_install(args: argparse.Namespace) -> None:
    apk = Path(args.apk).expanduser().resolve()
    if not apk.exists():
        emit({"message": "Không tìm thấy APK."}, 2)
    result = install_apk(apk, args.package)
    emit(result, 0 if result.get("ok") else 2)


def command_launch(args: argparse.Namespace) -> None:
    result = launch_package(args.package)
    emit(result, 0 if result.get("ok") else 2)


def safe_package_name(package: str) -> bool:
    # Package identifiers come from aapt in the UI, but validate again at the
    # trust boundary before passing one to adb.
    return bool(re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package))


def command_uninstall(args: argparse.Namespace) -> None:
    if not safe_package_name(args.package):
        emit({"message": "Package name không hợp lệ."}, 2)
    ts = tools()
    ready, device = adb_ready(ts, 30)
    if not ready:
        emit({"message": "Thiết bị ảo chưa sẵn sàng: " + device}, 2)
    response = run([str(ts["adb"]), "-s", device, "uninstall", args.package], timeout=60)
    ok = response["code"] == 0 and "Success" in response["output"]
    emit({"message": "Đã gỡ ứng dụng khỏi Android." if ok else "Không thể gỡ ứng dụng.", "package": args.package, "output": response["output"]}, 0 if ok else 2)


def command_device_info(_: argparse.Namespace) -> None:
    ts = tools()
    ready, device = adb_ready(ts, 30)
    if not ready:
        emit({"message": "Thiết bị ảo chưa sẵn sàng: " + device}, 2)
    adb = str(ts["adb"])
    def prop(name: str) -> str:
        return run([adb, "-s", device, "shell", "getprop", name], timeout=15)["output"].strip()
    battery = run([adb, "-s", device, "shell", "dumpsys", "battery"], timeout=20)["output"]
    level = re.search(r"level:\s*(\d+)", battery)
    emit({
        "message": "Thiết bị Android đang online.", "device": device,
        "model": prop("ro.product.model") or "Android Emulator",
        "android": prop("ro.build.version.release") or "?",
        "api": prop("ro.build.version.sdk") or "?",
        "battery": level.group(1) + "%" if level else "?",
    })


def command_logcat(args: argparse.Namespace) -> None:
    ts = tools()
    ready, device = adb_ready(ts, 30)
    if not ready:
        emit({"message": "Thiết bị ảo chưa sẵn sàng: " + device}, 2)
    # Dump-only, bounded log view: no continuously running child process is
    # left behind when a user closes AstraDroid.
    response = run([str(ts["adb"]), "-s", device, "logcat", "-d", "-t", str(args.lines), "-v", "threadtime"], timeout=45, maximum=18_000)
    emit({"message": "Đã lấy logcat gần nhất.", "device": device, "output": response["output"]}, 0 if response["code"] == 0 else 2)


def command_prepare(_: argparse.Namespace) -> None:
    # Firmware VT/SVM can ONLY be enabled by the owner in UEFI/BIOS.  We never
    # pretend otherwise.  Windows optional features do require elevation/reboot.
    script = APP_ROOT / "scripts" / "Enable-Windows-Acceleration.ps1"
    emit({
        "message": "Cần Administrator và khởi động lại để bật Windows Hypervisor Platform.",
        "firmware_note": "Intel VT-x / AMD SVM phải được bật trong UEFI/BIOS, không thể bật bằng script.",
        "script": str(script),
        "run_as_admin": f'powershell -ExecutionPolicy Bypass -File "{script}" -Apply',
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AstraDroid SDK control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=command_status)
    inspect = sub.add_parser("inspect-apk"); inspect.add_argument("--apk", required=True); inspect.set_defaults(func=command_inspect)
    create = sub.add_parser("create-avd")
    create.add_argument("--avd", default=DEFAULT_AVD); create.add_argument("--image", default="auto")
    create.add_argument("--device", default="pixel_6"); create.add_argument("--download", action="store_true")
    create.set_defaults(func=command_create_avd)
    start = sub.add_parser("start"); start.add_argument("--avd", default=DEFAULT_AVD); start.set_defaults(func=command_start)
    sub.add_parser("stop").set_defaults(func=command_stop)
    install = sub.add_parser("install"); install.add_argument("--apk", required=True); install.add_argument("--package"); install.set_defaults(func=command_install)
    launch = sub.add_parser("launch"); launch.add_argument("--package", required=True); launch.set_defaults(func=command_launch)
    uninstall = sub.add_parser("uninstall"); uninstall.add_argument("--package", required=True); uninstall.set_defaults(func=command_uninstall)
    sub.add_parser("device-info").set_defaults(func=command_device_info)
    logcat = sub.add_parser("logcat"); logcat.add_argument("--lines", type=int, default=350, choices=range(50, 2001)); logcat.set_defaults(func=command_logcat)
    sub.add_parser("prepare-windows").set_defaults(func=command_prepare)
    return parser


def main() -> None:
    if os.name != "nt":
        emit({"message": "AstraDroid backend chỉ chạy trên Windows."}, 2)
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit({"message": "Đã hủy."}, 130)
    except Exception as exc:  # Native host receives a useful JSON error, not a traceback.
        emit({"message": f"Lỗi nội bộ: {exc.__class__.__name__}: {exc}"}, 1)
