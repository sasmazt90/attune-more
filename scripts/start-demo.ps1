<#
.SYNOPSIS
    Togg Health MVP - Tek Komutla Kolay Demo Başlatıcı (PowerShell)
.DESCRIPTION
    FastAPI Core API backend'ini (Port 8000) ve Next.js Vehicle App frontend'ini (Port 3000)
    ayrı pencerelerde başlatır.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          TOGG HEALTH MVP - DEMO BAŞLATICI                  " -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Proje Konumu: $ProjectRoot" -ForegroundColor Gray

$SecureRuntime = Join-Path $ProjectRoot '.runtime\security-20261008'
if (-not (Test-Path -LiteralPath (Join-Path $SecureRuntime 'fastapi'))) {
    throw 'Install scripts/install_security_runtime.py before starting TOGG.'
}
$env:PYTHONPATH = $SecureRuntime + [IO.Path]::PathSeparator + $env:PYTHONPATH

# 1. Backend Penceresini Başlat
$BackendDir = Join-Path $ProjectRoot "services\core-api"
$BackendCmd = "Set-Location '$BackendDir'; if (Test-Path '.venv\Scripts\activate.ps1') { & '.\.venv\Scripts\activate.ps1' }; Write-Host '>>> Core API Başlatılıyor (Port 8000)...' -ForegroundColor Green; python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

Write-Host "[1/2] Backend (Core API) ayrı pencerede başlatılıyor..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCmd

# 2. Frontend Penceresini Başlat
$FrontendDir = Join-Path $ProjectRoot "apps\vehicle-app"
$FrontendCmd = "Set-Location '$FrontendDir'; Write-Host '>>> Vehicle App Başlatılıyor (Port 3000)...' -ForegroundColor Green; npm run dev"

Write-Host "[2/2] Frontend (Vehicle App) ayrı pencerede başlatılıyor..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCmd

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "             SERVİSLER BAŞARIYLA BAŞLATILDI                 " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "🚗 Araç Kokpiti (UI):     http://localhost:3000" -ForegroundColor Cyan
Write-Host "🔌 Backend API:           http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 API Dokümantasyonu:    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🔒 Gizlilik ve Sıfırlama: http://localhost:3000/privacy" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Demo akışını durdurmak için açılan terminal pencerelerini kapatabilirsiniz." -ForegroundColor Gray
