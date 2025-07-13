#!/usr/bin/env python3
"""
依賴修復腳本
檢查和修復常見的依賴問題
"""
import subprocess
import sys
import platform

def check_python_version():
    """檢查 Python 版本"""
    version = platform.python_version()
    print(f"Python 版本: {version}")
    
    if version.startswith("3.13"):
        print("⚠️  警告: Python 3.13 可能有相容性問題")
        print("建議使用 Python 3.11 或 3.12")
        return False
    return True

def install_build_tools():
    """安裝構建工具"""
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "--upgrade", "pip", "wheel", "setuptools"
        ], check=True)
        print("✅ 構建工具安裝成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 構建工具安裝失敗: {e}")
        return False

def test_pillow_installation():
    """測試 Pillow 安裝"""
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "Pillow==10.4.0", "--no-cache-dir"
        ], check=True)
        print("✅ Pillow 安裝成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Pillow 安裝失敗: {e}")
        return False

def main():
    """主函式"""
    print("🔧 開始依賴修復...")
    
    if not check_python_version():
        print("建議切換到 Python 3.11")
    
    if not install_build_tools():
        sys.exit(1)
    
    if not test_pillow_installation():
        print("嘗試安裝較舊版本的 Pillow...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "Pillow==9.5.0", "--no-cache-dir"
            ], check=True)
            print("✅ Pillow 9.5.0 安裝成功")
        except subprocess.CalledProcessError:
            print("❌ 所有 Pillow 版本都安裝失敗")
            sys.exit(1)
    
    print("🎉 依賴修復完成！")

if __name__ == "__main__":
    main()