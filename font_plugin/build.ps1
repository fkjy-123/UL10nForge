[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir,

    [Parameter(Mandatory = $true)]
    [string]$BepInExZip
)

$ErrorActionPreference = 'Stop'
$temporaryDirectory = $null
$expectedBepInExFileName = 'BepInEx_win_x64_5.4.23.5.zip'
$expectedBepInExSize = 639118
$expectedBepInExSha256 = '82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4'
$expectedSdkVersion = [System.Version]'10.0.301'

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [ValidateSet('Container', 'Leaf')]
        [string]$PathType
    )

    $pathRoot = [System.IO.Path]::GetPathRoot($Path)
    $isDriveAbsolute = $pathRoot -match '^[A-Za-z]:[\\/]$'
    $isUncAbsolute = $pathRoot -match '^\\\\[^\\]+\\[^\\]+[\\/]$'
    if (-not [System.IO.Path]::IsPathRooted($Path) -or
        (-not $isDriveAbsolute -and -not $isUncAbsolute)) {
        throw "Path must be absolute: $Path"
    }

    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $resolved -PathType $PathType)) {
        throw "Expected a $PathType path: $resolved"
    }

    return [System.IO.Path]::GetFullPath($resolved)
}

function Expand-ValidatedArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArchivePath,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $destinationRoot = [System.IO.Path]::GetFullPath($Destination)
    $destinationPrefix = $destinationRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    $memberNames = @{}
    try {
        foreach ($entry in $archive.Entries) {
            $normalized = $entry.FullName.Replace('\', '/')
            if ([string]::IsNullOrWhiteSpace($normalized) -or $normalized.StartsWith('/')) {
                throw "Unsafe archive member: $($entry.FullName)"
            }

            $parts = $normalized.Split('/') | Where-Object { $_ -ne '' }
            if ($parts.Count -eq 0 -or $parts -contains '..' -or $parts -contains '.') {
                throw "Unsafe archive member: $($entry.FullName)"
            }

            $unixFileType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
            if ($unixFileType -eq 0xA000) {
                throw "Archive must not contain symbolic links: $($entry.FullName)"
            }

            $memberNames[$normalized] = $true

            $target = [System.IO.Path]::GetFullPath(
                [System.IO.Path]::Combine($destinationRoot, $normalized.Replace('/', '\')))
            if (-not $target.StartsWith(
                    $destinationPrefix,
                    [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Archive member escapes the temporary directory: $($entry.FullName)"
            }
        }

        $requiredMembers = @(
            'winhttp.dll',
            'doorstop_config.ini',
            'BepInEx/core/BepInEx.dll'
        )
        $missingMembers = @(
            $requiredMembers | Where-Object { -not $memberNames.ContainsKey($_) }
        )
        if ($missingMembers.Count -gt 0) {
            throw 'BepInEx archive is missing required members: ' + ($missingMembers -join ', ')
        }
    }
    finally {
        $archive.Dispose()
    }

    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $destinationRoot)
}

try {
    $resolvedGameDir = Resolve-AbsolutePath -Path $GameDir -PathType Container
    $resolvedBepInExZip = Resolve-AbsolutePath -Path $BepInExZip -PathType Leaf
    if ([System.IO.Path]::GetFileName($resolvedBepInExZip) -ne $expectedBepInExFileName) {
        throw "Expected BepInEx archive $expectedBepInExFileName"
    }
    $actualBepInExSize = (Get-Item -LiteralPath $resolvedBepInExZip).Length
    if ($actualBepInExSize -ne $expectedBepInExSize) {
        throw (
            'BepInEx archive size mismatch: expected ' +
            $expectedBepInExSize + ', got ' + $actualBepInExSize
        )
    }
    $actualBepInExSha256 = (
        Get-FileHash -LiteralPath $resolvedBepInExZip -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($actualBepInExSha256 -ne $expectedBepInExSha256) {
        throw (
            'BepInEx archive SHA-256 mismatch: expected ' +
            $expectedBepInExSha256 + ', got ' + $actualBepInExSha256
        )
    }

    $managedDirectories = @(
        Get-ChildItem -LiteralPath $resolvedGameDir -Directory -Filter '*_Data' |
            ForEach-Object { Join-Path $_.FullName 'Managed' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Container }
    )
    if ($managedDirectories.Count -ne 1) {
        throw "Expected exactly one *_Data\Managed directory under $resolvedGameDir"
    }
    $managedDirectory = [System.IO.Path]::GetFullPath($managedDirectories[0])

    $temporaryName = 'hanhua-font-build-' + [System.Guid]::NewGuid().ToString('N')
    $temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) $temporaryName
    [void](New-Item -ItemType Directory -Path $temporaryDirectory)
    $runtimeDirectory = Join-Path $temporaryDirectory 'runtime'
    [void](New-Item -ItemType Directory -Path $runtimeDirectory)
    Expand-ValidatedArchive -ArchivePath $resolvedBepInExZip -Destination $runtimeDirectory

    $sdkCandidates = @()
    foreach ($line in (& dotnet --list-sdks)) {
        if ($line -match '^([^\s]+)\s+\[(.+)\]$') {
            try {
                $sdkCandidates += [pscustomobject]@{
                    Version = [System.Version]$Matches[1].Split('-')[0]
                    Compiler = Join-Path $Matches[2] ($Matches[1] + '\Roslyn\bincore\csc.dll')
                }
            }
            catch {
                continue
            }
        }
    }
    $matchingSdk = @(
        $sdkCandidates | Where-Object {
            $_.Version -eq $expectedSdkVersion -and
            (Test-Path -LiteralPath $_.Compiler -PathType Leaf)
        }
    )
    if ($matchingSdk.Count -ne 1) {
        throw "Expected exactly one installed dotnet SDK $expectedSdkVersion"
    }
    $compiler = $matchingSdk[0].Compiler

    $textMeshProCandidates = @(
        @(
            'Unity.TextMeshPro.dll',
            'UnityEngine.TextMeshPro.dll'
        ) | ForEach-Object { Join-Path $managedDirectory $_ } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
    if ($textMeshProCandidates.Count -ne 1) {
        throw "Expected exactly one TextMeshPro assembly in $managedDirectory"
    }

    $referencePaths = @(
        (Join-Path $managedDirectory 'mscorlib.dll'),
        (Join-Path $managedDirectory 'System.dll'),
        (Join-Path $managedDirectory 'System.Core.dll'),
        (Join-Path $managedDirectory 'UnityEngine.dll'),
        (Join-Path $managedDirectory 'UnityEngine.CoreModule.dll'),
        (Join-Path $managedDirectory 'UnityEngine.AssetBundleModule.dll'),
        (Join-Path $managedDirectory 'UnityEngine.TextRenderingModule.dll'),
        (Join-Path $managedDirectory 'UnityEngine.IMGUIModule.dll'),
        (Join-Path $managedDirectory 'UnityEngine.UI.dll'),
        $textMeshProCandidates[0],
        (Join-Path $runtimeDirectory 'BepInEx\core\BepInEx.dll'),
        (Join-Path $runtimeDirectory 'BepInEx\core\0Harmony.dll')
    )
    # netstandard.dll 仅 .NET 4.x 配置的 Managed 目录存在（Unity 2018.1+
    # 的 .NET 4.x 模式）；CLR 2.0（.NET 3.5，Unity 2018.2 及更早默认）下
    # 没有——可选引用，保证老 Unity 也能编译。产物引用游戏 mscorlib：
    # 用 CLR 2.0 游戏编译产出 mscorlib 2.0 引用，所有 Unity（CLR 4.0
    # 兼容 2.0 目标）通用。
    $netstandardPath = Join-Path $managedDirectory 'netstandard.dll'
    if (Test-Path -LiteralPath $netstandardPath -PathType Leaf) {
        $referencePaths += $netstandardPath
    }
    $missingReferences = @(
        $referencePaths | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
    )
    if ($missingReferences.Count -gt 0) {
        throw 'Missing compiler references: ' + ($missingReferences -join ', ')
    }

    $sourcePath = Join-Path $PSScriptRoot 'Hanhua.FontFallback\HanhuaFontPlugin.cs'
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Plugin source is missing: $sourcePath"
    }

    $temporaryOutput = Join-Path $temporaryDirectory 'Hanhua.FontFallback.dll'
    $compilerArguments = @(
        'exec',
        $compiler,
        '/noconfig',
        '/nostdlib+',
        '/target:library',
        '/deterministic+',
        '/optimize+',
        '/debug-',
        '/langversion:latest',
        "/out:$temporaryOutput",
        $sourcePath
    )
    foreach ($reference in $referencePaths) {
        $compilerArguments += "/reference:$reference"
    }

    Write-Host ('COMPILER_COMMAND=dotnet ' + ($compilerArguments -join ' '))
    & dotnet @compilerArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $temporaryOutput -PathType Leaf)) {
        throw "Roslyn compilation failed with exit code $LASTEXITCODE"
    }

    # 产物必须匹配受支持的 Unity CLR 2/4 家族。用字节加载避免 Windows
    # 对临时 DLL 保持路径锁，确保 finally 能清理且不掩盖验证错误。
    $probeOutputDeadline = [DateTime]::UtcNow.AddSeconds(5)
    $probeOutputFile = $null
    $probeAssemblyBytes = $null
    while ($true) {
        $probeOutputFile = Get-Item -LiteralPath $temporaryOutput
        if ($probeOutputFile.Length -ne 0) {
            $probeAssemblyBytes = [System.IO.File]::ReadAllBytes($temporaryOutput)
            if ($probeAssemblyBytes.Length -eq $probeOutputFile.Length) {
                break
            }
        }
        if ([DateTime]::UtcNow -ge $probeOutputDeadline) {
            if ($probeOutputFile.Length -eq 0) {
                throw 'Compiled plugin is empty; cannot verify CLR compatibility'
            }
            if ($probeAssemblyBytes.Length -ne $probeOutputFile.Length) {
                throw 'Compiled plugin read was incomplete; cannot verify CLR compatibility'
            }
        }
        Start-Sleep -Milliseconds 50
    }
    $probeAssembly = [Reflection.Assembly]::ReflectionOnlyLoad(
        [byte[]]$probeAssemblyBytes)
    $probeMscorlib = @(
        $probeAssembly.GetReferencedAssemblies() |
            Where-Object { $_.Name -eq 'mscorlib' }
    )
    if ($probeMscorlib.Count -ne 1) {
        throw 'Compiled plugin has no single mscorlib reference; cannot verify CLR compatibility'
    }
    $supportedMscorlibMajors = @('2', '4')
    $probeMscorlibMajor = $probeMscorlib[0].Version.Major.ToString()
    if ($supportedMscorlibMajors -notcontains $probeMscorlibMajor) {
        throw (
            'Compiled plugin targets mscorlib ' + $probeMscorlib[0].Version +
            '; supported Unity CLR families are major 2 and 4. ' +
            'Rebuild with a supported Unity game directory'
        )
    }

    $outputDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $PSScriptRoot '..\resources\font_override'))
    [void](New-Item -ItemType Directory -Force -Path $outputDirectory)
    $outputPath = Join-Path $outputDirectory 'Hanhua.FontFallback.dll'
    Copy-Item -LiteralPath $temporaryOutput -Destination $outputPath -Force
    $outputFile = Get-Item -LiteralPath $outputPath
    $outputSha256 = (
        Get-FileHash -LiteralPath $outputPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    Write-Host "OUTPUT=$($outputFile.FullName)"
    Write-Host "OUTPUT_SIZE=$($outputFile.Length)"
    Write-Host "OUTPUT_SHA256=$outputSha256"
}
finally {
    if ($temporaryDirectory -and (Test-Path -LiteralPath $temporaryDirectory)) {
        $resolvedTemporary = [System.IO.Path]::GetFullPath($temporaryDirectory)
        $expectedParent = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if (
            [System.IO.Path]::GetDirectoryName($resolvedTemporary).TrimEnd('\') -eq
                $expectedParent.TrimEnd('\') -and
            [System.IO.Path]::GetFileName($resolvedTemporary).StartsWith(
                'hanhua-font-build-',
                [System.StringComparison]::Ordinal)
        ) {
            Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
        }
        else {
            Write-Warning "Refusing to clean unexpected temporary path: $resolvedTemporary"
        }
    }
}
