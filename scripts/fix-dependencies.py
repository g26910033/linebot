#!/usr/bin/env python3
"""
依賴修復腳本
檢查和修復常見的依賴問題，並提供修復建議。
PEP8/型別註解/效能/安全優化。
"""
import subprocess
import sys
import platform
import os
from typing import List, Optional

REQUIREMENTS_FILE_NAME: str = "requirements.txt"
SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: str = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
REQUIREMENTS_TXT_PATH: str = os.path.join(PROJECT_ROOT, REQUIREMENTS_FILE_NAME)


def print_section_header(title: str) -> None:
    """
    打印格式化的區塊標題。
    Args:
        title (str): 區塊的標題。
    """
    print(f"\n--- {title} ---")


def run_pip_command(args: List[str], success_msg: str, fail_msg: str) -> bool:
    """
    執行 pip 命令並打印成功/失敗訊息。
    Args:
        args (List[str]): pip 命令參數。
        success_msg (str): 成功訊息。
        fail_msg (str): 失敗訊息。
    Returns:
        bool: 成功為 True。
    """
    try:
        command: List[str] = [sys.executable, "-m", "pip"] + args
        print(f"Executing: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {success_msg}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {fail_msg}: {e.stderr.strip()}")
        if e.stdout:
            print(f"詳細輸出: {e.stdout.strip()}")
        return False
    except FileNotFoundError:
        print("❌ 命令 'pip' 或 Python 解釋器未找到。請確認 Python 已正確安裝並在 PATH 中。")
        return False
    except Exception as e:
        print(f"❌ 執行 pip 命令時發生未預期錯誤: {e}")
        return False


def check_python_version() -> bool:
    """
    檢查 Python 版本並提供建議。
    Returns:
        bool: 推薦版本為 True。
    """
    print_section_header("Python 版本檢查")
    current_version: str = platform.python_version()
    print(f"當前 Python 版本: {current_version}")
    try:
        major, minor, _ = map(int, current_version.split('.'))
    except ValueError:
        print("❌ 無法解析 Python 版本號。請確認 Python 安裝正確。")
        return False
    if major == 3 and minor == 13:
        print("⚠️  警告: Python 3.13 可能存在相容性問題，部分套件尚未完全支援。")
        print("建議使用 Python 3.11 或 3.12 以獲得最佳相容性。")
        return False
    if major == 3 and minor < 11:
        print("⚠️  警告: Python 版本過舊。")
        print("建議升級到 Python 3.11 或更高版本，以獲得更好的性能和安全性。")
        return False
    if major != 3:
        print("⚠️  警告: 此腳本專為 Python 3 設計。您目前使用的版本可能不相容。")
        return False
    print("✅ Python 版本檢查通過。")
    return True


def check_virtual_environment() -> bool:
    """
    檢查是否在虛擬環境中。
    Returns:
        bool: 虛擬環境為 True。
    """
    print_section_header("虛擬環境檢查")
    if (sys.prefix == sys.base_prefix) and (not hasattr(sys, 'real_prefix')):
        print("⚠️  建議: 您目前不在虛擬環境中。")
        print("強烈建議使用虛擬環境 (如 venv 或 conda) 來管理專案依賴，以避免全域衝突。")
        print("您可以使用以下命令創建並激活虛擬環境:")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate  (Linux/macOS)")
        print("  .\\venv\\Scripts\\activate  (Windows PowerShell)")
        return False
    env_name: str = os.path.basename(sys.prefix)
    print(f"✅ 您正在虛擬環境中 ({env_name})。")
    return True


def install_build_tools() -> bool:
    """
    安裝或升級構建工具 (pip, wheel, setuptools)。
    Returns:
        bool: 成功為 True。
    """
    print_section_header("構建工具安裝/升級")
    return run_pip_command(
        ["install", "--upgrade", "pip", "wheel", "setuptools"],
        "構建工具 (pip, wheel, setuptools) 安裝/升級成功。",
        "構建工具安裝/升級失敗"
    )


def install_package(package_name: str, version: Optional[str] = None, no_cache_dir: bool = False) -> bool:
    """
    嘗試安裝指定的 Python 套件。
    Args:
        package_name (str): 套件名稱。
        version (Optional[str]): 指定版本。
        no_cache_dir (bool): 是否禁用快取。
    Returns:
        bool: 安裝成功為 True。
    """
    target: str = f"{package_name}=={version}" if version else package_name
    args: List[str] = ["install", target]
    if no_cache_dir:
        args.append("--no-cache-dir")
    version_str: str = f" {version}" if version else ""
    return run_pip_command(
        args,
        f"{package_name}{version_str} 安裝成功。",
        f"{package_name}{version_str} 安裝失敗"
    )


def fix_pillow_installation() -> bool:
    """
    嘗試修復 Pillow 套件的安裝問題。
    多版本嘗試，並提示系統依賴。
    Returns:
        bool: Pillow 安裝成功為 True。
    """
    print_section_header("Pillow 套件安裝修復")
    print("ℹ️ 嘗試安裝 Pillow 10.4.0 (禁用緩存)...")
    if install_package("Pillow", "10.4.0", no_cache_dir=True):
        print("✅ Pillow 10.4.0 安裝成功。")
        return True
    print("ℹ️ Pillow 10.4.0 安裝失敗，嘗試安裝較舊的 Pillow 9.5.0 (禁用緩存)...")
    if install_package("Pillow", "9.5.0", no_cache_dir=True):
        print("✅ Pillow 9.5.0 安裝成功。")
        return True
    print("❌ 所有嘗試的 Pillow 版本都安裝失敗。這可能是由於缺少系統依賴 (如 zlib, libjpeg) 導致。")
    print("請檢查您的系統環境，或參考 Pillow 官方文件以解決此問題。")
    print("您可能需要安裝開發庫，例如在 Debian/Ubuntu 上使用 'sudo apt-get install libjpeg-dev zlib1g-dev' 或在 Fedora 上使用 'sudo dnf install libjpeg-turbo-devel zlib-devel'。")
    return False


def install_from_requirements() -> bool:
    """
    從 requirements.txt 安裝依賴。
    Returns:
        bool: 安裝成功為 True。
    """
    print_section_header("從 requirements.txt 安裝依賴")
    if not os.path.exists(REQUIREMENTS_TXT_PATH):
        print(f"ℹ️ 未找到 {REQUIREMENTS_TXT_PATH} 文件。如果您的專案有依賴文件，請確認路徑或名稱。")
        return True
    print(f"找到 {REQUIREMENTS_TXT_PATH}，嘗試安裝其中的依賴...")
    return run_pip_command(
        ["install", "-r", REQUIREMENTS_TXT_PATH],
        "requirements.txt 中的所有依賴安裝成功。",
        "requirements.txt 中的部分或所有依賴安裝失敗"
    )


def main() -> None:
    """
    主函式，執行所有依賴檢查和修復步驟。
    """
    print("🚀 開始依賴修復與環境檢查...")
    check_python_version()
    check_virtual_environment()
    if not install_build_tools():
        print("致命錯誤: 無法安裝必要的構建工具 (pip, wheel, setuptools)。請檢查您的網路連接或權限。")
        sys.exit(1)
    fix_pillow_installation()
    if not install_from_requirements():
        print("⚠️ 某些依賴可能未能成功安裝。請檢查上述錯誤訊息以了解詳情。")
    print("\n🎉 依賴修復與環境檢查完成！請檢查上述訊息以確認所有問題是否已解決。")
    print("如果問題仍然存在，請截圖錯誤訊息並尋求進一步協助。")


if __name__ == "__main__":
    main()
