# snap-path.exe의 시작 프로그램 바로가기 생성 스크립트
# 사용법: powershell -ExecutionPolicy Bypass -File create_shortcut.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ExePath = Join-Path $ScriptDir "dist\snap-path.exe"

if (-not (Test-Path $ExePath)) {
    Write-Host "ERROR: snap-path.exe not found at $ExePath" -ForegroundColor Red
    Write-Host "Run 'pyinstaller --onefile --noconsole --name snap-path snap_path.pyw' first."
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\snap-path.lnk"
$Shortcut = $WshShell.CreateShortcut($StartupPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "snap-path screen capture"
$Shortcut.Save()
Write-Host "Startup shortcut created: $StartupPath"
Write-Host "Target: $ExePath"
