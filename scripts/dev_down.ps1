# PowerShell dev helper script - bring down services
# Usage: .\dev_down.ps1

Write-Host "🛑 Stopping Jeevn dev services..."

docker compose -f infra/docker-compose.example.yml down -v

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Services stopped successfully"
} else {
    Write-Host "❌ Failed to stop services"
    exit 1
}
