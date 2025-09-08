# Poneglyph Complete System Manager for Windows
# PowerShell script to manage the complete MapReduce system

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "start", "stop", "status", "test", "logs", "clean", "help")]
    [string]$Action = "help"
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = "docker-compose.complete.yml"

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 50) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 50) -ForegroundColor Cyan
    Write-Host ""
}

function Test-DockerCompose {
    try {
        docker-compose --version | Out-Null
        return $true
    }
    catch {
        Write-Host "❌ Docker Compose not found. Please install Docker Desktop." -ForegroundColor Red
        return $false
    }
}

function Test-Docker {
    try {
        docker --version | Out-Null
        docker ps | Out-Null
        return $true
    }
    catch {
        Write-Host "❌ Docker not running. Please start Docker Desktop." -ForegroundColor Red
        return $false
    }
}

function Build-System {
    Write-Header "BUILDING PONEGLYPH SYSTEM"
    
    Write-Host "🔨 Building all Docker images..." -ForegroundColor Yellow
    
    try {
        docker-compose -f $ComposeFile build
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ All images built successfully!" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Build failed!" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Build error: $_" -ForegroundColor Red
        return $false
    }
}

function Start-System {
    Write-Header "STARTING PONEGLYPH SYSTEM"
    
    Write-Host "🚀 Starting all services..." -ForegroundColor Yellow
    
    try {
        docker-compose -f $ComposeFile up -d
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ All services started!" -ForegroundColor Green
            Write-Host ""
            Write-Host "📋 Service URLs:" -ForegroundColor Cyan
            Write-Host "  • Java Master: http://localhost:8080"
            Write-Host "  • gRPC Middleware: localhost:50051"
            Write-Host "  • RabbitMQ Management: http://localhost:15672 (poneglyph/poneglyph123)"
            Write-Host "  • Redis: localhost:6379"
            Write-Host "  • Dashboard: http://localhost:80"
            return $true
        } else {
            Write-Host "❌ Failed to start services!" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Start error: $_" -ForegroundColor Red
        return $false
    }
}

function Stop-System {
    Write-Header "STOPPING PONEGLYPH SYSTEM"
    
    Write-Host "🛑 Stopping all services..." -ForegroundColor Yellow
    
    try {
        docker-compose -f $ComposeFile down
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ All services stopped!" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Failed to stop services!" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Stop error: $_" -ForegroundColor Red
        return $false
    }
}

function Show-Status {
    Write-Header "PONEGLYPH SYSTEM STATUS"
    
    Write-Host "📊 Container Status:" -ForegroundColor Cyan
    docker-compose -f $ComposeFile ps
    
    Write-Host ""
    Write-Host "🔍 Service Health:" -ForegroundColor Cyan
    
    # Test gRPC Middleware
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ConnectAsync("localhost", 50051).Wait(3000)
        if ($tcpClient.Connected) {
            Write-Host "  ✅ gRPC Middleware (port 50051): HEALTHY" -ForegroundColor Green
        } else {
            Write-Host "  ❌ gRPC Middleware (port 50051): NOT ACCESSIBLE" -ForegroundColor Red
        }
        $tcpClient.Close()
    }
    catch {
        Write-Host "  ❌ gRPC Middleware (port 50051): NOT ACCESSIBLE" -ForegroundColor Red
    }
    
    # Test RabbitMQ
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:15672" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "  ✅ RabbitMQ Management (port 15672): HEALTHY" -ForegroundColor Green
    }
    catch {
        Write-Host "  ❌ RabbitMQ Management (port 15672): NOT ACCESSIBLE" -ForegroundColor Red
    }
    
    # Test Redis
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ConnectAsync("localhost", 6379).Wait(3000)
        if ($tcpClient.Connected) {
            Write-Host "  ✅ Redis (port 6379): HEALTHY" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Redis (port 6379): NOT ACCESSIBLE" -ForegroundColor Red
        }
        $tcpClient.Close()
    }
    catch {
        Write-Host "  ❌ Redis (port 6379): NOT ACCESSIBLE" -ForegroundColor Red
    }
}

function Show-Logs {
    Write-Header "PONEGLYPH SYSTEM LOGS"
    
    $services = @("middleware", "worker1", "worker2", "worker3", "master", "rabbitmq", "redis")
    
    foreach ($service in $services) {
        Write-Host ""
        Write-Host "--- $($service.ToUpper()) LOGS ---" -ForegroundColor Cyan
        docker-compose -f $ComposeFile logs --tail=15 $service
    }
}

function Test-System {
    Write-Header "TESTING PONEGLYPH SYSTEM"
    
    Write-Host "🧪 Running integration tests..." -ForegroundColor Yellow
    
    # Check if Python test script exists
    $testScript = Join-Path $ProjectRoot "test_complete_system.py"
    if (Test-Path $testScript) {
        python $testScript
    } else {
        Write-Host "⚠️  Python test script not found. Running basic connectivity tests..." -ForegroundColor Yellow
        Show-Status
    }
}

function Clean-System {
    Write-Header "CLEANING PONEGLYPH SYSTEM"
    
    Write-Host "🧹 Removing containers, networks, and volumes..." -ForegroundColor Yellow
    
    try {
        docker-compose -f $ComposeFile down --volumes --remove-orphans
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ System cleaned successfully!" -ForegroundColor Green
            
            # Optional: Remove images
            $response = Read-Host "Do you want to remove Docker images as well? (y/N)"
            if ($response -eq "y" -or $response -eq "Y") {
                docker-compose -f $ComposeFile down --rmi all --volumes --remove-orphans
                Write-Host "✅ Images removed!" -ForegroundColor Green
            }
            return $true
        } else {
            Write-Host "❌ Failed to clean system!" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Clean error: $_" -ForegroundColor Red
        return $false
    }
}

function Show-Help {
    Write-Header "PONEGLYPH SYSTEM MANAGER"
    
    Write-Host "📋 Available Commands:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  build   - Build all Docker images" -ForegroundColor White
    Write-Host "  start   - Start the complete system" -ForegroundColor White
    Write-Host "  stop    - Stop all services" -ForegroundColor White
    Write-Host "  status  - Show system status and health" -ForegroundColor White
    Write-Host "  test    - Run integration tests" -ForegroundColor White
    Write-Host "  logs    - Show logs from all services" -ForegroundColor White
    Write-Host "  clean   - Remove containers and volumes" -ForegroundColor White
    Write-Host "  help    - Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "📖 Example Usage:" -ForegroundColor Cyan
    Write-Host "  .\manage.ps1 build    # Build the system"
    Write-Host "  .\manage.ps1 start    # Start all services"
    Write-Host "  .\manage.ps1 status   # Check system health"
    Write-Host "  .\manage.ps1 test     # Run tests"
    Write-Host "  .\manage.ps1 stop     # Stop everything"
    Write-Host ""
    Write-Host "🎯 Quick Start:" -ForegroundColor Cyan
    Write-Host "  1. .\manage.ps1 build"
    Write-Host "  2. .\manage.ps1 start"
    Write-Host "  3. .\manage.ps1 test"
    Write-Host ""
}

# Main execution
try {
    Set-Location $ProjectRoot
    
    # Check prerequisites
    if (-not (Test-Docker)) {
        exit 1
    }
    
    if (-not (Test-DockerCompose)) {
        exit 1
    }
    
    # Execute the requested action
    switch ($Action) {
        "build" { 
            $success = Build-System
            if (-not $success) { exit 1 }
        }
        "start" { 
            $success = Start-System
            if (-not $success) { exit 1 }
        }
        "stop" { 
            $success = Stop-System
            if (-not $success) { exit 1 }
        }
        "status" { 
            Show-Status 
        }
        "test" { 
            Test-System 
        }
        "logs" { 
            Show-Logs 
        }
        "clean" { 
            $success = Clean-System
            if (-not $success) { exit 1 }
        }
        "help" { 
            Show-Help 
        }
        default { 
            Show-Help 
        }
    }
    
    Write-Host ""
    Write-Host "🎉 Operation completed successfully!" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
}
