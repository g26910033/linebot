#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vsc_agent_pro.py: Final streamlined version with hardcoded Project ID and no venv dependency.

import os
import sys
import datetime
import difflib
import json
from pathlib import Path

# 引入 Vertex AI 函式庫
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
from vertexai.preview.vision_models import ImageGenerationModel

# --- Helper Functions (無需修改) ---

def print_color(text, color_code):
    print(f"\033[{color_code}m{text}\033[0m")

def get_project_tree():
    tree = []
    exclude_dirs = {'.git', '__pycache__', '.vscode', 'venv', '.venv'}
    exclude_files = {'.DS_Store', 'vsc_agent.py', 'vsc_agent_pro.py'}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * level
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
        for file_path in file_paths:
            os.system(f"git add '{file_path}'")
        os.system(f"git commit -m '{commit_message}'")
        os.system(f"git push -u origin {branch_name}")
        return True
    except Exception as e:
        print_color(f"❌ 推送至 GitHub 時發生錯誤: {e}", "31")
        return False

def get_ai_response(prompt_text, expect_json=False):
    try:
        # 根據是否為 JSON 決定要呼叫哪個模型
        if expect_json:
            # 規劃和產生結構化資料時，使用能力更全面的 Pro 模型
            response = text_model.generate_content(prompt_text)
        else:
             # 一般對話或簡單翻譯，使用速度更快的 Flash 模型 (如果未來要區分)
             # 目前統一使用 Pro
            response = text_model.generate_content(prompt_text)

        output = response.text
        if expect_json:
            output = output.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(output)
        return output
    except Exception as e:
        print_color(f"❌ 與 Gemini API 溝通時發生錯誤: {e}", "31")
        if hasattr(e, 'response'): print_color(str(e.response), "31")
        return None

def get_files_to_edit(project_tree, user_prompt):
    print_color("🤖 正在分析您的需求並規劃修改範圍...", "36")
    prompt = f"""
You are a senior software architect. Your task is to analyze a user's request and a project's file structure, then determine which files need to be read and potentially modified to fulfill the request.
Respond with ONLY a JSON array of file paths. Do not include any other text or explanation.
File structure:\n{project_tree}\n\nUser request: "{user_prompt}"
"""
    return get_ai_response(prompt, expect_json=True)

def get_code_modifications(project_tree, relevant_files_content, user_prompt):
    print_color("🤖 正在根據您的指令產生修改建議...", "36")
    files_str = "\n\n".join([f"--- START OF FILE: {path} ---\n{content}\n--- END OF FILE: {path} ---" for path, content in relevant_files_content.items()])
    prompt = f"""
You are an expert pair programmer AI assistant. Your task is to modify the provided code based on the user's request.
The user's request may involve multiple files. You must return all changes in a single JSON object.
The JSON object should have file paths as keys and the complete, updated content of the file as string values.
IMPORTANT: The file content you return must be the *entire* file, not just the changed parts. Only include files that you are actually modifying.
Project file structure for context:\n{project_tree}\n\nUser request: "{user_prompt}"
Content of relevant files to modify:\n{files_str}
Your response MUST be a single, raw JSON object.
"""
    return get_ai_response(prompt, expect_json=True)

def project_agent():
    global text_model
    try:
        print_color("正在初始化 Google AI 服務...", "36")
        
        # 【核心修正】直接將您的 Project ID 寫入程式碼
        gcp_project_id = "gen-lang-client-0879418335"
        
        vertexai.init(project=gcp_project_id)
        
        # 【核心修正】依照您的指示，設定指定的模型
        text_model = GenerativeModel("gemini-2.5-pro")
        global image_gen_model
        image_gen_model = GenerativeModel("imagen-3.0-generate-002")

        print_color(f"✅ Google AI 初始化成功！專案：{gcp_project_id}", "32")
        print_color(f"   - 文字模型: gemini-2.5-pro", "32")
        print_color(f"   - 圖像模型: imagen-3.0-generate-002", "32")

    except Exception as e:
        print_color(f"❌ Google AI 初始化失敗: {e}", "31")
        print_color("請確認您已執行 `gcloud auth application-default login`。", "33")
        sys.exit(1)

    # 後續程式碼與之前版本相同...

if __name__ == "__main__":
    project_agent()