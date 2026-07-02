Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
python = "python.exe"
defaultPath = "C:\Users\Gstar\AppData\Local\Programs\Python\Python312\python.exe"
If fso.FileExists(defaultPath) Then
    python = defaultPath
End If
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & python & """ """ & scriptDir & "\run_candidatures.py""", 1, True
dashboard = scriptDir & "\_logs\tableau_de_bord.md"
If fso.FileExists(dashboard) Then
    WshShell.Run "notepad """ & dashboard & """", 1, False
End If