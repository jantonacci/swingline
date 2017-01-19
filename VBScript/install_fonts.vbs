' Based on original post by KODIAC http://www.visualbasicscript.com/fb.ashx?m=72168
' Follow up post by AaronZirbes with improvements http://www.visualbasicscript.com/fb.ashx?m=92986
Option Explicit
Const FONTS = &H14&
Const ForAppending = 8
Dim fso
Dim objShell
Dim objFontFolder
Dim oShell
Dim objDictionary
Dim strSystemRootDir
Dim strFontDir
Dim strTempDir
Dim f1
Dim doExist
Dim dontExist
Dim yesToAll
Dim noProgressDialog
Dim noUIIfError

' Initialize Global Objects
Set objShell = CreateObject("Shell.Application")
Set objFontFolder = objShell.Namespace(FONTS)
set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set objDictionary = CreateObject("Scripting.Dictionary")

' Initialize Global Variables
strSystemRootDir = oShell.ExpandEnvironmentStrings("%systemroot%")
strFontDir = strSystemRootDir & "\fonts\"
strTempDir = fso.GetParentFolderName(Wscript.ScriptFullName)
objDictionary.CompareMode = vbTextCompare
noProgressDialog = 4
yesToAll = 16
noUIIfError = 1024

' Execute Main Sub-routine
Main

'===================================================================
Public Sub Main
'===================================================================
Dim pwd
Dim rootFontInstallFolder
Dim param
Set f1 = FSO.createTextFile(strTempDir & "\installed_fonts.txt", ForAppending)
pwd = fso.GetParentFolderName(Wscript.ScriptFullName)
' Default to the current folder
rootFontInstallFolder = pwd
If Wscript.Arguments.Count = 1 Then
    param = Wscript.Arguments(0)
    If fso.FolderExists(param) Then
        rootFontInstallFolder = param
    End If
End If
doExist = 0
dontExist = 0
CollectFonts
InstallFonts rootFontInstallFolder ' insert path here to font folder
wscript.echo doExist & " fonts already installed." & vbcrlf & dontExist & " new fonts installed."
End Sub

'===================================================================
Public Sub CollectFonts
'===================================================================
Dim fontFolderPath
Dim fontFolder
Dim fileName
Dim fileExtension
Dim filePath
Dim oFile
Dim firstFileName
Dim firstFilePath
Dim objItem
firstFilePath = objFontFolder.Items.Item(0).Path
firstFileName = objFontFolder.Items.Item(0).Name
fontFolderPath = Replace(firstFilePath, "\" & firstFileName, "")
Set fontFolder = fso.GetFolder(fontFolderPath)
For each oFile in fontFolder.Files
    filePath = oFile.Path
    fileName = LCase(oFile.Name)
    fileExtension = LCase(fso.GetExtensionName(filePath))
    If fileExtension = "ttf" or _
        fileExtension = "otf" or _
        fileExtension = "pfm" or _
        fileExtension = "fon" Then
        If Not objDictionary.Exists(fileName) Then
            objDictionary.Add fileName, fileName
        End If
    End If
Next
For each objItem in objDictionary
    f1.writeline objDictionary.Item(objItem)
Next
End Sub
'===================================================================
Public Sub InstallFonts(ByVal folder)
'===================================================================
Dim fontInstallFolder
Dim fileExtension
Dim fileName
Dim file
Dim subFolder
Set fontInstallFolder = fso.getFolder(folder)
For Each file in fontInstallFolder.Files
    fileExtension = LCase(fso.GetExtensionName(file))
    fileName = LCase(fso.GetFileName(file))
    If fileExtension = "ttf" or _
        fileExtension = "otf" or _
        fileExtension = "pfm" or _
        fileExtension = "fon" Then
        'check if Font is Already installed. If not, Install
        If objDictionary.Exists(fileName) Then
            ' wscript.echo fileName & " already exists in " & strFontDir
            doExist = doExist + 1
        Else
            'wscript.echo fso.GetAbsolutePathName(File) & " doesn't exists in " & strFontDir
            objFontFolder.CopyHere file.Path, noProgressDialog + yesToAll + noUIIfError
            dontExist = dontExist + 1
        End If
    End If
Next
End Sub
