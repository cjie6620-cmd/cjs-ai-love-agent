# dev_run.ps1
# 开发启动脚本：启动前自动清理残留 uvicorn 进程与 8000 端口，避免 Windows 下
# reloader 异常退出后端口僵死（socket 引用已不存在的 PID，导致新进程请求挂起）。
#
# 使用方式：
#   PS> .\scripts\dev_run.ps1
#   PS> .\scripts\dev_run.ps1 -Port 8001
#
# 依赖：PowerShell 5.1+、.venv 已激活或 python 在 PATH 中。

[CmdletBinding()]
param(
    # 监听端口，默认 8000
    [int]$Port = 8000,
    # FastAPI 应用入口
    [string]$App = "app:app",
    # 是否启用 --reload
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

Write-Host "==> [1/3] 清理端口 $Port 上的残留进程..." -ForegroundColor Cyan

# 查找所有占用目标端口的进程 PID
$occupyingPids = @()
try {
    $occupyingPids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
} catch {
    Write-Host "   跳过 Get-NetTCPConnection 查询: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 逐个尝试停止进程；忽略已经不存在的 PID
foreach ($targetPid in $occupyingPids) {
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction Stop
        Write-Host "   已杀死 PID=$targetPid" -ForegroundColor Green
    } catch {
        Write-Host "   PID=$targetPid 已失效或无权限，跳过" -ForegroundColor Yellow
    }
}

# 额外兜底：杀掉所有残留的 python.exe 中命令行包含 uvicorn/app:app 的进程
$stalePythons = Get-CimInstance -ClassName Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "uvicorn|app:app" }

foreach ($proc in $stalePythons) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        Write-Host "   已杀死残留 uvicorn 进程 PID=$($proc.ProcessId)" -ForegroundColor Green
    } catch {
        Write-Host "   PID=$($proc.ProcessId) 清理失败，跳过" -ForegroundColor Yellow
    }
}

Start-Sleep -Seconds 1

Write-Host "==> [2/3] 校验端口 $Port 是否释放..." -ForegroundColor Cyan
$stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($stillListening) {
    Write-Host "   端口 $Port 仍被占用，可能是 Windows 僵尸 socket（PID 已不存在但内核未释放）" -ForegroundColor Red
    Write-Host "   建议：使用其他端口（例如 -Port 8001）或重启 Windows" -ForegroundColor Red
    exit 1
} else {
    Write-Host "   端口 $Port 已空闲" -ForegroundColor Green
}

Write-Host "==> [3/3] 启动 uvicorn ..." -ForegroundColor Cyan
$reloadFlag = if ($NoReload.IsPresent) { @() } else { @("--reload") }

# 启动 uvicorn，把参数拼齐后交给 python -m uvicorn
$uvicornArgs = @("-m", "uvicorn", $App, "--host", "127.0.0.1", "--port", "$Port") + $reloadFlag
& python @uvicornArgs
