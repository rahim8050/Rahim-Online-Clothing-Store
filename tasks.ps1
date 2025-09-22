param([string]$task="help")

$env:DJANGO_SETTINGS_MODULE="Rahim_Online_ClothesStore.settings"

switch ($task) {
  "lint" { ruff .; ruff format --check .; black --check .; isort --check-only .; break }
  "type" { mypy .; break }
  "test" { pytest -q --cov=. --cov-report=term-missing; break }
  "cc"   { radon cc -s -a apis cart orders payments users product_app ops_agent notifications Mpesa assistant; break }
  "mi"   { radon mi -s apis cart orders payments users product_app ops_agent notifications Mpesa assistant; break }
  "cloc" { cloc --vcs=git --include-ext=py,js,vue,html,css --not-match-d 'migrations|node_modules|static\\(dist|build)|staticfiles|dist|build'; break }
  default { "Usage: .\tasks.ps1 [lint|type|test|cc|mi|cloc]"; break }
}
