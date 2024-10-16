import streamlit as st
import subprocess
import os
import shutil
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from docx import Document
import pdfplumber
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
import re

# 初始化 OpenAI API
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("未能從環境變數中讀取 OpenAI API 密鑰。請設置環境變數 OPENAI_API_KEY。")
else:
    client = OpenAI(api_key=api_key)

# 新增：側邊欄選擇 GPT 模型
model_name = st.sidebar.selectbox(
    "選擇 GPT 模型版本",
    options=["gpt-4o", "gpt-4o-mini"]
)

# 使用者選擇的模型
MODEL_NAME = model_name

# 創建 Streamlit 網頁
st.title("GPT 程式審查工具")
st.write(f"已選擇 :green[{MODEL_NAME}] 模型進行代碼審查")
st.write("上傳程式碼文件或壓縮檔，透過選擇的 GPT 模型進行審查，並可選擇夾帶審查規則文件")

# 側邊欄選擇語言
file_type = st.sidebar.selectbox(
    "選擇要審查的程式語言類型",
    options=[".py", ".cpp", ".cs"]
)

# 上傳檔案區域（支援多個檔案或壓縮檔）
uploaded_files = st.file_uploader(f"上傳程式碼文件（:red[{file_type}]）、壓縮檔（.zip、.7z）", type=[file_type[1:], "zip", "7z"], accept_multiple_files=True)

# 上傳審查規則文檔（必須上傳，支援 txt、md、docx、pdf）
rules_file = st.file_uploader("必須：上傳審查規則文件", type=["txt", "md", "docx", "pdf"])

# 使用 7-Zip 命令行解壓檔案（ZIP 或 7z）
def extract_with_7zip(file_path, output_dir):
    try:
        seven_zip_path = r"C:\Program Files\7-Zip\7z.exe"  # 根據你的系統進行調整
        command = [seven_zip_path, 'x', file_path, f'-o{output_dir}', '-y']  # 添加 '-y' 自動確認
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        process.wait()

        if process.returncode == 0:
            return output_dir
        else:
            st.error(f"7-Zip 解壓失敗: {process.stderr.read()}")

        return output_dir
    except Exception as e:
        st.error(f"7-Zip 解壓過程中出現錯誤: {e}")
        return None

# 設定審查規則的預設路徑
default_rule_paths = {
    ".py": "./rules/Python/rule.txt",  # Python 的預設審查規則路徑
    ".cs": "./rules/C#/rule.txt",      # C# 的預設審查規則路徑
    ".cpp": "./rules/C++/rule.txt"     # C++ 的預設審查規則路徑
}

# 檢查是否上傳審查規則文件，如果沒有，則使用預設文件
def get_rules_content(file_type, rules_file):
    if rules_file:  # 若使用者有上傳審查規則文件
        return parse_rules_file(rules_file)
    else:  # 若沒有上傳，使用預設路徑中的規則文件
        default_file_path = default_rule_paths.get(file_type)
        if default_file_path and os.path.exists(default_file_path):
            with open(default_file_path, "r", encoding="utf-8") as default_file:
                return default_file.read()
        else:
            st.error(f"預設的審查規則文件 {default_file_path} 不存在。請檢查文件路徑。")
            return ""


# 處理規則文件
def parse_rules_file(file):
    try:
        if file.type == "text/plain":
            return file.read().decode("utf-8")
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = Document(file)
            return "\n".join([para.text for para in doc.paragraphs])
        elif file.type == "application/pdf":
            text = ""
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip() == "":
                st.error("無法從 PDF 中提取到任何文本。")
            return text
        else:
            st.error("無法識別的文件類型")
            return ""
    except Exception as e:
        st.error(f"解析文件時出現錯誤：{e}")
        return ""

# 從 GPT-4 的審查結果中提取各個審查項目和對應結果
def extract_review_items(result_text):
    review_items = []
    lines = result_text.split('\n')
    
    # 嘗試解析 | 分隔的行
    for line in lines:
        if '|' in line:
            parts = line.split('|')
            if len(parts) == 3:
                rule = parts[0].strip()
                status = parts[1].strip()
                suggestion = parts[2].strip()

                # 根據狀態調整為「符合」或「不符合」
                if '必須' in status or '不允許' in status or '慎用' in status or '不符合' in status:
                    status = '不符合'
                else:
                    status = '符合'

                review_items.append({
                    "審查項目": rule,
                    "狀態": status,
                    "建議": suggestion
                })
    
    return review_items

# 從 HTML 模板文件中讀取參考格式
def load_reference_html_template(template_path="./rules/format/report_format.html"):
    try:
        with open(template_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        st.error(f"未找到 HTML 模板文件: {template_path}")
        return None

# GPT 生成基於參考 HTML 格式的完整報告
def generate_html_report_with_gpt_based_on_template(review_results, template_content):
    # 構建審查摘要，供 GPT 使用
    review_summary = ""
    for file_name, review_items in review_results.items():
        review_summary += f"<h2>File: {file_name}</h2>\n"
        for item in review_items:
            review_summary += f"<h3>Review Item: {item['審查項目']}</h3>\n"
            review_summary += f"<p>Status: {item['狀態']}</p>\n"
            review_summary += f"<p>Suggestion: {item['建議']}</p>\n"
            if item.get('code_snippet'):
                review_summary += f"<pre><code>{item['code_snippet']}</code></pre>\n"
        review_summary += "<hr>\n"

    # GPT 的 prompt，讓 GPT 自行根據參考 HTML 生成完整的報告
    prompt = f"""
    You are a helpful assistant. Below is an HTML report template that serves as a reference:

    {template_content}

    Please generate a new HTML report based on this format, using the following code review results:

    {review_summary}

    Ensure that the structure, styles, and layout match the reference HTML, but fill in the new review results appropriately.
    Do not include the original reference content; only the new review data should be in the generated report.
    """

    try:
        # 使用 GPT 生成完整的 HTML 報告
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        # GPT 回傳的 HTML 報告
        html_report = completion.choices[0].message.content
        return html_report
    except Exception as e:
        st.error(f"生成 HTML 報告時出現錯誤：{e}")
        return None

# 定義 create_review_dataframe 函數
def create_review_dataframe(review_results):
    table_data = []
    for file_name, review_items in review_results.items():
        for item in review_items:
            table_data.append({
                "文件名稱": file_name,
                "審查項目": item["審查項目"],
                "狀態": item["狀態"],
                "建議": item["建議"]
            })
    
    return pd.DataFrame(table_data)

# 檢查是否點擊"開始審查"
if st.button("開始審查"):    
    # 根據使用者選擇的程式語言類型和上傳情況，獲取審查規則內容
    rules_content = get_rules_content(file_type, rules_file)            
    if not rules_content.strip():
        st.error("審查規則文件內容為空或無法解析，請重新上傳正確的文件。")
    else:
        files_content = {}
        output_dir = "./extracted_files"

        # 清空 temp 和 output 目錄
        if os.path.exists("./temp"):
            shutil.rmtree("./temp")
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs("./temp")
        os.makedirs(output_dir)

        # 處理上傳的檔案
        for uploaded_file in uploaded_files:
            temp_path = f"./temp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            # 僅對 ZIP 和 7Z 檔案進行解壓
            if uploaded_file.type in ["application/x-zip-compressed", "application/x-7z-compressed"]:
                extracted_path = extract_with_7zip(temp_path, output_dir)
                if extracted_path:
                    for root, dirs, files in os.walk(extracted_path):
                        for file in files:
                            if file.endswith(file_type[1:]):  # 移除點判斷檔案類型
                                file_path = os.path.join(root, file)
                                with open(file_path, "r", encoding='utf-8') as py_file:
                                    files_content[file] = py_file.read()
            else:
                # 直接讀取其他文件類型（如 .py）
                with open(temp_path, "r", encoding='utf-8') as py_file:
                    files_content[uploaded_file.name] = py_file.read()

            # 提取審查項目
            extracted_rules = []  # 初始化 extracted_rules
            try:
                messages = [
                    {"role": "system", "content": f"以下是審查規則文件的內容：\n{rules_content}"},
                    {"role": "user", "content": f"請分析該規則文件並提取出所有需要審查的項目，並使用格式 '審查項目 | 狀態 | 建議' 回覆。"}
                ]
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages
                )
                result = completion.choices[0].message.content
                extracted_rules = result.split('\n')
                extracted_rules = [rule.strip() for rule in extracted_rules if rule.strip()]
            except Exception as e:
                st.error(f"從規則文件中提取審查項目時出現錯誤：{e}")
                extracted_rules = []

            # 檢查 extracted_rules 是否提取成功
            if extracted_rules:                
                # 進行代碼審查
                review_results = {}
                for file_name, content in files_content.items():
                    if isinstance(content, str):
                        messages = [
                            {"role": "user", "content": f"請審查以下代碼，並根據以下項目判斷是否合格，使用格式 '審查項目 | 狀態 | 建議' 回覆：{', '.join(extracted_rules)}\n{content}"},
                            {"role": "system", "content": f"請根據以下規則進行審查：\n{rules_content}"}
                        ]
                        try:
                            completion = client.chat.completions.create(
                                model=MODEL_NAME,
                                messages=messages
                            )
                            result = completion.choices[0].message.content
                            review_results[file_name] = extract_review_items(result)  # 提取各項結果
                        except Exception as e:
                            review_results[file_name] = f"審查過程中出現錯誤：{e}"

                # 生成審查結果的 DataFrame
                df = create_review_dataframe(review_results)                
                st.table(df)

                # 生成 HTML 報告
                template_content = load_reference_html_template()  # 讀取模板內容
                if template_content:
                    html_report = generate_html_report_with_gpt_based_on_template(review_results, template_content)  # 傳遞所有審查結果
                    if html_report:
                        st.download_button("下載審查報告 (HTML)", data=html_report, file_name="審查報告.html", mime="text/html")
                    else:
                        st.error("生成 HTML 報告失敗")
            else:
                st.error("未能提取任何審查項目，請檢查規則文件內容。")
