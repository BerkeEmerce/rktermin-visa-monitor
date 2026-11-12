# Run from the extracted repository root. Requires git and GitHub CLI (gh).
$ErrorActionPreference = 'Stop'
# Pick up installers' PATH changes when this PowerShell window was already open.
# Preserve existing entries and update only this process, not Windows settings.
$setupInstalledPaths = @(
    [Environment]::GetEnvironmentVariable('Path', 'Machine')
    [Environment]::GetEnvironmentVariable('Path', 'User')
) -join ';'
foreach ($setupDirectory in ($setupInstalledPaths -split ';')) {
    if (-not [string]::IsNullOrWhiteSpace($setupDirectory) -and
        ($env:Path -split ';') -notcontains $setupDirectory) {
        $env:Path += ";$setupDirectory"
    }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI from https://cli.github.com then rerun this script.' }
gh auth status
if ($LASTEXITCODE -ne 0) { gh auth login --web --git-protocol https }
if ($LASTEXITCODE -ne 0) { throw 'GitHub sign-in failed.' }
$repoName = Read-Host 'Repository name (press Enter for rktermin-visa-monitor)'
if ([string]::IsNullOrWhiteSpace($repoName)) { $repoName = 'rktermin-visa-monitor' }
if ($repoName -notmatch '^[A-Za-z0-9_.-]+$') { throw 'Use a repository name with letters, numbers, dots, dashes or underscores.' }
if (Test-Path -LiteralPath '.git') { throw 'This helper expects an extracted package without an existing .git directory.' }
git init -b main
if ($LASTEXITCODE -ne 0) { throw 'git init failed.' }
git add .
git -c user.name='Monitor Setup' -c user.email='monitor-setup@users.noreply.github.com' commit -m 'Add experimental personal visa monitor'
if ($LASTEXITCODE -ne 0) { throw 'Initial commit failed.' }
gh repo create $repoName --public --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw 'Repository creation failed; inspect gh output before rerunning.' }
Write-Host 'Paste the bot token at the hidden prompt from gh (input is not echoed).'
gh secret set TELEGRAM_BOT_TOKEN
if ($LASTEXITCODE -ne 0) { throw 'Token secret could not be saved.' }
Write-Host 'Enter your Telegram chat ID at the next hidden prompt.'
gh secret set TELEGRAM_CHAT_ID
if ($LASTEXITCODE -ne 0) { throw 'Chat ID secret could not be saved.' }
gh workflow run monitor.yml -f mode=telegram-test
gh run list --workflow monitor.yml --limit 1
Write-Host 'Repository is published. Schedules remain disabled until live validation. See START_HERE.md.'
