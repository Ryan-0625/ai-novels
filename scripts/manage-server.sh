#!/bin/bash
# 服务器管理脚本

PROJECT_DIR="e:\VScode(study)\Project\AI-Novels"

# 确保logs目录存在
mkdir -p "$PROJECT_DIR/logs"

# 启动服务器
start_server() {
    echo "Starting server on port 8006..."
    cd "$PROJECT_DIR"
    e:/Python/Python3.13/python -m uvicorn src.ai_novels.api.main:app \
        --host 0.0.0.0 --port 8006 --reload 2>&1 | tee "$PROJECT_DIR/logs/server.log"
}

# 测试任务
test_task() {
    echo "Creating test task..."
    curl -s -X POST "http://localhost:8006/api/v1/tasks" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "test_manual",
            "task_type": "novel",
            "genre": "fantasy",
            "title": "Manual Test",
            "description": "Manual test of workflow",
            "chapters": 2,
            "word_count_per_chapter": 1000
        }'
}

# 查看任务状态
task_status() {
    local task_id=$1
    curl -s "http://localhost:8006/api/v1/tasks/$task_id" | python -m json.tool
}

# 查看日志
show_logs() {
    tail -n 50 "$PROJECT_DIR/logs/server.log"
}

case "$1" in
    start)
        start_server
        ;;
    test)
        test_task
        ;;
    status)
        task_status "$2"
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|test|status <task_id>|logs}"
        exit 1
        ;;
esac
