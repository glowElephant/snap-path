$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\snap-path.lnk"
$Shortcut = $WshShell.CreateShortcut($StartupPath)
$Shortcut.TargetPath = "C:\Users\SmartPro\AppData\Local\Programs\Python\Launcher\pyw.exe"
$Shortcut.Arguments = "C:\Git\snap-path\snap_path.pyw"
$Shortcut.WorkingDirectory = "C:\Git\snap-path"
$Shortcut.Description = "snap-path screen capture"
$Shortcut.Save()
Write-Host "Startup shortcut created: $StartupPath"
