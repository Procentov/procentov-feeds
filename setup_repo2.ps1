$ErrorActionPreference = "Continue"
Set-Location "C:\work\xml-feedy\procentov"

Write-Host "=== FAZE E: vytvoreni remote repo + push ==="

# Zkus zalozit repo (pokud uz existuje, gh hodi error a my ho ignorujeme)
gh repo view Procentov/procentov-feeds *> $null
$exists = ($LASTEXITCODE -eq 0)

if ($exists) {
    Write-Host "Repo Procentov/procentov-feeds JIZ EXISTUJE na GitHubu, skip create"
} else {
    Write-Host "Repo neexistuje, zakladam..."
    gh repo create Procentov/procentov-feeds --public --description "ATOS XML feeds for Procentov.cz" --disable-issues --disable-wiki
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: gh repo create selhalo s code $LASTEXITCODE"
        exit 1
    }
    Write-Host "Repo zalozeno"
}

# Napoj remote
$remotes = (git remote) -split "`n"
if ($remotes -notcontains "origin") {
    git remote add origin "https://github.com/Procentov/procentov-feeds.git"
    Write-Host "remote origin pridan"
} else {
    git remote set-url origin "https://github.com/Procentov/procentov-feeds.git"
    Write-Host "remote origin nastaven (set-url)"
}

# Stage + commit
git add .gitignore docs/ transformer.py cenove_overridy.csv requirements.txt README.md
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "Nic ke commitu (uz commitnuto?)"
} else {
    git commit -m "Sprint 1: Milo furniture feed (348 variant, 10 master groups)"
    Write-Host "Commit hotov"
}

# Push
Write-Host ""
Write-Host "Push to origin/main..."
git push -u origin main 2>&1 | ForEach-Object { Write-Host $_ }
$pushExit = $LASTEXITCODE

if ($pushExit -ne 0) {
    Write-Host ""
    Write-Host "Standardni push failed (exit $pushExit), zkousim s --force (cisty repo)..."
    git push -u origin main --force 2>&1 | ForEach-Object { Write-Host $_ }
    $pushExit = $LASTEXITCODE
}

if ($pushExit -ne 0) {
    Write-Host "ERROR: push selhal"
    exit 1
}
Write-Host "Push OK"

Write-Host ""
Write-Host "=== FAZE F: aktivace GitHub Pages ==="

# Aktivace Pages
$pagesResult = gh api "repos/Procentov/procentov-feeds/pages" -X POST -f "source[branch]=main" -f "source[path]=/docs" 2>&1
Write-Host "Pages API response:"
$pagesResult | ForEach-Object { Write-Host $_ }

# Overeni Pages config
Write-Host ""
Write-Host "=== Pages config (po aktivaci) ==="
gh api "repos/Procentov/procentov-feeds/pages" 2>&1 | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "=== HOTOVO ==="
Write-Host "Repo URL:    https://github.com/Procentov/procentov-feeds"
Write-Host "Landing URL: https://procentov.github.io/procentov-feeds/"
Write-Host "Feed URL:    https://procentov.github.io/procentov-feeds/atos.xml"
Write-Host ""
Write-Host "Last commit:"
git log -1 --oneline
