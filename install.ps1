$proj = "C:\Projects\AI-Code-Guardian"
$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

# Hidden Launcher (VBS) taake black window na khule
$vbs = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$proj\start_guardian.bat""", 0, False
"@
[IO.File]::WriteAllText("$proj\launch_hidden.vbs", $vbs)

# Desktop aur Start Menu par Shortcut banao
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Desktop\CodeGuardian.AI.lnk")
$Shortcut.TargetPath = "$proj\launch_hidden.vbs"
$Shortcut.WorkingDirectory = $proj
$Shortcut.IconLocation = "$proj\app.ico,0"
$Shortcut.Save()

$SMShortcut = $WshShell.CreateShortcut("$StartMenu\CodeGuardian.AI.lnk")
$SMShortcut.TargetPath = "$proj\launch_hidden.vbs"
$SMShortcut.WorkingDirectory = $proj
$SMShortcut.IconLocation = "$proj\app.ico,0"
$SMShortcut.Save()

Write-Host "=========================================" -ForegroundColor Green
Write-Host "   INSTALLATION SUCCESSFUL! (CodeGuardian.AI)" -ForegroundColor Green
Write-Host "   Check your Desktop for the App Icon." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green