# PowerShell dev helper script - bring up services
# Usage: .\dev_up.ps1

Write-Host "🚀 Starting Jeevn dev services..."

# Check if docker compose is available
$dockerCompose = docker compose --version 2>$null
if (-not $dockerCompose) {
    Write-Host "❌ Docker Compose not found. Please install Docker Desktop."
    exit 1
}

Write-Host "📦 Starting containers..."
docker compose -f infra/docker-compose.example.yml up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Services started successfully"
    Write-Host ""
    Write-Host "Services running:"
    Write-Host "  - API: http://localhost:8000"
    Write-Host "  - Streamlit UI: Run 'streamlit run src/jeevn/ui/app.py'"
    Write-Host "  - Postgres: localhost:5432"
    Write-Host "  - MinIO: http://localhost:9001"
} else {
    Write-Host "❌ Failed to start services"
    exit 1
}
