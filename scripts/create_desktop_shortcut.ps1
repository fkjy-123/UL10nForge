param(
    [string]$ShortcutPath = (Join-Path `
        -Path (Join-Path -Path $env:USERPROFILE -ChildPath "Desktop") `
        -ChildPath ((-join @(
            [char]0x6C49,
            [char]0x5316,
            [char]0x52A9,
            [char]0x624B
        )) + ".lnk")),
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonExe = ""
)

# 优先使用内置 Python(runtime\python,随包分发);缺失时回退系统 python。
function Get-PythonExe {
    param([string]$ProjectRoot)
    $builtin = Join-Path -Path $ProjectRoot -ChildPath "runtime\python\python.exe"
    if (Test-Path -LiteralPath $builtin -PathType Leaf) {
        return $builtin
    }
    return (Get-Command python -ErrorAction Stop).Source
}

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Resolve-ExistingFile {
    param(
        [string]$Path,
        [string]$Description
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description does not exist or is not a file: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).ProviderPath
}

function Resolve-ExistingDirectory {
    param(
        [string]$Path,
        [string]$Description
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description does not exist or is not a directory: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).ProviderPath
}

function Assert-ShortcutProperty {
    param(
        [string]$Name,
        [string]$Actual,
        [string]$Expected,
        [System.StringComparison]$Comparison = [System.StringComparison]::Ordinal
    )

    if (-not [string]::Equals($Actual, $Expected, $Comparison)) {
        throw "Shortcut verification failed for $Name. Expected '$Expected', got '$Actual'."
    }
}

$resolvedProjectRoot = Resolve-ExistingDirectory -Path $ProjectRoot -Description "Project root"
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Get-PythonExe -ProjectRoot $resolvedProjectRoot
}
$mainPath = Resolve-ExistingFile `
    -Path (Join-Path -Path $resolvedProjectRoot -ChildPath "main.py") `
    -Description "Project main.py"
$resolvedPythonExe = Resolve-ExistingFile -Path $PythonExe -Description "Python executable"
$pythonDirectory = Split-Path -Parent $resolvedPythonExe
$pythonwPath = Resolve-ExistingFile `
    -Path (Join-Path -Path $pythonDirectory -ChildPath "pythonw.exe") `
    -Description "pythonw.exe beside Python executable"

if ([string]::IsNullOrWhiteSpace($ShortcutPath)) {
    throw "Shortcut path must not be empty."
}

$shortcutFullPath = [System.IO.Path]::GetFullPath($ShortcutPath)
$shortcutName = Split-Path -Leaf $shortcutFullPath
if ([string]::IsNullOrWhiteSpace($shortcutName) -or
    -not [string]::Equals(
        [System.IO.Path]::GetExtension($shortcutName),
        ".lnk",
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
    throw "Shortcut path must end in .lnk: $shortcutFullPath"
}

$shortcutDirectory = Resolve-ExistingDirectory `
    -Path (Split-Path -Parent $shortcutFullPath) `
    -Description "Shortcut parent directory"
$resolvedShortcutPath = Join-Path -Path $shortcutDirectory -ChildPath $shortcutName

$expectedArguments = '"' + $mainPath + '"'
$expectedDescription = "Unity " + (-join @(
    [char]0x6E38,
    [char]0x620F,
    [char]0x6C49,
    [char]0x5316,
    [char]0x52A9,
    [char]0x624B
))
$shell = $null
$shortcut = $null
$verifiedShortcut = $null

try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($resolvedShortcutPath)
    $shortcut.TargetPath = $pythonwPath
    $shortcut.Arguments = $expectedArguments
    $shortcut.WorkingDirectory = $resolvedProjectRoot
    $shortcut.Description = $expectedDescription
    $shortcut.Save()

    $verifiedShortcut = $shell.CreateShortcut($resolvedShortcutPath)
    Assert-ShortcutProperty -Name "TargetPath" `
        -Actual $verifiedShortcut.TargetPath `
        -Expected $pythonwPath `
        -Comparison ([System.StringComparison]::OrdinalIgnoreCase)
    Assert-ShortcutProperty -Name "Arguments" `
        -Actual $verifiedShortcut.Arguments `
        -Expected $expectedArguments
    Assert-ShortcutProperty -Name "WorkingDirectory" `
        -Actual $verifiedShortcut.WorkingDirectory `
        -Expected $resolvedProjectRoot `
        -Comparison ([System.StringComparison]::OrdinalIgnoreCase)
    Assert-ShortcutProperty -Name "Description" `
        -Actual $verifiedShortcut.Description `
        -Expected $expectedDescription

    Write-Output "ShortcutPath=$resolvedShortcutPath"
    Write-Output "TargetPath=$($verifiedShortcut.TargetPath)"
    Write-Output "Arguments=$($verifiedShortcut.Arguments)"
    Write-Output "WorkingDirectory=$($verifiedShortcut.WorkingDirectory)"
    Write-Output "Description=$($verifiedShortcut.Description)"
}
finally {
    foreach ($comObject in @($verifiedShortcut, $shortcut, $shell)) {
        if ($null -ne $comObject -and [System.Runtime.InteropServices.Marshal]::IsComObject($comObject)) {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($comObject)
        }
    }
}
