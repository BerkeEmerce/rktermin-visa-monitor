# Run in your own PowerShell window; gh hides API-key input.
$ErrorActionPreference = 'Stop'
$gh = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
if (-not (Test-Path -LiteralPath $gh)) { $gh = (Get-Command gh -ErrorAction Stop).Source }
$repo = 'BerkeEmerce/rktermin-visa-monitor'
Write-Host 'Paste your funded 2Captcha API key at the hidden prompt. This enables paid CAPTCHA solving.'
& $gh secret set CAPTCHA_API_KEY --repo $repo
if ($LASTEXITCODE -ne 0) { throw 'API key could not be saved.' }
& $gh variable set CAPTCHA_MODE --body 2captcha --repo $repo
if ($LASTEXITCODE -ne 0) { throw 'Could not enable 2Captcha.' }
& $gh variable set CHECK_INTERVAL_MINUTES --body 60 --repo $repo
if ($LASTEXITCODE -ne 0) { throw 'Could not set hourly interval.' }
& $gh variable set MONITOR_ENABLED --body true --repo $repo
if ($LASTEXITCODE -ne 0) { throw 'Could not enable hourly schedule.' }
& $gh workflow run monitor.yml --repo $repo -f mode=monitor
if ($LASTEXITCODE -ne 0) { throw 'Could not start live validation.' }
Write-Host 'Live check started. View results: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions'
