# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    Deja una PC nueva lista para trabajar en los cuatro FinPlan.

.DESCRIPTION
    Owner, 2026-09-10: «me compré una computadora nueva… ¿qué debo llevar de acá
    para allá para que la compu conozca, instale, logre autorización, para que
    pueda trabajar con un click?».

    Instala las herramientas, clona los cuatro repos, arma los entornos y deja
    escrito lo único que NO puede hacer solo: las tres autorizaciones que exigen
    tu sesión (GitHub, Railway y la clave SSH).

    ⚠️ NO trae secretos. Los `.env` con `SECRET_KEY` y la clave SSH privada son
    lo único que se lleva a mano — ver la sección «LO QUE SÍ HAY QUE LLEVAR» al
    final de la corrida. Un secreto que viaja en un repositorio deja de ser un
    secreto.

.EXAMPLE
    Abrir PowerShell y correr:
        Set-ExecutionPolicy -Scope Process Bypass -Force
        .\NUEVA_PC.ps1

.NOTES
    Probado contra el inventario real de la PC vieja el 2026-09-10:
    git 2.55 · node 24.18 · npm 11.16 · railway CLI 5.30.1 · Python 3.12 en los
    venv (OJO: el Python del sistema era 3.14, y los proyectos NO usan ése).
#>
[CmdletBinding()]
param(
    # Dónde viven los clones. En la PC vieja es C:\dev.
    [string]$Raiz = "C:\dev",
    # Saltarse la instalación de herramientas (si ya están).
    [switch]$SoloRepos
)

$ErrorActionPreference = "Stop"

$REPOS = @(
    @{ nombre = "FinPlan_Amarena"; hotel = "Amarena Canvas Beach Hotel" }
    @{ nombre = "FinPlan_Oxygen";  hotel = "Oxygen Jungle Villas" }
    @{ nombre = "FinPlan_Gardens"; hotel = "Ojochal Gardens" }
    @{ nombre = "FinPlan_CWL";     hotel = "Corcovado Wilderness Lodge" }
)

function Titulo($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "  OK   $t" -ForegroundColor Green }
function Falta($t)  { Write-Host "  ---  $t" -ForegroundColor Yellow }
function Malo($t)   { Write-Host "  !!   $t" -ForegroundColor Red }

function Existe($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ── 1 · Las herramientas ─────────────────────────────────────────────────────
#
# ⚠️ Python **3.12**, no el más nuevo. Los venv de los cuatro proyectos están en
# 3.12 y varias dependencias todavía no publican rueda para 3.14 — instalar sólo
# la última deja `pip install` compilando desde fuente y fallando.
if (-not $SoloRepos) {
    Titulo "Herramientas"
    if (-not (Existe winget)) {
        Malo "No hay winget. Instalá las herramientas a mano: Git, Python 3.12, Node LTS y Railway CLI."
    } else {
        $paquetes = @(
            @{ id = "Git.Git";                 cmd = "git";     nota = "Git" }
            @{ id = "Python.Python.3.12";      cmd = $null;     nota = "Python 3.12 (los proyectos NO usan el 3.14)" }
            @{ id = "OpenJS.NodeJS.LTS";       cmd = "node";    nota = "Node LTS" }
            @{ id = "Railway.RailwayCLI";      cmd = "railway"; nota = "Railway CLI" }
            @{ id = "PostgreSQL.PostgreSQL.16";cmd = $null;     nota = "PostgreSQL 16 (sólo si vas a correr la base local)" }
        )
        foreach ($p in $paquetes) {
            if ($p.cmd -and (Existe $p.cmd)) { Ok "$($p.nota) ya estaba"; continue }
            Write-Host "  ...  instalando $($p.nota)"
            winget install --id $p.id --silent --accept-package-agreements --accept-source-agreements | Out-Null
            Ok $p.nota
        }
    }
    Falta "Claude Code: se instala aparte, desde la app de escritorio o claude.com/code"
}

# ── 2 · Los repos ────────────────────────────────────────────────────────────
#
# Desde el 2026-09-09 los cuatro están completos en GitHub, así que NO hay que
# copiar carpetas de la PC vieja: se clonan. Antes de esa fecha esto no era
# posible y había 63 commits que vivían en un solo disco.
Titulo "Repos"
New-Item -ItemType Directory -Force -Path $Raiz | Out-Null
foreach ($r in $REPOS) {
    $destino = Join-Path $Raiz $r.nombre
    if (Test-Path (Join-Path $destino ".git")) { Ok "$($r.nombre) ya estaba clonado"; continue }
    Write-Host "  ...  clonando $($r.nombre)"
    git clone "https://github.com/ITCRC1/$($r.nombre).git" $destino
    Ok $r.nombre
}

# ── 3 · Los entornos ─────────────────────────────────────────────────────────
Titulo "Entornos de Python y Node"
$py312 = $null
foreach ($cand in @("py -3.12", "python3.12", "python")) {
    try {
        $v = & ([scriptblock]::Create("$cand --version")) 2>&1
        if ("$v" -match "3\.12") { $py312 = $cand; break }
    } catch { }
}
if (-not $py312) {
    Malo "No encontré Python 3.12. Instalalo y volvé a correr con -SoloRepos."
} else {
    Ok "Python 3.12: $py312"
    foreach ($r in $REPOS) {
        $back = Join-Path $Raiz "$($r.nombre)\backend"
        if (-not (Test-Path $back)) { continue }
        $venv = Join-Path $back ".venv"
        if (-not (Test-Path $venv)) {
            Write-Host "  ...  venv de $($r.nombre)"
            Push-Location $back
            & ([scriptblock]::Create("$py312 -m venv .venv"))
            & "$venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
            & "$venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
            Pop-Location
        }
        Ok "$($r.nombre) backend"
    }
    foreach ($r in $REPOS) {
        $front = Join-Path $Raiz "$($r.nombre)\frontend"
        if (-not (Test-Path $front)) { continue }
        if (-not (Test-Path (Join-Path $front "node_modules"))) {
            Write-Host "  ...  npm ci de $($r.nombre) (tarda)"
            Push-Location $front; npm ci --silent; Pop-Location
        }
        Ok "$($r.nombre) frontend"
    }
}

# ── 4 · Lo que el guion NO puede hacer solo ──────────────────────────────────
Titulo "LO QUE FALTA — son tres autorizaciones y dos archivos"

Write-Host @"

  1 · GITHUB — iniciá sesión como ITCRC1, no como otra cuenta
      La primera vez que hagas `git push`, Windows abre el navegador.
      ⚠️ Entrá con ITCRC1 (Finance@thecostaricacollection.com).

      ⚠️⚠️ NO copies la credencial guardada de la PC vieja. Ahí quedó
      almacenada la cuenta `Bismark1973`, que tenía permiso en Amarena y NO
      en los otros tres: eso costó un día entero de 403 el 2026-09-09.
      Empezar limpio en la máquina nueva evita heredar el problema.

      Para comprobar que quedó bien, sin subir nada:
          cd $Raiz\FinPlan_Oxygen
          git push --dry-run origin HEAD

  2 · RAILWAY — una sola vez, abre el navegador
          railway login
      La cuenta es brodriguez7301@gmail.com.

  3 · CLAVE SSH — hace falta para entrar a las bases de producción
      Sin ella funciona todo MENOS `railway ssh` (que es como se leen y
      corrigen datos en producción sin contraseñas).

      Dos caminos:
      (a) Generar una nueva acá y registrarla en Railway (recomendado):
              ssh-keygen -t ed25519 -C "pc-nueva"
          y después pegar el contenido de %USERPROFILE%\.ssh\id_ed25519.pub
          en Railway → Account Settings → SSH Keys.
      (b) Llevar la de la PC vieja: %USERPROFILE%\.ssh\id_ed25519 y su .pub
          (en la vieja está registrada como 'ventanas-pc-claude').

  4 · LOS .env DEL BACKEND — esto SÍ hay que llevarlo a mano
      No están en Git a propósito: traen SECRET_KEY.
      Copiá de la PC vieja:
          C:\dev\FinPlan_Amarena\backend\.env
          C:\dev\FinPlan_CWL\backend\.env
      (Oxygen y Gardens no tenían .env local.)

      Amarena lleva: DATABASE_URL, SECRET_KEY, DATA_DIR, HOTEL_ID, HOTEL_NAME,
      HOTEL_SHORT_NAME, HOTEL_ROOMS, HOTEL_TC_USD, CORS_ORIGINS.

  5 · LA MEMORIA DE CLAUDE — es lo que hace que baste UNA instrucción
      Copiá la carpeta entera:
          C:\Users\<vos>\.claude\projects\C--dev-Ventanas\memory\
      Son 33 notas con las trampas aprendidas: los nombres exactos de los
      servicios de Railway, por qué el front de Oxygen se sube desde la raíz
      del repo y el de Gardens desde frontend/, el descarte silencioso del
      mapeo, que recalculate_scenario hace su propio commit… Sin eso, la
      máquina nueva sabe programar pero no conoce ESTE sistema.

"@ -ForegroundColor Gray

Titulo "Comprobación final"
Write-Host "  Corré esto y las cuatro suites tienen que dar verde:`n"
foreach ($r in $REPOS) {
    Write-Host "      cd $Raiz\$($r.nombre)\backend; .\.venv\Scripts\python.exe -m pytest -q"
}
Write-Host ""
