param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$Destination = "",
    [switch]$CpuOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$sourcePath = [System.IO.Path]::GetFullPath($Source)
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $destinationPath = Join-Path $projectRoot "runtime\llama"
} else {
    $destinationPath = [System.IO.Path]::GetFullPath($Destination)
}

if (-not [System.IO.Directory]::Exists($sourcePath)) {
    throw "llama.cpp runtime source directory does not exist: $sourcePath"
}

$sourcePrefix = $sourcePath.TrimEnd('\') + '\'
$destinationPrefix = $destinationPath.TrimEnd('\') + '\'
if ($sourcePath -eq $destinationPath -or
    $sourcePrefix.StartsWith($destinationPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $destinationPrefix.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Source and destination must not overlap."
}

$required = @(
    "llama-server.exe",
    "llama-server-impl.dll",
    "llama-common.dll",
    "llama.dll",
    "ggml.dll",
    "ggml-base.dll"
)
if (-not $CpuOnly) {
    $required += @(
        "ggml-cuda.dll",
        "cublas64_13.dll",
        "cublasLt64_13.dll",
        "cudart64_13.dll"
    )
}

$missing = @($required | Where-Object {
    -not [System.IO.File]::Exists((Join-Path $sourcePath $_))
})
$cpuLibraries = @(Get-ChildItem -LiteralPath $sourcePath -File -Filter "ggml-cpu-*.dll")
if ($cpuLibraries.Count -eq 0) {
    $missing += "ggml-cpu-*.dll"
}
if ($missing.Count -gt 0) {
    throw "Incomplete llama.cpp runtime. Missing: $($missing -join ', ')"
}

[System.IO.Directory]::CreateDirectory($destinationPath) | Out-Null
$files = @(
    Get-Item -LiteralPath (Join-Path $sourcePath "llama-server.exe")
    Get-ChildItem -LiteralPath $sourcePath -File -Filter "*.dll"
)
if ($CpuOnly) {
    $files = @($files | Where-Object {
        $_.Name -notin @("ggml-cuda.dll", "cublas64_13.dll", "cublasLt64_13.dll", "cudart64_13.dll")
    })
}

$copied = 0
$skipped = 0
foreach ($file in $files) {
    $target = Join-Path $destinationPath $file.Name
    $same = $false
    if ([System.IO.File]::Exists($target)) {
        $targetInfo = Get-Item -LiteralPath $target
        if ($targetInfo.Length -eq $file.Length) {
            $same = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -eq
                    (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        }
    }
    if ($same) {
        $skipped++
        continue
    }
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    $copied++
}

$destinationMissing = @($required | Where-Object {
    -not [System.IO.File]::Exists((Join-Path $destinationPath $_))
})
if (@(Get-ChildItem -LiteralPath $destinationPath -File -Filter "ggml-cpu-*.dll").Count -eq 0) {
    $destinationMissing += "ggml-cpu-*.dll"
}
if ($destinationMissing.Count -gt 0) {
    throw "Runtime verification failed. Missing: $($destinationMissing -join ', ')"
}

$models = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "models") -File -Filter "*.gguf" -ErrorAction SilentlyContinue)
Write-Output "Installed llama.cpp runtime: $destinationPath"
Write-Output "Copied: $copied; unchanged: $skipped"
if ($models.Count -gt 0) {
    Write-Output "Discovered model: $($models[0].FullName)"
} else {
    Write-Output "No GGUF model found under: $(Join-Path $projectRoot 'models')"
}
