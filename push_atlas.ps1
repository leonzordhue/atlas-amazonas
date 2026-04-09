# ╔══════════════════════════════════════════════════════════════╗
# ║  PUSH AUTOMÁTICO — Atlas Amazonas                           ║
# ║  Executa no PowerShell (Windows)                             ║
# ║  Pré-requisito: Git instalado e autenticado (git config)     ║
# ╚══════════════════════════════════════════════════════════════╝

# ── CONFIGURAÇÃO ──
$PASTA_GEOJSON = "C:\Users\peneto\Desktop\novo geojson"
$REPO_URL      = "https://github.com/leonzordhue/atlas-amazonas.git"
$REPO_LOCAL    = "$env:TEMP\atlas-amazonas"
$BRANCH        = "main"

Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ATLAS AMAZONAS — Push Automático" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. CLONE OU PULL ──
if (Test-Path $REPO_LOCAL) {
    Write-Host "[1/4] Repositório local encontrado. Atualizando..." -ForegroundColor Yellow
    Set-Location $REPO_LOCAL
    git pull origin $BRANCH 2>&1 | Out-Null
} else {
    Write-Host "[1/4] Clonando repositório..." -ForegroundColor Yellow
    git clone $REPO_URL $REPO_LOCAL 2>&1 | Out-Null
    Set-Location $REPO_LOCAL
}

# ── 2. COPIAR GEOJSON ──
Write-Host "[2/4] Copiando GeoJSONs de: $PASTA_GEOJSON" -ForegroundColor Yellow
$arquivos = Get-ChildItem -Path $PASTA_GEOJSON -Filter "*.geojson" -File
$count = 0
foreach ($f in $arquivos) {
    Copy-Item $f.FullName -Destination $REPO_LOCAL -Force
    Write-Host "      + $($f.Name) ($([math]::Round($f.Length/1KB, 1)) KB)" -ForegroundColor Gray
    $count++
}
Write-Host "      Total: $count arquivo(s) copiado(s)" -ForegroundColor Green

# ── 3. GIT ADD + COMMIT ──
Write-Host "[3/4] Commitando..." -ForegroundColor Yellow
git add -A 2>&1 | Out-Null

$data = Get-Date -Format "yyyy-MM-dd HH:mm"
$msg = "atlas: atualização automática — $count geojson(s) — $data"

# Verifica se há mudanças
$status = git status --porcelain
if ($status) {
    git commit -m $msg 2>&1 | Out-Null
    Write-Host "      Commit: $msg" -ForegroundColor Gray
} else {
    Write-Host "      Nenhuma alteração detectada." -ForegroundColor Gray
}

# ── 4. PUSH ──
Write-Host "[4/4] Enviando para GitHub..." -ForegroundColor Yellow
git push origin $BRANCH 2>&1

Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Green
Write-Host "  CONCLUÍDO!" -ForegroundColor Green
Write-Host "  https://github.com/leonzordhue/atlas-amazonas" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
