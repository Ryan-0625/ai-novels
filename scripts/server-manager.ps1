#!/usr/bin/env pwsh
"""
服务器进程管理脚本

功能：
- 启动服务器
- 停止服务器
- 重启服务器
- 查看服务器状态
"""

param(
    [Parameter(Mandatory=$true)][ValidateSet('start', 'stop', 'restart', 'status', 'kill')][string]$Action,
    [int]$Port = 8004,
    [string]$ProjectDir = "e:\VScode(study)\Project\AI-Novels"
)

# 切换到项目目录
Set-Location -Path $ProjectDir

function Get-ServerProcess {
    param([int]$Port)
    $processId = netstat -ano | Select-String ":$Port " | ForEach-Object {
        $_.Line.Split(' ')[-1]
    }
    if ($processId) {
        return Get-Process -Id $processId -ErrorAction SilentlyContinue
    }
    return $null
}

function Stop-Server {
    param([int]$Port)

    $process = Get-ServerProcess -Port $Port
    if ($process) {
        Write-Host "找到服务器进程: $($process.ProcessName) (PID: $($process.Id))"

        # 尝试优雅停止
        Write-Host "正在停止服务器..."
        Stop-Process -Id $process.Id -Force
        Start-Sleep -Seconds 2

        # 验证是否停止
        if (!(Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
            Write-Host "服务器已停止"
            return $true
        }

        # 强制终止
        Write-Host "强制终止进程..."
        Stop-Process -Id $process.Id -Force
        Start-Sleep -Seconds 1
        return $true
    }

    Write-Host "未找到端口 $Port 上运行的服务器进程"
    return $true
}

function Start-Server {
    param([int]$Port)

    # 检查是否已在运行
    $existing = Get-ServerProcess -Port $Port
    if ($existing) {
        Write-Host "服务器已在运行 (PID: $($existing.Id))"
        return $true
    }

    Write-Host "正在启动服务器 on port $Port..."
    Write-Host "执行命令: uvicorn src.ai_novels.api.main:app --host 0.0.0.0 --port $Port --reload"

    # 启动服务器（后台）
    Start-Process -FilePath "uvicorn" `
        -ArgumentList "src.ai_novels.api.main:app", "--host", "0.0.0.0", "--port", $Port, "--reload" `
        -NoNewWindow `
        -RedirectStandardOutput "$ProjectDir/logs/server.log" `
        -RedirectStandardError "$ProjectDir/logs/server-error.log" `
        -PassThru

    Write-Host "服务器启动中... 等待10秒..."
    Start-Sleep -Seconds 10

    # 验证启动
    $process = Get-ServerProcess -Port $Port
    if ($process) {
        Write-Host "服务器启动成功 (PID: $($process.Id))"
        return $true
    }

    Write-Host "服务器启动失败，请查看日志文件"
    return $false
}

function Get-ServerStatus {
    param([int]$Port)

    $process = Get-ServerProcess -Port $Port
    if ($process) {
        Write-Host "服务器正在运行:"
        Write-Host "  进程名: $($process.ProcessName)"
        Write-Host "  PID: $($process.Id)"
        Write-Host "  端口: $Port"
        Write-Host "  状态: 运行中"

        # 测试API
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response) {
                Write-Host "  API: 健康"
            }
        } catch {
            Write-Host "  API: 无响应"
        }

        return "running"
    }

    Write-Host "服务器未运行在端口 $Port"
    return "stopped"
}

# 主逻辑
switch ($Action) {
    "start" {
        Start-Server -Port $Port
    }
    "stop" {
        Stop-Server -Port $Port
    }
    "restart" {
        Write-Host "重启服务器..."
        Stop-Server -Port $Port
        Start-Sleep -Seconds 2
        Start-Server -Port $Port
    }
    "status" {
        Get-ServerStatus -Port $Port
    }
    "kill" {
        $process = Get-ServerProcess -Port $Port
        if ($process) {
            Write-Host "强制终止进程 $($process.Id)..."
            Stop-Process -Id $process.Id -Force
            Write-Host "进程已终止"
        }
    }
}
