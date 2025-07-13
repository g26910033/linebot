#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vsc_agent.py: An interactive agent for code modification in VS Code.
# This script is designed to be run in the integrated terminal of Visual Studio Code on macOS.
# Recommended execution: python3 vsc_agent.py

import subprocess
import os
import sys
import datetime
import difflib

# --- Helper Functions ---

def print_color(text, color_code):
    """Prints text in a specified color."""
    print(f"\033[{color_code}m{text}\033[0m")

def run_command(command):
    """Runs a shell command and returns its output or raises an error."""
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print_color(f"❌ 命令執行失敗: {command}", "31")
        print_color(f"錯誤訊息: {result.stderr}", "31")
        return None
    return result.stdout.strip()

def get_diff(original, modified, filename=""):
    """Generates and returns a unified diff string."""
    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff_lines)

def print_diff(diff_text):
    """Prints a diff with colors for better readability."""
    for line in diff_text.splitlines():
        if line.startswith('+'):
            print_color(line, "32")  # Green for additions
        elif line.startswith('-'):
            print_color(line, "31")  # Red for deletions
        elif line.startswith('^'):
            print_color(line, "34")  # Blue for context lines
        else:
            print(line)

def get_gemini_suggestion(file_content, user_prompt):
    """Calls the Gemini CLI to get a code modification suggestion."""
    print_color("🤖 正在思考中，請稍候...", "36")
    
    # Construct a high-quality prompt for the Gemini CLI
    full_prompt = f"""
    You are an expert pair programmer AI assistant. Your task is to modify the provided code based on the user's request.
    IMPORTANT: Only output the complete, raw, updated code. Do not include any explanations, comments, apologies, or markdown formatting like ```python.

    User's request: "{user_prompt}"

    Here is the current code to modify:
    --- START OF CODE ---
    {file_content}
    --- END OF CODE ---
    """
    
    # Using the 'gemini' CLI tool
    # Ensure the gemini CLI is authenticated and in your PATH
    command = f"gemini pro <<< '{full_prompt}'"
    suggested_code = run_command(command)
    
    if suggested_code is None:
        return None

    return suggested_code

# --- Main Agent Logic ---

def main_agent():
    # 1. Environment Check
    if not os.path.exists('.git'):
        print_color("❌ 錯誤：目前的資料夾不是一個 Git 倉庫。請在專案的根目錄執行此腳本。", "31")
        sys.exit(1)

    print_color("🚀 AI 程式碼代理已啟動！", "35")
    print_color("隨時輸入 !help 來查看可用指令。", "35")

    # 2. Target File Input
    while True:
        target_file = input("請輸入您想編輯的檔案相對路徑 (例如: src/main.py): ")
        if not os.path.exists(target_file):
            print_color(f"❌ 錯誤：找不到檔案 '{target_file}'。請確認路徑是否正確。", "31")
        else:
            break

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
        current_content = original_content
        print_color(f"✅ 已成功讀取檔案 '{target_file}'。開始進行對話式修改。", "32")
    except Exception as e:
        print_color(f"❌ 讀取檔案時發生錯誤: {e}", "31")
        sys.exit(1)

    # 3. Main Conversation Loop
    while True:
        try:
            user_input = input("🤖 請下達您的指令 (或輸入 !help): ")

            if user_input.strip() == "!quit":
                print_color("👋 感謝使用，下次見！", "35")
                break

            elif user_input.strip() == "!help":
                print_color("\n--- 可用指令 ---", "33")
                print("!help   : 顯示此說明")
                print("!diff   : 顯示目前所有的修改與原始檔案的差異")
                print("!revert : 放棄所有修改，將檔案還原到最初狀態")
                print("!save   : 將目前所有修改儲存並推送到 GitHub 的一個新分支")
                print("!quit   : 退出代理程式")
                print_color("------------------\n", "33")
            
            elif user_input.strip() == '!diff':
                diff = get_diff(original_content, current_content, target_file)
                if not diff:
                    print_color("✅ 目前沒有任何修改。", "32")
                else:
                    print_color("\n--- 目前的修改差異 ---", "33")
                    print_diff(diff)
                    print_color("---------------------\n", "33")

            elif user_input.strip() == '!revert':
                confirmation = input("⚠️ 您確定要放棄所有修改嗎？(y/n): ").lower()
                if confirmation == 'y':
                    current_content = original_content
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write(current_content)
                    print_color("✅ 所有修改已被還原。", "32")
                else:
                    print_color("操作已取消。", "36")

            elif user_input.strip() == '!save':
                if original_content == current_content:
                    print_color("🤔 沒有任何修改可以儲存。", "33")
                    continue

                branch_name = f"feature/agent-edits-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                print_color(f"準備將變更推送至新的分支: {branch_name}", "36")
                
                try:
                    run_command(f"git checkout -b {branch_name}")
                    run_command(f"git add {target_file}")
                    commit_message = f"AI-assisted changes for {target_file}"
                    run_command(f"git commit -m '{commit_message}'")
                    run_command(f"git push -u origin {branch_name}")

                    print_color("\n✅ 成功！已將變更推送至新分支。", "32")
                    print_color("您現在可以關閉此終端機，並使用 VS Code 左側的「原始檔控制」面板 (Source Control) 來查看分支並建立 Pull Request。", "32")
                    break # Task completed, exit the agent.
                except Exception as e:
                    print_color(f"❌ 推送至 GitHub 時發生錯誤: {e}", "31")
                    print_color("建議手動還原變更，或解決 Git 衝突後再試一次。", "33")


            else: # Natural Language Prompt for Gemini
                suggested_code = get_gemini_suggestion(current_content, user_input)
                
                if suggested_code and suggested_code != current_content:
                    diff = get_diff(current_content, suggested_code, target_file)
                    print_color("\n--- Gemini 提議的變更 ---", "33")
                    print_diff(diff)
                    print_color("------------------------\n", "33")
                    
                    apply_change = input("是否套用以上變更？(y/n): ").lower()
                    if apply_change == 'y':
                        current_content = suggested_code
                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(current_content)
                        print_color("✅ 變更已套用！您現在可以在 VS Code 編輯器中看到即時更新。", "32")
                    else:
                        print_color("操作已取消，未套用變更。", "36")
                elif suggested_code == current_content:
                    print_color("🤔 Gemini 認為目前的程式碼已符合您的要求，無需修改。", "33")
                else:
                    print_color("無法從 Gemini 獲取有效的建議。", "31")

        except KeyboardInterrupt:
            print_color("\n👋 偵測到中斷指令，正在離開。感謝使用！", "35")
            break
        except Exception as e:
            print_color(f"\n❌ 發生未預期的錯誤: {e}", "31")


if __name__ == "__main__":
    main_agent()