$ErrorActionPreference = 'Stop'
$repo = 'F:\workspace\obsidian-site'
$logDir = Join-Path $repo 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$log = Join-Path $logDir "sync_$stamp.log"
Start-Transcript -Path $log -Append | Out-Null
try {
  Set-Location $repo
  & 'C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe' 'F:\workspace\obsidian-site\scripts\build_site.py'

  $changes = git status --porcelain
  if (-not $changes) {
    Write-Host 'No changes to sync.'
    exit 0
  }

  $riskPattern = '(api[_-]?key\s*[:=]|secret\s*[:=]|password\s*[:=]|token\s*[:=]|client_secret\s*[:=]|BEGIN .*PRIVATE KEY)'
  $scanTargets = @('site', 'scripts', 'assets', 'templates', 'README.md', 'index.html')
  $rg = Get-Command rg -ErrorAction SilentlyContinue
  if ($rg) {
    $risk = & rg -n -i $riskPattern $scanTargets 2>$null
  } else {
    $risk = Get-ChildItem -Path $scanTargets -Recurse -File -ErrorAction SilentlyContinue | Select-String -Pattern $riskPattern -CaseSensitive:$false
  }
  if ($risk) {
    Write-Host 'Potential secret-like text found. Refusing to push.'
    Write-Host $risk
    exit 2
  }

  git add -A
  $message = 'Sync Obsidian site ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')
  git commit -m $message
  git push
  Write-Host 'Sync complete.'
} finally {
  Stop-Transcript | Out-Null
}
