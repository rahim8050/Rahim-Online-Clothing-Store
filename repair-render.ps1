$ErrorActionPreference = "Stop"

Write-Host "==> Starting Render repair (Tailwind, WhiteNoise, settings, templates)..."

function Backup-File($path) {
  if (Test-Path $path) {
    Copy-Item $path "$path.bak" -Force
  }
}

# 1) Clean requirements.txt merge markers
if (Test-Path "requirements.txt") {
  Backup-File "requirements.txt"
  (Get-Content requirements.txt) |
    Where-Object { $_ -notmatch '^(<<<<<<<|=======|>>>>>>>)' } |
    Set-Content requirements.txt -NoNewline
  Write-Host "requirements.txt cleaned (if markers existed)."
} else {
  Write-Host "requirements.txt not found (skipping)."
}

# 2) Tailwind source & config
New-Item -ItemType Directory -Force -Path "src" | Out-Null
if (Test-Path "src/input.css") {
  Backup-File "src/input.css"
  $css = Get-Content "src/input.css" -Raw
  $css = $css -replace '(?is)@import\s+["''].*tailwindcss["''];?\s*', ''
  $css = $css -replace '(?is)url\([^)]*src\/tailwindcss[^)]*\)', ''
  foreach ($d in @("base","components","utilities")) {
    if ($css -notmatch "@tailwind\s+$d;") {
      $css = "@tailwind $d;`n" + $css
    }
  }
  Set-Content "src/input.css" $css -NoNewline
  Write-Host "Sanitized src/input.css"
} else {
@"
@tailwind base;
@tailwind components;
@tailwind utilities;

/* put any custom CSS below */
"@ | Set-Content "src/input.css" -NoNewline
  Write-Host "Created src/input.css"
}

if (-not (Test-Path "tailwind.config.js")) {
@"
module.exports = {
  content: [
    "./templates/**/*.{html,htm}",
    "./**/*.html",
    "./**/*.{js,ts,vue}",
    "./**/*.py"
  ],
  theme: { extend: {} },
  plugins: [],
};
"@ | Set-Content "tailwind.config.js" -NoNewline
  Write-Host "Created tailwind.config.js"
} else {
  Write-Host "tailwind.config.js already exists."
}

# 3) Ensure static/build exists
New-Item -ItemType Directory -Force -Path "static\build" | Out-Null
if (-not (Test-Path "static\.gitkeep")) { "" | Set-Content "static\.gitkeep" }
Write-Host "Ensured static/build and static/.gitkeep"

# 4) Patch templates: compiled CSS & remove CDN
$templates = Get-ChildItem -Recurse -Include *.html -Path "templates" -ErrorAction SilentlyContinue
foreach ($f in $templates) {
  $content = Get-Content $f.FullName -Raw
  $orig = $content
  if ($content -notmatch '\{\%\s*load\s+static\s*\%\}') {
    if ($content -match '(?is)<head[^>]*>') {
      $content = $content -replace '(?is)(<head[^>]*>)', "`$1`r`n{% load static %}"
    } else {
      $content = "{% load static %}`r`n" + $content
    }
  }
  $content = $content -replace '(?is)<script[^>]*cdn\.tailwindcss\.com[^<]*</script>\s*', ''
  $content = $content -replace '(?is)\{\%\s*static\s*[''"]src/input\.css[''"]\s*\%\}', "{% static 'build/tailwind.css' %}"
  if ($content -ne $orig) {
    Backup-File $f.FullName
    Set-Content $f.FullName $content -NoNewline
    Write-Host "Patched $($f.FullName)"
  }
}

# 5) Patch settings.py (WhiteNoise + Stripe env guards)
$settingsCandidates = @(
  "Rahim_Online_ClothesStore\settings.py",
  "Rahim_Online_ClothesStore\settings\__init__.py"
)
$settingsPath = $settingsCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($null -eq $settingsPath) {
  Write-Warning "Could not find settings.py. If it's elsewhere, update the path list."
} else {
  Backup-File $settingsPath
  $s = Get-Content $settingsPath -Raw
  if ($s -notmatch '(?m)^\s*import\s+sys\b') {
    $s = $s -replace '(?m)^(from\s+pathlib\s+import\s+Path\s*)$', "`$1`r`nimport sys"
  }
  $s = $s -replace '(?m)^\s*STATIC_URL\s*=.*$', 'STATIC_URL = "/static/"'
  if ($s -notmatch '(?m)^\s*STATIC_ROOT\s*=') { $s += "`r`nSTATIC_ROOT = BASE_DIR / 'staticfiles'" }
  if ($s -notmatch '(?m)^\s*STATICFILES_DIRS\s*=') { $s += "`r`nSTATICFILES_DIRS = [BASE_DIR / 'static']" }
  if ($s -notmatch '(?m)^\s*STATICFILES_STORAGE\s*=') { $s += "`r`nSTATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'" }

  if ($s -notmatch '(?m)^\s*from\s+environ\s+import\s+Env\b') { $s = "from environ import Env`r`n" + $s }
  if ($s -notmatch '(?m)^\s*env\s*=\s*Env\(\)') { $s = $s -replace '(?m)^(BASE_DIR\s*=.*)$', "`$1`r`nenv = Env()" }

  $s = $s -replace '(?is)raise\s+RuntimeError\(\s*["'']Missing\s+required\s+payment\s+envs.*?\)\s*', ''
  $s = $s -replace '(?is)#\s*BEGIN_STRIPE_GUARD.*?#\s*END_STRIPE_GUARD', ''
  $stripeGuard = @"
# BEGIN_STRIPE_GUARD
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)
MGMT_CMDS_SAFE = {"collectstatic", "migrate", "makemigrations", "check", "test", "shell"}
RUNNING_MGMT = (len(sys.argv) > 1 and sys.argv[1] in MGMT_CMDS_SAFE)
IS_PROD = (not env.bool("DEBUG", False))
REQUIRE_PAYMENT_ENVS = IS_PROD and (not RUNNING_MGMT)
if REQUIRE_PAYMENT_ENVS:
    _missing = [k for k, v in {
        "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
        "STRIPE_WEBHOOK_SECRET": STRIPE_WEBHOOK_SECRET,
    }.items() if not v]
    if _missing:
        raise RuntimeError(f"Missing required payment envs: {', '.join(_missing)}")
else:
    STRIPE_SECRET_KEY = STRIPE_SECRET_KEY or "disabled"
    STRIPE_WEBHOOK_SECRET = STRIPE_WEBHOOK_SECRET or "disabled"
# END_STRIPE_GUARD
"@
  $s += "`r`n" + $stripeGuard
  Set-Content $settingsPath $s -NoNewline
  Write-Host "Patched $settingsPath"
}

Write-Host "==> Repair complete. Commit & push, then update Render Build Command."
