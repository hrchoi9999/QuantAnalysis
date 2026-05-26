param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Python = "D:\Quant\venv64\Scripts\python.exe"
$Script = "D:\QuantAnalysis\intraday_live_stock_refresh.py"
$StatusDir = "D:\QuantAnalysis\_tmp\intraday-live-refresh"
$StdoutPath = Join-Path $StatusDir "latest_stdout.json"
$StderrPath = Join-Path $StatusDir "latest_stderr.txt"
$StatusPath = Join-Path $StatusDir "latest_status.json"

New-Item -ItemType Directory -Force -Path $StatusDir | Out-Null

if (-not (Test-Path $Python)) {
    $Python = "python"
}

$argsList = @($Script)
if ($Force) {
    $argsList += "--force"
}

$startedAt = Get-Date -Format o
$output = & $Python @argsList 2>&1
$exitCode = $LASTEXITCODE
$finishedAt = Get-Date -Format o

$stdout = $output -join [Environment]::NewLine
$stdout | Set-Content -Path $StdoutPath -Encoding UTF8

if ($exitCode -ne 0) {
    $stdout | Set-Content -Path $StderrPath -Encoding UTF8
} else {
    "" | Set-Content -Path $StderrPath -Encoding UTF8
}

$status = [ordered]@{
    started_at = $startedAt
    finished_at = $finishedAt
    exit_code = $exitCode
    command = "$Python $($argsList -join ' ')"
    stdout_path = $StdoutPath
    stderr_path = $StderrPath
}
$status | ConvertTo-Json -Depth 4 | Set-Content -Path $StatusPath -Encoding UTF8

Write-Output $stdout
exit $exitCode
