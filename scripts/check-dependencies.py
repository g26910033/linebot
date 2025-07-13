#!/usr/bin/env python3
"""
依賴檢查腳本
檢查並解決常見的依賴衝突問題
"""
import subprocess
import sys
from typing import List

# --- Constants --- #
REQUIREMENTS_AUTO_FILE = "requirements-auto.txt"
TEST_REQUIREMENTS_FILES = [
    "requirements.txt",
    "requirements-safe.txt", 
    "requirements-minimal.txt"
]

# 基本套件，使用已知的建議版本範圍以提高兼容性。
# 這些版本範圍是基於常見的穩定性和兼容性考慮而設定的。
BASE_PACKAGES = [
    "line-bot-sdk>=3.12.0,<4.0.0",
    "flask>=3.0.0,<4.0.0",
    "google-cloud-aiplatform>=1.40.0,<2.0.0",
    "cloudinary>=1.40.0,<2.0.0",
    "Pillow>=10.0.0,<11.0.0",
    "redis>=5.0.0,<6.0.0",
    "gunicorn>=21.0.0,<22.0.0",
    "requests>=2.32.3", # 常見依賴問題源，明確指定較新版本
    "urllib3>=2.0.0",   # 常見依賴問題源，明確指定較新版本
]

# --- Functions --- #

def check_package_conflicts() -> List[str]:
    """
    檢查已安裝套件的依賴衝突。
    使用 `pip check` 找出不相容的套件。
    """
    print("🔍 執行 pip check 檢查已安裝套件的依賴衝突...")
    try:
        # pip check returns non-zero on conflicts and prints details to stdout
        result = subprocess.run([sys.executable, "-m", "pip", "check"],
                                capture_output=True, text=True, check=False)

        if result.returncode != 0:
            conflicts = result.stdout.strip().split('\n')
            print("❌ 檢測到依賴衝突:", file=sys.stderr)
            for conflict in conflicts:
                print(f"  - {conflict}", file=sys.stderr)
            return conflicts
        else:
            print("✅ 未檢測到已安裝套件的依賴衝突 (pip check)。")
            return []
    except Exception as e:
        print(f"⚠️ 執行 pip check 時發生錯誤: {e}", file=sys.stderr)
        return [f"Error running pip check: {e}"]

def test_installation(requirements_file: str) -> bool:
    """
    測試安裝需求檔案。
    使用 `pip install --dry-run` 模擬安裝並檢查兼容性。
    """
    print(f"🧪 測試安裝 {requirements_file}...")
    
    try:
        # 使用 --dry-run 模擬安裝，不實際修改環境，只檢查依賴解析
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--dry-run", 
            "-r", requirements_file
        ], check=True, capture_output=True, text=True)
        
        print(f"  ✅ {requirements_file} 相容性測試通過")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ {requirements_file} 測試失敗:", file=sys.stderr)
        print(f"     錯誤碼: {e.returncode}", file=sys.stderr)
        print(f"     標準輸出:\n{e.stdout}", file=sys.stderr)
        print(f"     錯誤輸出:\n{e.stderr}", file=sys.stderr) # 打印標準錯誤以獲取更多信息
        return False
    except FileNotFoundError:
        print(f"  ⚠️  錯誤: 需求檔案 '{requirements_file}' 不存在。", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ❌ 測試 {requirements_file} 時發生未知錯誤: {e}", file=sys.stderr)
        return False

def generate_compatible_requirements() -> None:
    """
    生成一份帶有常見版本範圍的 `requirements-auto.txt`。
    這是一個啟發式方法，旨在提供一個基本的、可能相容的依賴集合。
    它不執行複雜的依賴解析，而是基於常見的兼容性建議。
    """
    print(f"🔧 嘗試生成一份啟發式相容需求檔案 `{REQUIREMENTS_AUTO_FILE}`...")
    
    try:
        with open(REQUIREMENTS_AUTO_FILE, "w") as f:
            f.write("# 自動生成的相容需求檔案\n")
            f.write("# 這些版本範圍是基於常見的穩定性和兼容性考慮而設定的。\n")
            f.write("# 它不執行複雜的依賴解析，僅提供一個啟發式基礎。\n\n")
            for package in BASE_PACKAGES:
                f.write(f"{package}\n")
        
        print(f"  ✅ 已生成 {REQUIREMENTS_AUTO_FILE}")
    except IOError as e:
        print(f"  ❌ 無法寫入 {REQUIREMENTS_AUTO_FILE} 檔案: {e}", file=sys.stderr)

def main():
    """主函式"""
    print("🚀 開始執行專案依賴檢查和優化...")
    
    # 步驟 1: 檢查當前環境的依賴衝突
    current_env_conflicts = check_package_conflicts()
    if current_env_conflicts:
        print("\n⚠️ 建議在繼續之前解決上述已安裝套件的衝突。", file=sys.stderr)
    else:
        print("\n✅ 當前環境的已安裝套件依賴關係良好。")

    print("\n--- 測試各需求檔案的兼容性 ---")
    
    working_files = []
    for file in TEST_REQUIREMENTS_FILES:
        # test_installation now handles FileNotFoundError internally
        if test_installation(file):
            working_files.append(file)
        else:
            # If test_installation returns False, it already printed an error.
            # No need for an extra print here unless specific further action is needed.
            pass 
    
    if working_files:
        print(f"\n✅ 發現以下需求檔案相容性測試通過: {', '.join(working_files)}")
        print(f"建議使用其中一個，例如: {working_files[0]}")
    else:
        print("\n❌ 所有現有需求檔案都未能通過兼容性測試。", file=sys.stderr)
        print("嘗試生成一個新的啟發式兼容需求檔案...", file=sys.stderr)
        generate_compatible_requirements()
        
        if test_installation(REQUIREMENTS_AUTO_FILE):
            print(f"\n✅ 成功生成並測試通過 {REQUIREMENTS_AUTO_FILE}。")
            print(f"建議您檢查 `{REQUIREMENTS_AUTO_FILE}` 的內容，並考慮將其作為新的基準。")
        else:
            print(f"\n❌ 自動生成的需求檔案 `{REQUIREMENTS_AUTO_FILE}` 也未能通過測試。", file=sys.stderr)
            print("這可能表示專案存在深層次的依賴衝突，需要手動仔細檢查。", file=sys.stderr)
            print("請參考 `TROUBLESHOOTING.md` 文件或查閱相關文件以獲取進一步幫助。", file=sys.stderr)

if __name__ == "__main__":
    main()
