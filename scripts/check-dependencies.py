#!/usr/bin/env python3
"""
依賴檢查腳本
檢查並解決常見的依賴衝突問題
"""
import subprocess
import sys
import json
from typing import Dict, List, Tuple

def check_package_conflicts() -> List[Tuple[str, str, str]]:
    """檢查套件衝突"""
    conflicts = []
    
    # 已知的衝突組合
    known_conflicts = [
        ("line-bot-sdk", "3.12.0", "requests", ">=2.32.3"),
        ("google-cloud-aiplatform", "1.42.1", "urllib3", ">=2.0.0"),
    ]
    
    print("🔍 檢查已知的依賴衝突...")
    for pkg1, ver1, pkg2, ver2 in known_conflicts:
        print(f"  ✅ {pkg1} {ver1} 需要 {pkg2} {ver2}")
    
    return conflicts

def get_package_info(package_name: str) -> Dict:
    """取得套件資訊"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "show", package_name
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            return info
        return {}
    except Exception:
        return {}

def test_installation(requirements_file: str) -> bool:
    """測試安裝需求檔案"""
    print(f"🧪 測試安裝 {requirements_file}...")
    
    try:
        # 建立虛擬環境進行測試
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--dry-run", 
            "-r", requirements_file
        ], check=True, capture_output=True)
        
        print(f"  ✅ {requirements_file} 相容性測試通過")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ {requirements_file} 測試失敗:")
        print(f"     {e.stderr.decode()}")
        return False

def generate_compatible_requirements() -> None:
    """生成相容的需求檔案"""
    print("🔧 生成相容的需求檔案...")
    
    # 基本套件（不指定次要版本）
    base_packages = [
        "line-bot-sdk==3.12.0",
        "flask>=3.0.0,<4.0.0",
        "google-cloud-aiplatform>=1.40.0,<2.0.0",
        "cloudinary>=1.40.0,<2.0.0",
        "Pillow>=10.0.0,<11.0.0",
        "redis>=5.0.0,<6.0.0",
        "gunicorn>=21.0.0,<22.0.0",
    ]
    
    with open("requirements-auto.txt", "w") as f:
        f.write("# 自動生成的相容需求檔案\n")
        f.write("# 使用範圍版本避免衝突\n\n")
        for package in base_packages:
            f.write(f"{package}\n")
    
    print("  ✅ 已生成 requirements-auto.txt")

def main():
    """主函式"""
    print("🔍 開始依賴檢查...")
    
    # 檢查衝突
    conflicts = check_package_conflicts()
    
    # 測試不同的需求檔案
    test_files = [
        "requirements.txt",
        "requirements-safe.txt", 
        "requirements-minimal.txt"
    ]
    
    working_files = []
    for file in test_files:
        try:
            if test_installation(file):
                working_files.append(file)
        except FileNotFoundError:
            print(f"  ⚠️  檔案 {file} 不存在")
    
    if working_files:
        print(f"\n✅ 可用的需求檔案: {', '.join(working_files)}")
        print(f"建議使用: {working_files[0]}")
    else:
        print("\n❌ 所有需求檔案都有問題，生成新的相容版本...")
        generate_compatible_requirements()
        
        if test_installation("requirements-auto.txt"):
            print("✅ 自動生成的需求檔案可用")
        else:
            print("❌ 無法解決依賴衝突，請手動檢查")

if __name__ == "__main__":
    main()