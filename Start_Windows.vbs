Option Explicit
Dim shell, files, folder, entry, command, candidates, launched
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
entry = Chr(34) & files.BuildPath(folder, "Open_SPARKLE_CODER.pyw") & Chr(34)
shell.CurrentDirectory = folder
candidates = Array("pyw.exe -3 ", "pythonw.exe ", "py.exe -3 ", "python.exe ")
launched = False
For Each command In candidates
    On Error Resume Next
    Err.Clear
    shell.Run command & entry, 0, False
    If Err.Number = 0 Then launched = True
    On Error GoTo 0
    If launched Then Exit For
Next
If Not launched Then
    MsgBox "Install Python 3.11 or newer, then double-click Start_Windows.vbs again." & vbCrLf & vbCrLf & "If Windows blocks VBScript, open Open_SPARKLE_CODER.pyw using Python instead.", vbInformation, "SPARKLE CODER"
    shell.Run Chr(34) & files.BuildPath(folder, "OPEN_FIRST.html") & Chr(34), 1, False
End If
