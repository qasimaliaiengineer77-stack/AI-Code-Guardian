$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

# Shortcuts delete karo
Remove-Item "$Desktop\CodeGuardian.AI.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$StartMenu\CodeGuardian.AI.lnk" -Force -ErrorAction SilentlyContinue

Write-Host "=========================================" -ForegroundColor Red
Write-Host "   UNINSTALLATION SUCCESSFUL!" -ForegroundColor Red
Write-Host "   Shortcuts have been removed." -ForegroundColor Red
Write-Host "=========================================" -ForegroundColor Red