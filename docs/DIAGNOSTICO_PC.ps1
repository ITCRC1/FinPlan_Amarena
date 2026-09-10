# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    Dice, punto por punto, qué le falta a esta PC para trabajar en los FinPlan.

.DESCRIPTION
    Owner, 2026-09-10: *«yo recuerdo que me decías "¿querés que haga el cambio en
    los otros FinPlan?" y ejecutabas sin problemas; ahora no puedo, ni en FinPlan
    Amarena que era la propiedad que más acceso tenía»*.

    No es que se haya perdido acceso: la PC vieja tenía cosas que una máquina
    recién comprada no trae, y tres de las cuatro son INVISIBLES —no fallan con
    un error, simplemente hacen que nada se ofrezca—.

    Este guion no arregla nada. Sólo mide y dice qué falta, para dejar de
    adivinar. Es de lectura: no instala, no borra, no sube nada.

.EXAMPLE
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\DIAGNOSTICO_PC.ps1
#>
[CmdletBinding()]
param([string]$Raiz = "C:\dev")

$falta = @()
function Ok($t)    { Write-Host "  [ OK ]  $t" -ForegroundColor Green }
function No($t, $c){ Write-Host "  [FALTA] $t" -ForegroundColor Yellow
                     $script:falta += $c }
function Titulo($t){ Write-Host "`n=== $t ===" -ForegroundColor Cyan }

# ── 1 · Herramientas ─────────────────────────────────────────────────────────
Titulo "Herramientas"
foreach ($c in @(
    @{cmd="git";     nota="Git"},
    @{cmd="node";    nota="Node"},
    @{cmd="npm";     nota="npm"},
    @{cmd="railway"; nota="Railway CLI"})) {
    if (Get-Command $c.cmd -ErrorAction SilentlyContinue) {
        Ok "$($c.nota) — $(& $c.cmd --version 2>&1 | Select-Object -First 1)"
    } else { No "$($c.nota) no está instalado" "instalar $($c.nota)" }
}

# ⚠️ Python 3.12 EXACTO. El del sistema puede ser más nuevo y no sirve: varias
# dependencias no publican rueda para 3.13/3.14 y `pip install` falla compilando.
$py = $null
foreach ($cand in @("py -3.12","python3.12","python")) {
    try { $v = & ([scriptblock]::Create("$cand --version")) 2>&1
          if ("$v" -match "3\.12") { $py = $cand; break } } catch {}
}
if ($py) { Ok "Python 3.12 ($py)" }
else     { No "Python 3.12 (los proyectos NO usan el 3.13/3.14)" "instalar Python 3.12" }

# ── 2 · Repos ────────────────────────────────────────────────────────────────
Titulo "Repos en $Raiz"
$repos = @("FinPlan_Amarena","FinPlan_Oxygen","FinPlan_Gardens","FinPlan_CWL")
foreach ($r in $repos) {
    $d = Join-Path $Raiz $r
    if (Test-Path (Join-Path $d ".git")) { Ok $r }
    else { No "$r no está clonado" "clonar $r" }
}

# ── 3 · Entornos ─────────────────────────────────────────────────────────────
Titulo "Entornos"
foreach ($r in $repos) {
    $v = Join-Path $Raiz "$r\backend\.venv\Scripts\python.exe"
    if (Test-Path $v) { Ok "$r backend ($(& $v --version 2>&1))" }
    else { No "$r sin venv" "armar el venv de $r" }
    $n = Join-Path $Raiz "$r\frontend\node_modules"
    if (Test-Path $n) { Ok "$r frontend" }
    else { No "$r sin node_modules" "npm ci en $r" }
}

# ── 4 · Las tres autorizaciones ──────────────────────────────────────────────
Titulo "Autorizaciones"

# GitHub: se prueba SIN subir nada.
$repoGit = Join-Path $Raiz "FinPlan_Amarena"
if (Test-Path (Join-Path $repoGit ".git")) {
    Push-Location $repoGit
    $salida = (git push --dry-run origin HEAD 2>&1) -join " "
    Pop-Location
    if ($salida -match "denied|403") {
        No "GitHub rechaza el push — $(($salida -split 'remote: ')[-1])" "iniciar sesión en GitHub como ITCRC1"
    } elseif ($salida -match "Everything up-to-date|->") {
        Ok "GitHub acepta el push"
    } else { No "GitHub: respuesta inesperada" "revisar la sesión de GitHub" }
} else { No "no puedo probar GitHub sin el repo" "clonar primero" }

# ⚠️ Con qué cuenta empuja esta máquina. En la PC vieja quedó `Bismark1973`,
# que tenía permiso en Amarena y NO en los otros tres: ahí nacieron los 403.
$cred = (cmdkey /list 2>$null | Select-String "github" -Context 0,2) -join " "
if ($cred -match "Usuario:\s*(\S+)") {
    if ($Matches[1] -eq "ITCRC1") { Ok "Credencial de GitHub: ITCRC1 (la correcta)" }
    else { No "Credencial de GitHub guardada: $($Matches[1]) — debería ser ITCRC1" "borrar la credencial y entrar como ITCRC1" }
} else { Ok "No hay credencial de GitHub guardada (se pedirá al primer push)" }

if (Get-Command railway -ErrorAction SilentlyContinue) {
    $who = (railway whoami 2>&1) -join " "
    if ($who -match "Logged in") { Ok "Railway — $who" }
    else { No "Railway sin sesión" "correr: railway login" }
}

$llave = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
if (Test-Path $llave) { Ok "Clave SSH presente" }
else { No "sin clave SSH (hace falta SÓLO para 'railway ssh' a producción)" "generar la clave y registrarla en Railway" }

# ── 5 · Los dos secretos que no están en Git ─────────────────────────────────
Titulo "Archivos que no viajan por Git"
foreach ($r in @("FinPlan_Amarena","FinPlan_CWL")) {
    $e = Join-Path $Raiz "$r\backend\.env"
    if (Test-Path $e) { Ok "$r\backend\.env" }
    else { No "falta $r\backend\.env (trae SECRET_KEY)" "copiar el .env de $r desde la PC vieja" }
}

# ── 6 · Lo invisible: lo que Claude sabe de ESTE sistema ─────────────────────
Titulo "Contexto de Claude"
$mem = Join-Path $env:USERPROFILE ".claude\projects\C--dev-Ventanas\memory"
if (Test-Path $mem) {
    $n = (Get-ChildItem $mem -Filter *.md -ErrorAction SilentlyContinue).Count
    if ($n -ge 20) { Ok "Memoria de Claude: $n notas" }
    else { No "Memoria de Claude incompleta ($n notas; en la PC vieja son 33)" "copiar la carpeta de memoria" }
} else {
    No "Sin memoria de Claude — sabe programar, pero no conoce ESTE sistema" "copiar la carpeta de memoria"
}

# ── El veredicto ─────────────────────────────────────────────────────────────
Titulo "Resultado"
if ($falta.Count -eq 0) {
    Write-Host "  Esta PC está lista. Nada que hacer." -ForegroundColor Green
} else {
    Write-Host "  Faltan $($falta.Count) cosa(s):`n" -ForegroundColor Yellow
    $i = 1
    foreach ($f in $falta) { Write-Host "   $i. $f"; $i++ }
    Write-Host @"

  Casi todo lo resuelve el guion de al lado:
      .\NUEVA_PC.ps1

  Lo que ese guion NO puede hacer es iniciar sesión por vos (GitHub, Railway
  y la clave SSH) ni inventar los .env, que traen secretos.
"@ -ForegroundColor Gray
}

Write-Host @"

── Y las DOS cosas que no se ven en esta lista ──────────────────────────────

  A · LAS CARPETAS QUE CLAUDE TIENE PERMITIDAS
      Claude Code sólo puede tocar los directorios que le abriste. Si lo abrís
      parado en otra carpeta, no alcanza C:\dev\FinPlan_* y no es que "no
      quiera": no los ve. En la PC vieja esta sesión tenía habilitado
      C:\dev\FinPlan_Amarena ADEMÁS del proyecto principal.
      → Abrí Claude en C:\dev, o agregá las carpetas de los cuatro FinPlan.

  B · EL MODO DE PERMISOS
      Por omisión pide aprobación para cada comando. En la PC vieja las
      corridas largas iban en modo de permisos amplios, y por eso podía decir
      "¿lo aplico en los otros tres?" y hacerlo de una.
      → Si querés ese ritmo, hay que habilitarlo en la máquina nueva.

"@ -ForegroundColor Gray
