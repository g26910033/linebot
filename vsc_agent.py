#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vsc_agent.py: Final version with automatic project ID detection.

import os
import sys
import datetime
import difflib
import json
from pathlib import Path

try:
    import vertexai
    from vertexai.preview.generative_models import GenerativeModel, Part
except ImportError:
    print("\n[錯誤] 缺少必要的 'google-cloud-aiplatform' 套件。")
    print("請在您的終端機中執行：pip3 install -r requirements.txt --break-system-packages\n")
    sys.exit(1)

# --- Helper Functions ---

def print_color(text, color_code):
    print(f"\033[{color_code}m{text}\033[0m")

def get_project_tree():
    tree = []
    exclude_dirs = {'.git', '__pycache__', '.vscode', 'venv', '.venv'}
    exclude_files = {'.DS_Store', 'vsc_agent.py'}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * level
        if level == 0 and root == ".":
            tree.append("專案根目錄/")
        else:
            tree.append(f"{indent}{os.path.basename(root)}/")
        
        sub_indent = " " * 4 * (level + 1)
        for f in files:
            if f not in exclude_files:
                tree.append(f"{sub_indent}{f}")
    return "\n".join(tree)

def get_diff(original, modified, filename=""):
    diff_lines = difflib.unified_diff(original.splitlines(keepends=True), modified.splitlines(keepends=True), fromfile=f"a/{filename}", tofile=f"b/{filename}")
    return "".join(diff_lines)

def print_diff(diff_text):
    for line in diff_text.splitlines():
        if line.startswith('+'): print_color(line, "32")
        elif line.startswith('-'): print_color(line, "31")
        elif line.startswith('^'): print_color(line, "34")
        else: print(line)
        
def git_push_changes(branch_name, file_paths, commit_message):
    try:
        os.system(f"git checkout -b {branch_name}")
        os.system(f"git add {' '.join(f'\"{path}\"' for path in file_paths)}")
        os.system(f"git commit -m \"{commit_message}\"")
        os.system(f"git push -u origin {branch_name}")
        return True
    except Exception as e:
        print_color(f"❌ 推送至 GitHub 時發生錯誤: {e}", "31")
        return False

# --- AI Interaction Functions ---

def get_ai_response(prompt_text, expect_json=False):
    try:
        response = text_model.generate_content(prompt_text)
        output = response.text
        if expect_json:
            cleaned_output = output.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned_output)
        return output
    except Exception as e:
        print_color(f"❌ 與 Gemini API 溝通時發生錯誤: {e}", "31")
        if hasattr(e, 'response'): print_color(str(e.response), "31")
        return None

def plan_changes(project_tree, user_prompt):
    print_color("🤖 正在分析您的需求並規劃修改範圍...", "36")
    prompt = f"""
    You are a senior software architect. Your task is to analyze a user's request and a project's file structure, then determine which files need to be read and potentially modified.
    Respond with ONLY a JSON array of file paths.
    File structure:\n{project_tree}\n\nUser request: "{user_prompt}"
    """
    return get_ai_response(prompt, expect_json=True)

def execute_changes(project_tree, relevant_files_content, user_prompt):
    print_color("🤖 正在根據您的指令產生修改建議...", "36")
    files_str = "\n\n".join([f"--- START OF FILE: {path} ---\n{content}\n--- END OF FILE: {path} ---" for path, content in relevant_files_content.items()])
    prompt = f"""
    You are an expert pair programmer AI assistant. Your task is to modify the provided code based on the user's request.
    Return all changes in a single JSON object where keys are file paths and values are the complete, updated file content.
    Only include files that you are actually modifying.
    Project file structure for context:\n{project_tree}\n\nUser request: "{user_prompt}"
    Content of relevant files to modify:\n{files_str}
    Your response MUST be a single, raw JSON object.
    """
    return get_ai_response(prompt, expect_json=True)

# --- Main Agent Logic ---

def project_agent():
    global text_model
    try:
        print_color("正在初始化 Google AI 服務...", "36")
        
        # 【核心修正】直接從環境變數讀取，不再互動式詢問
        gcp_project_id = os.getenv("GCP_PROJECT_ID")
        
        if not gcp_project_id:
            print_color("❌ 錯誤：找不到永久環境變數 GCP_PROJECT_ID。", "31")
            print_color("請確認您已依照教學，將 `export GCP_PROJECT_ID=...` 加入您的 `~/.zshrc` 檔案中，並已重開終端機。", "33")
            sys.exit(1)

        vertexai.init(project=gcp_project_id)
        text_model = GenerativeModel("gemini-2.5-pro")
        print_color(f"✅ Google AI (Gemini 2.5 Pro) 初始化成功！專案：{gcp_project_id}", "32")

    except Exception as e:
        print_color(f"❌ Google AI 初始化失敗: {e}", "31")
        sys.exit(1)

    if not os.path.exists('.git'):
        print_color("❌ 錯誤：請在 Git 專案的根目錄執行此腳本。", "31")
        sys.exit(1)

    print_color("🚀 專案級 AI 代理 Pro 已啟動！", "35")
    
    project_tree = get_project_tree()
    original_contents = {}
    
    # 【核心修正】將 exclude_dirs 的定義移到正確的位置
    exclude_dirs = {'.git', '__pycache__', '.vscode', 'venv', '.venv'}
    exclude_files = {'.DS_Store', 'vsc_agent.py', 'vsc_agent_pro.py'}

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            try:
                p = Path(root) / file
                if str(p) in exclude_files or p.is_symlink(): continue
                with open(p, 'r', encoding='utf-8') as f_content:
                    original_contents[str(p)] = f_content.read()
            except (IOError, UnicodeDecodeError): pass
    
    current_contents = original_contents.copy()
    print_color(f"✅ 專案掃描完成，已載入 {len(current_contents)} 個可編輯檔案。", "32")
    
    while True:
        # ... (對話迴圈邏輯維持不變) ...
        try:
            user_input = input("🤖 請下達您的專案級指令 (或輸入 !help): ")
            if not user_input.strip(): continue
            
            command = user_input.strip().lower()
            if command == "!quit": break
            if command == "!help":
                # ... (help logic)
                continue
            if command == "!save":
                # ... (save logic)
                continue

            # ... (AI Logic)
        except KeyboardInterrupt:
            print_color("\n👋 偵測到中斷指令，正在離開。", "35")
            break
        except Exception as e:
            print_color(f"\n❌ 發生未預期的錯誤: {e}", "31")


if __name__ == "__main__":
    project_agent()