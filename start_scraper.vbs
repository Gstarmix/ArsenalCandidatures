Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
python = "python.exe"
defaultPath = "C:\Users\Gstar\AppData\Local\Programs\Python\Python312\python.exe"
If fso.FileExists(defaultPath) Then
    python = defaultPath
End If
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & python & """ """ & scriptDir & "\run_candidatures.py"" --scraper", 1, True
liste = scriptDir & "\_logs\offres_francetravail.md"
If fso.FileExists(liste) Then
    WshShell.Run "notepad """ & liste & """", 1, False
End If