# timelog installer
# Usage (once repo is on GitHub):
#   irm https://raw.githubusercontent.com/YOUR_ORG/timelog/main/install.ps1 | iex
# Or locally from a repo clone:
#   .\install.ps1
#
# Install order:
#   1. Latest GitHub Release wheel  (if gh CLI available or repo is accessible)
#   2. Latest git main branch        (fallback)
#   3. Local clone                   (if running from the repo itself)

$ErrorActionPreference = "Stop"

# ── Configure these for your org ─────────────────────────────────────────────
$GH_REPO = "dever-labs/timelog"
# ─────────────────────────────────────────────────────────────────────────────

function Write-Step($msg) { Write-Host "`n  → $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  ✔ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  ✘ $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  timelog installer" -ForegroundColor White
Write-Host "  ──────────────────────────────────────────" -ForegroundColor DarkGray

# ── 1. Python ────────────────────────────────────────────────────────────────
Write-Step "Checking Python..."
try {
    $pyver = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
    Write-OK $pyver
} catch {
    Write-Fail "Python not found. Install Python 3.11+ from https://python.org"
}

# ── 2. pipx ───────────────────────────────────────────────────────────────────
Write-Step "Checking pipx..."
$pipxCmd = Get-Command pipx -ErrorAction SilentlyContinue
if (-not $pipxCmd) {
    Write-Host "  pipx not found — installing..." -ForegroundColor Yellow
    pip install pipx --user --quiet
    python -m pipx ensurepath | Out-Null
    $env:PATH += ";$env:USERPROFILE\.local\bin;$env:APPDATA\Python\Python311\Scripts"
    Write-OK "pipx installed"
} else {
    Write-OK "pipx $( pipx --version )"
}

# ── 3. Resolve install source ─────────────────────────────────────────────────
Write-Step "Resolving install source..."
$installSource = $null

# Try GitHub CLI first — works for private repos without extra auth setup
$ghCmd = Get-Command gh -ErrorAction SilentlyContinue
if ($ghCmd) {
    try {
        $releaseJson = gh release view --repo $GH_REPO --json tagName,assets 2>&1
        $release     = $releaseJson | ConvertFrom-Json
        $whlAsset    = $release.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
        if ($whlAsset) {
            $tag         = $release.tagName
            $tmpWhl      = Join-Path $env:TEMP $whlAsset.name
            Write-Host "  Downloading $( $whlAsset.name ) ($tag)..." -ForegroundColor DarkGray
            gh release download $tag --repo $GH_REPO --pattern "*.whl" --output $tmpWhl --clobber 2>&1 | Out-Null
            $installSource = $tmpWhl
            Write-OK "Using release $tag"
        }
    } catch { }
}

# Fall back to git+https install from latest tag
if (-not $installSource) {
    try {
        $latestTag = git ls-remote --tags "https://github.com/$GH_REPO.git" 2>$null |
                     Select-String 'refs/tags/v[\d]+\.[\d]+\.[\d]+$' |
                     ForEach-Object { $_.Matches.Value -replace 'refs/tags/', '' } |
                     Sort-Object { [version]($_ -replace 'v','') } |
                     Select-Object -Last 1
        if ($latestTag) {
            $installSource = "git+https://github.com/$GH_REPO.git@$latestTag"
            Write-OK "Using release $latestTag (git)"
        }
    } catch { }
}

# Fall back to main branch
if (-not $installSource) {
    $repoRoot = $PSScriptRoot
    if ($repoRoot -and (Test-Path "$repoRoot\pyproject.toml")) {
        $installSource = $repoRoot
        Write-OK "Using local repo clone"
    } else {
        $installSource = "git+https://github.com/$GH_REPO.git"
        Write-Warn "Could not resolve a release — installing from main branch"
    }
}

# ── 4. Install timelog ────────────────────────────────────────────────────────
Write-Step "Installing timelog..."
python -m pipx install $installSource --force --quiet
Write-OK "timelog installed"

# ── 5. Playwright Chromium ────────────────────────────────────────────────────
Write-Step "Installing Playwright Chromium browser..."
$playwrightInVenv = "$env:USERPROFILE\pipx\venvs\timelog\Scripts\playwright.exe"
if (Test-Path $playwrightInVenv) {
    & $playwrightInVenv install chromium | Out-Null
    Write-OK "Chromium installed"
} else {
    Write-Warn "Could not find playwright in pipx venv — run manually after install:"
    Write-Host '    pipx runpip timelog run playwright install chromium' -ForegroundColor DarkGray
}

# ── 6. Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ──────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  ✔ timelog is ready! Open a new terminal, then:" -ForegroundColor Green
Write-Host ""
Write-Host "    1. timelog init         ← walks you through everything" -ForegroundColor DarkGray
Write-Host "    2. timelog schedule install" -ForegroundColor DarkGray
Write-Host ""
