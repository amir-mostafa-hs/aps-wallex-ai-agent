#!/usr/bin/env bash
set -e

COMMAND="${1:-help}"
ARG1="${2:-50}"

case "$COMMAND" in
    build)
        echo "Building Wallex Opportunity Agent Docker Image..."
        docker compose build
        ;;
    up)
        echo "Starting Agent in Shadow mode with Web Dashboard..."
        docker compose up -d
        echo "Dashboard available at: http://localhost:8000"
        ;;
    down)
        echo "Stopping Wallex Agent..."
        docker compose down
        ;;
    logs)
        docker compose logs -f app
        ;;
    restart)
        docker compose restart app
        ;;
    preflight)
        echo "Running Preflight Verification within container..."
        docker compose run --rm app python -m wallex_agent preflight
        ;;
    backtest)
        echo "Running Backtest ($ARG1 cycles) within container..."
        docker compose run --rm app python -m wallex_agent backtest --cycles "$ARG1"
        ;;
    report)
        echo "Reading Telemetry Report from container volume..."
        docker compose run --rm app python -m wallex_agent report
        ;;
    test)
        echo "Running automated test suite in container..."
        docker compose run --rm app python -m pytest tests/ -v
        ;;
    help|*)
        echo "Usage: ./scripts/docker-helper.sh [command]"
        echo ""
        echo "Available commands:"
        echo "  build       Build Docker image"
        echo "  up          Run agent in Shadow mode (daemon)"
        echo "  down        Stop running agent"
        echo "  logs        Follow agent container logs"
        echo "  restart     Restart agent container"
        echo "  preflight   Run preflight safety check"
        echo "  backtest N  Run backtest for N cycles (default 50)"
        echo "  report      Display trade & loss audit report"
        echo "  test        Run test suite inside container"
        ;;
esac
