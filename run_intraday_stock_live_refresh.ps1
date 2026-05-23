param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Python = "D:\Quant\venv64\Scripts\python.exe"
$Script = "D:\QuantAnalysis\intraday_live_stock_refresh.py"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

if ($Force) {
    & $Python $Script --force
} else {
    & $Python $Script
}
