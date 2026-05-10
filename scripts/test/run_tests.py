#!/usr/bin/env python
"""
测试运行器 - 执行项目测试套件
"""
import sys
import os
import subprocess

# 添加 src 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_tests():
    """运行所有测试"""
    # 设置环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.join(os.path.dirname(__file__), 'src')
    
    # 运行 pytest
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short'],
        cwd=os.path.dirname(__file__),
        env=env,
        capture_output=True,
        text=True
    )
    
    print("STDOUT:")
    print(result.stdout)
    print("\nSTDERR:")
    print(result.stderr)
    print(f"\nReturn code: {result.returncode}")
    
    return result.returncode

if __name__ == '__main__':
    sys.exit(run_tests())
