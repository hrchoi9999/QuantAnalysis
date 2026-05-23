param(
    [string]$BackupRoot = "D:\QuantBackup\QuantAnalysis",
    [int]$KeepDays = 30
)

$ErrorActionPreference = "Stop"

$Source = "D:\QuantAnalysis"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = Join-Path $BackupRoot "QuantAnalysis-$Timestamp"

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

$ExcludeDirs = @(".git", "__pycache__", "_tmp", "backups")
$ExcludeFiles = @()

robocopy $Source $Destination /E /XD $ExcludeDirs /XF $ExcludeFiles /R:2 /W:2 /NFL /NDL /NP | Out-Null
$ExitCode = $LASTEXITCODE
if ($ExitCode -ge 8) {
    throw "robocopy failed with exit code $ExitCode"
}

$Manifest = [ordered]@{
    source = $Source
    destination = $Destination
    created_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    exclude_dirs = $ExcludeDirs
    exclude_files = $ExcludeFiles
    robocopy_exit_code = $ExitCode
}

$ManifestPath = Join-Path $Destination "backup_manifest.json"
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $ManifestPath -Encoding UTF8

if (Test-Path $BackupRoot) {
    Get-ChildItem -Path $BackupRoot -Directory -Filter "QuantAnalysis-*" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
        Remove-Item -Recurse -Force
}

Write-Output "status=ok"
Write-Output "destination=$Destination"
Write-Output "manifest=$ManifestPath"
Write-Output "keep_days=$KeepDays"
