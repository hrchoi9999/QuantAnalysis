param(
    [string]$Remote = "origin",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Repo = "D:\QuantAnalysis"
$Now = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"

Set-Location $Repo

git status --short | Out-Null

$Changes = git status --porcelain
if (-not $Changes) {
    Write-Output "status=no_changes"
    Write-Output "checked_at=$Now"
    exit 0
}

git add -A
$Staged = git diff --cached --name-only
if (-not $Staged) {
    Write-Output "status=no_staged_changes"
    Write-Output "checked_at=$Now"
    exit 0
}

$CommitMessage = "Daily QuantAnalysis backup $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git commit -m $CommitMessage
git push $Remote $Branch

Write-Output "status=ok"
Write-Output "committed_at=$Now"
Write-Output "branch=$Branch"
Write-Output "remote=$Remote"
