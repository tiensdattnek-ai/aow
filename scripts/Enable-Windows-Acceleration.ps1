# AstraDroid Windows acceleration preparation
# This script deliberately cannot and does not try to alter UEFI/BIOS settings.
# Run as Administrator. It enables Windows optional features and asks for reboot.

[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$required = @(
    'HypervisorPlatform',
    'VirtualMachinePlatform',
    'Microsoft-Hyper-V-Hypervisor'
)

function Test-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host ''
Write-Host 'AstraDroid • Windows acceleration preparation' -ForegroundColor Cyan
Write-Host 'Firmware note: Intel VT-x / AMD SVM must be enabled by you in UEFI/BIOS.' -ForegroundColor Yellow

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Write-Host ("CPU virtualization extensions: {0}" -f $cpu.VMMonitorModeExtensions)
Write-Host ("Virtualization enabled in firmware: {0}" -f $cpu.VirtualizationFirmwareEnabled)

$report = foreach ($feature in $required) {
    try {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        [PSCustomObject]@{ Feature = $feature; State = $state; Available = $true }
    } catch {
        [PSCustomObject]@{ Feature = $feature; State = 'Not available in this Windows edition'; Available = $false }
    }
}
$report | Format-Table -AutoSize

if (-not $Apply) {
    Write-Host ''
    Write-Host 'No changes were made. To apply as Administrator:' -ForegroundColor Green
    Write-Host '  powershell -ExecutionPolicy Bypass -File .\Enable-Windows-Acceleration.ps1 -Apply'
    exit 0
}

if (-not (Test-Admin)) {
    throw 'Administrator rights are required. Re-open the script with Run as administrator.'
}

foreach ($item in $report | Where-Object { $_.Available -and $_.State -ne 'Enabled' }) {
    Write-Host ("Enabling {0}..." -f $item.Feature) -ForegroundColor Cyan
    Enable-WindowsOptionalFeature -Online -FeatureName $item.Feature -All -NoRestart | Out-Host
}

Write-Host 'Setting hypervisorlaunchtype to auto...' -ForegroundColor Cyan
& bcdedit /set hypervisorlaunchtype auto | Out-Host

Write-Host ''
Write-Host 'Windows acceleration features have been prepared.' -ForegroundColor Green
Write-Host 'Restart Windows before starting the Android Emulator.' -ForegroundColor Yellow
if (-not $cpu.VirtualizationFirmwareEnabled) {
    Write-Host 'IMPORTANT: Windows still does not see firmware virtualization. Reboot to UEFI/BIOS and enable Intel VT-x or AMD SVM.' -ForegroundColor Yellow
}
