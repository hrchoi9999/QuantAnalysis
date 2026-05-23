param(
    [string]$AsOf = (Get-Date).ToString("yyyy-MM-dd")
)

$ErrorActionPreference = "Stop"
$Python = "D:\Quant\venv64\Scripts\python.exe"
$Script = "D:\QuantAnalysis\portfolio_pipeline.py"

if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python $Script --asof $AsOf
