<#
.SYNOPSIS
    Wallex Opportunity Agent Docker Helper Script for Windows
.DESCRIPTION
    Provides simple shortcuts to build, run, preflight, backtest, and report within Docker.
.EXAMPLE
    .\scripts\docker-helper.ps1 up
    .\scripts\docker-helper.ps1 preflight
    .\scripts\docker-helper.ps1 backtest 100
    .\scripts\docker-helper.ps1 report
    .\scripts\docker-helper.ps1 down
#>

param (
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("build", "up", "down", "logs", "preflight", "backtest", "report", "test", "restart", "help")]
    [string]$Command,

    [Parameter(Position = 1, Mandatory = $false)]
    [string]$Arg1
)

switch ($Command) {
    "build" {
        Write-Host "Building Wallex Opportunity Agent Docker Image..." -ForegroundColor Cyan
        docker compose build
    }
    "up" {
        Write-Host "Starting Agent in Shadow mode with Web Dashboard..." -ForegroundColor Green
        docker compose up -d
        Write-Host "Dashboard available at: http://localhost:8000" -ForegroundColor Yellow
    }
    "down" {
        Write-Host "Stopping Wallex Agent..." -ForegroundColor Yellow
        docker compose down
    }
    "logs" {
        docker compose logs -f app
    }
    "restart" {
        docker compose restart app
    }
    "preflight" {
        Write-Host "Running Preflight Verification within container..." -ForegroundColor Cyan
        docker compose run --rm app python -m wallex_agent preflight
    }
    "backtest" {
        $cycles = if ($Arg1) { $Arg1 } else { "50" }
        Write-Host "Running Backtest ($cycles cycles) within container..." -ForegroundColor Cyan
        docker compose run --rm app python -m wallex_agent backtest --cycles $cycles
    }
    "report" {
        Write-Host "Reading Telemetry Report from container volume..." -ForegroundColor Cyan
        docker compose run --rm app python -m wallex_agent report
    }
    "test" {
        Write-Host "Running automated test suite in container..." -ForegroundColor Cyan
        docker compose run --rm app python -m pytest tests/ -v
    }
    "help" {
        Write-Host "Available commands:" -ForegroundColor Green
        Write-Host "  build      - Build Docker image"
        Write-Host "  up         - Run agent in Shadow mode (daemon)"
        Write-Host "  down       - Stop running agent"
        Write-Host "  logs       - Follow agent container logs"
        Write-Host "  restart    - Restart agent container"
        Write-Host "  preflight  - Run preflight safety check"
        Write-Host "  backtest N - Run backtest for N cycles (default 50)"
        Write-Host "  report     - Display trade & loss audit report"
        Write-Host "  test       - Run test suite inside container"
    }
}
