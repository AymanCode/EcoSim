$ErrorActionPreference = "Stop"

docker compose up --build -d

Write-Host ""
Write-Host "EcoSim is starting." -ForegroundColor Cyan
Write-Host "Dashboard: http://localhost:5173" -ForegroundColor Green
Write-Host "Health:    http://localhost:5173/health" -ForegroundColor Green
Write-Host ""
Write-Host "To stop the stack:" -ForegroundColor Yellow
Write-Host "docker compose down"
