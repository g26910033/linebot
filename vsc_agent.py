#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vsc_agent.py: Project-aware agent for multi-file, conversational coding.
# This version uses the Vertex AI SDK directly and is designed for local use in VS Code.

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
    print("請在您的終端機中執行：pip3 install -r requirements.txt\n")
    sys.exit(1)

# --- Helper Functions ---

def print_color(text, color_code):
    """Prints text in a specified color."""
    print(f"\033[{color_code}m{text}\033[0m")

def get_project_tree():
    """Generates a text-based representation of the project file tree."""
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
        if line.startswith('+'): print_color(line, "32") # Green
        elif line.startswith('-'): print_color(line, "31") # Red
        elif line.startswith('^'): print_color(line, "34") # Blue
        else: print(line)
        
def git_push_changes(branch_name, file_paths, commit_message):
    try:
        print_color(f"正在建立新分支: {branch_name}...", "36")
        os.system(f"git checkout -b {branch_name}")
        
        print_color("正在將變更加入暫存區...", "36")
        os.system(f"git add {' '.join(f'\"{path}\"' for path in file_paths)}")

        print_color("正在提交變更...", "36")
        os.system(f"git commit -m \"{commit_message}\"")

        print_color("正在推送至 GitHub...", "36")
        os.system(f"git push -u origin {branch_name}")
        return True
    except Exception as e:
        print_color(f"❌ 推送至 GitHub 時發生錯誤: {e}", "31")
        return False

# --- AI Interaction Functions ---

def get_ai_response(prompt_text, expect_json=False):
    try:
        response = model.generate_content(prompt_text)
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
    prompt = f"""You are a senior software architect. Your task is to analyze a user's request and a project's file structure, then determine which files need to be read and potentially modified to fulfill the request.
Respond with ONLY a JSON array of file paths. Do not include any other text or explanation.

File structure:
{project_tree}

User request: "{user_prompt}"
"""
    return get_ai_response(prompt, expect_json=True)

def execute_changes(project_tree, relevant_files_content, user_prompt):
    print_color("🤖 正在根據您的指令產生修改建議...", "36")
    files_str = "\n\n".join([f"--- START OF FILE: {path} ---\n{content}\n--- END OF FILE: {path} ---" for path, content in relevant_files_content.items()])
    prompt = f"""
You are an expert pair programmer AI assistant. Your task is to modify the provided code based on the user's request.
The user's request may involve multiple files. You must return all changes in a single JSON object.
The JSON object should have file paths as keys and the complete, updated content of the file as string values.
IMPORTANT: The file content you return must be the *entire* file, not just the changed parts. Only include files that you are actually modifying.
Project file structure for context:\n{project_tree}

User request: "{user_prompt}"
Content of relevant files to modify:\n{files_str}

Your response MUST be a single, raw JSON object.
"""
    return get_ai_response(prompt, expect_json=True)

# --- Main Agent Logic ---

def project_agent():
    global model
    try:
        print_color("正在初始化 Google AI 服務...", "36")
        gcp_project_id = os.getenv("GCP_PROJECT_ID")
        if not gcp_project_id:
            gcp_project_id = input("🔵 請輸入您的 Google Cloud Project ID: ")
            if not gcp_project_id:
                print_color("❌ 未提供 Project ID，程式無法繼續。", "31")
                sys.exit(1)
        vertexai.init(project=gcp_project_id)
        model = GenerativeModel("gemini-2.5-pro")
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
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            try:
                p = Path(root) / file
                if str(p) == 'vsc_agent.py' or p.is_symlink() or str(p) in exclude_files: continue
                with open(p, 'r', encoding='utf-8') as f_content:
                    original_contents[str(p)] = f_content.read()
            except (IOError, UnicodeDecodeError): pass
    
    current_contents = original_contents.copy()
    print_color(f"✅ 專案掃描完成，已載入 {len(current_contents)} 個可編輯檔案。", "32")
    
    while True:
        try:
            user_input = input("🤖 請下達您的專案級指令 (或輸入 !help): ")
            if not user_input.strip(): continue
            
            command = user_input.strip().lower()
            if command == "!quit": break
            if command == "!help":
                # Help logic here
                continue
            if command == "!save":
                changed_files = {path: content for path, content in current_contents.items() if original_contents.get(path) != content}
                if not changed_files:
                    print_color("🤔 沒有任何修改可以儲存。", "33")
                    continue
                branch_name = f"feature/agent-edits-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                commit_message = input("請輸入本次提交的說明 (Commit Message): ")
                if not commit_message:
                    commit_message = f"AI-assisted changes based on user prompt"
                if git_push_changes(branch_name, list(changed_files.keys()), commit_message):
                    print_color("\n✅ 成功！已將變更推送至新分支。", "32")
                    break
                else:
                    print_color("推送失敗，請檢查終端機中的 Git 錯誤訊息。", "31")
                continue

            files_to_edit = plan_changes(project_tree, user_input)
            if not files_to_edit or not isinstance(files_to_edit, list):
                print_color("🤔 AI 規劃失敗或認為不需修改，請嘗試更明確的指令。", "33")
                continue

            print_color(f"📝 AI 規劃修改以下檔案: {', '.join(files_to_edit)}", "36")
            relevant_contents = {fp: current_contents[fp] for fp in files_to_edit if fp in current_contents}
            
            if not relevant_contents:
                print_color("❌ 沒有可供修改的相關檔案。", "31")
                continue

            modifications = execute_changes(project_tree, relevant_contents, user_input)
            if not modifications:
                print_color("🤔 AI 未能產生有效的修改建議。", "33")
                continue

            print_color("\n" + "="*25 + " Gemini 提議的變更 " + "="*25, "94")
            has_changes = False
            for file_path, new_content in modifications.items():
                if file_path in current_contents:
                    diff = get_diff(current_contents[file_path], new_content, file_path)
                    if diff:
                        has_changes = True
                        print_color(f"\n--- 檔案: {file_path} ---", "33")
                        print_diff(diff)
            print_color("="*70 + "\n", "94")

            if not has_changes:
                print_color("🤔 AI 認為無需修改。", "33")
                continue
                
            apply_change = input("是否套用以上所有變更？(y/n): ").lower()
            if apply_change == 'y':
                for file_path, new_content in modifications.items():
                    if file_path in current_contents:
                        current_contents[file_path] = new_content
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                print_color("✅ 所有變更已套用！", "32")
            else:
                print_color("操作已取消。", "36")
        except KeyboardInterrupt:
            print_color("\n👋 偵測到中斷指令，正在離開。", "35")
            break
        except Exception as e:
            print_color(f"\n❌ 發生未預期的錯誤: {e}", "31")

if __name__ == "__main__":
    project_agent()