#!/usr/bin/env python3
"""
Requirements 版本驗證腳本
在部署前檢查所有依賴是否可以正確安裝
"""
import subprocess
import sys
import tempfile
import os

def check_requirements():
    """檢查 requirements.txt 中的所有套件是否可以安裝"""
    print("🔍 檢查 requirements.txt 中的套件版本...")
    
    try:
        # 使用 pip 的 dry-run 功能檢查依賴
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', 
            '--dry-run', '--quiet', '--no-deps', 
            '-r', 'requirements.txt'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ 所有套件版本檢查通過！")
            return True
        else:
            print("❌ 發現版本問題：")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ 檢查超時，可能網路較慢")
        return False
    except Exception as e:
        print(f"❌ 檢查過程發生錯誤: {e}")
        return False

def check_critical_packages():
    """檢查關鍵套件的可用性"""
    critical_packages = [
        'line-bot-sdk==3.12.0',
        'flask==3.1.0',
        'gunicorn==23.0.0',
        'cloudinary==1.41.0',
        'google-cloud-aiplatform==1.71.1'
    ]
    
    print("\n🎯 檢查關鍵套件...")
    
    for package in critical_packages:
        try:
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', 
                '--dry-run', '--quiet', package
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"✅ {package}")
            else:
                print(f"❌ {package} - {result.stderr.strip()}")
                return False
                
        except Exception as e:
            print(f"❌ {package} - 檢查失敗: {e}")
            return False
    
    return True

def main():
    """主函數"""
    print("🚀 LINE Bot Requirements 版本驗證")
    print("=" * 50)
    
    # 檢查是否在正確的目錄
    if not os.path.exists('requirements.txt'):
        print("❌ 找不到 requirements.txt 檔案")
        print("請確保在 linebot 目錄中執行此腳本")
        sys.exit(1)
    
    # 檢查關鍵套件
    if not check_critical_packages():
        print("\n❌ 關鍵套件檢查失敗")
        sys.exit(1)
    
    # 檢查完整 requirements
    if not check_requirements():
        print("\n❌ Requirements 檢查失敗")
        print("\n💡 建議解決方案：")
        print("1. 檢查網路連線")
        print("2. 更新 pip: python -m pip install --upgrade pip")
        print("3. 檢查 requirements.txt 格式")
        sys.exit(1)
    
    print("\n🎉 所有檢查通過！可以安全部署到 Render")
    print("\n📋 下一步：")
    print("1. 提交程式碼到 GitHub")
    print("2. 在 Render 建立 Web Service")
    print("3. 設定環境變數")
    print("4. 部署並測試")

if __name__ == "__main__":
    main()