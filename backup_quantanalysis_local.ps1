param(
    [string]$BackupRoot = "D:\QuantBackup\QuantAnalysis",
    [int]$KeepCount = 1
)

$ErrorActionPreference = "Stop"

$Source = "D:\QuantAnalysis"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupName = "QuantAnalysis-$Timestamp.zip"
$BackupFile = Join-Path $BackupRoot $BackupName
$TempFile = "$BackupFile.tmp"

$ExcludeDirs = @(".git", "__pycache__", "_tmp", "backups")
$ExcludeFiles = @()

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

if (Test-Path -LiteralPath $TempFile) {
    Remove-Item -LiteralPath $TempFile -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$SourceRoot = (Resolve-Path -LiteralPath $Source).Path.TrimEnd("\")
$CreatedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
$Skipped = New-Object System.Collections.Generic.List[string]
$FileCount = 0

$Zip = [System.IO.Compression.ZipFile]::Open($TempFile, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $Source -Recurse -File -Force |
        Where-Object {
            $relative = $_.FullName.Substring($SourceRoot.Length + 1)
            $parts = $relative -split "[\\/]"
            (-not ($parts | Where-Object { $ExcludeDirs -contains $_ })) -and
                (-not ($ExcludeFiles -contains $_.Name))
        } |
        ForEach-Object {
            $File = $_
            $relative = $_.FullName.Substring($SourceRoot.Length + 1)
            try {
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                    $Zip,
                    $File.FullName,
                    $relative,
                    [System.IO.Compression.CompressionLevel]::Optimal
                ) | Out-Null
                $script:FileCount += 1
            } catch {
                $Skipped.Add($File.FullName) | Out-Null
            }
        }

    $Manifest = [ordered]@{
        source = $Source
        destination = $BackupFile
        backup_type = "zip"
        created_at = $CreatedAt
        exclude_dirs = $ExcludeDirs
        exclude_files = $ExcludeFiles
        file_count = $FileCount
        skipped_files = $Skipped
        keep_count = $KeepCount
    }
    $ManifestJson = $Manifest | ConvertTo-Json -Depth 6
    $Entry = $Zip.CreateEntry("backup_manifest.json")
    $Writer = New-Object System.IO.StreamWriter($Entry.Open(), [System.Text.Encoding]::UTF8)
    try {
        $Writer.Write($ManifestJson)
    } finally {
        $Writer.Dispose()
    }
} finally {
    $Zip.Dispose()
}

Move-Item -LiteralPath $TempFile -Destination $BackupFile -Force

if (Test-Path -LiteralPath $BackupRoot) {
    $ResolvedRoot = (Resolve-Path -LiteralPath $BackupRoot).Path.TrimEnd("\")
    $ResolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
    if ($ResolvedRoot -ne "D:\QuantBackup\QuantAnalysis") {
        throw "Refusing cleanup outside expected backup root: $ResolvedRoot"
    }

    Get-ChildItem -LiteralPath $BackupRoot -Force |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $KeepCount |
        Remove-Item -Recurse -Force

    Get-ChildItem -LiteralPath $BackupRoot -Force |
        Where-Object { $_.FullName -ne $ResolvedBackup } |
        Remove-Item -Recurse -Force
}

Write-Output "status=ok"
Write-Output "destination=$BackupFile"
Write-Output "backup_type=zip"
Write-Output "file_count=$FileCount"
Write-Output "skipped_count=$($Skipped.Count)"
Write-Output "keep_count=$KeepCount"
