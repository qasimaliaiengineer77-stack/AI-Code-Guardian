Set WshShell = CreateObject("WScript.Shell")
' 1. Run installation silently in background
WshShell.Run """E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\venv\Scripts\python.exe"" -m pip install -r ""E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\requirements.txt"" -q", 0, True
WshShell.Run """E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\venv\Scripts\python.exe"" -m pip install psutil -q", 0, True

' 2. Create Desktop Shortcut
Dim Desktop
Desktop = WshShell.SpecialFolders("Desktop")
Set oLink = WshShell.CreateShortcut(Desktop & "\CodeGuardian.AI.lnk")
oLink.TargetPath = "E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\venv\Scripts\pythonw.exe"
oLink.Arguments = """E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\app_launcher.py"""
oLink.WorkingDirectory = "E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian"
oLink.IconLocation = "E:\computer\Docements\fmaily.doc\AI_Project\AI_Code_Guardian\app.ico,0"
oLink.Save

' 3. Show Success Message
MsgBox "Installation Successful! App icon has been added to your Desktop.", 64, "CodeGuardian.AI Setup"