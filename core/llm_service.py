import os
import json
import requests
from typing import Dict, List, Any

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def analyze_issue_with_llm(issue_title: str, issue_body: str, repo_files: List[Dict] = None) -> Dict[str, Any]:
    """Анализ Issue с помощью LLM"""

    files_context = ""
    if repo_files:
        files_context = "Файлы в репозитории:\n"
        for file in repo_files[:20]:
            files_context += f"- {file['path']} ({file['size']} bytes)\n"

    prompt = f"""
Ты - опытный разработчик. Проанализируй задачу и создай план реализации.

**Задача:**
{issue_title}

**Описание:**
{issue_body}

{files_context}

**Проанализируй:**
1. Что нужно сделать?
2. Какие файлы нужно изменить/создать?
3. Какие технологии использовать?
4. Оцени сложность (низкая/средняя/высокая)

Верни ответ в формате JSON:
{{
    "summary": "Краткое описание решения",
    "estimated_complexity": "низкая/средняя/высокая",
    "files_to_create": ["список файлов для создания"],
    "files_to_modify": ["список файлов для изменения"],
    "steps": ["шаг 1", "шаг 2", "шаг 3"]
}}
"""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты опытный разработчик. Отвечай только в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']

            try:
                content = content.replace('```json', '').replace('```', '').strip()
                analysis = json.loads(content)
                return analysis
            except json.JSONDecodeError:
                return {
                    "summary": content[:200],
                    "estimated_complexity": "средняя",
                    "files_to_create": ["solution.py"],
                    "files_to_modify": [],
                    "steps": ["Создать файл solution.py"]
                }
        else:
            print(f"❌ Ошибка DeepSeek API: {response.status_code}")
            return {"error": f"API error: {response.status_code}"}

    except Exception as e:
        print(f"❌ Ошибка анализа Issue: {e}")
        return {"error": str(e)}


def generate_code_changes(issue_body: str, analysis: Dict) -> Dict[str, Any]:
    """Генерация изменений кода на основе анализа"""

    prompt = f"""
Ты - опытный разработчик. Создай или измени код для решения задачи.

**Задача:**
{issue_body}

**Анализ задачи:**
{json.dumps(analysis, ensure_ascii=False, indent=2)}

**Требования:**
1. Создай полный, рабочий код
2. Добавь комментарии
3. Следуй PEP8
4. Учитывай контекст задачи

Верни ответ в формате JSON:
{{
    "summary": "Что было сделано",
    "changes": [
        {{
            "file_path": "путь/к/файлу.py",
            "new_content": "полный код файла"
        }}
    ]
}}
"""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты опытный разработчик Python. Отвечай только в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']

            try:
                content = content.replace('```json', '').replace('```', '').strip()
                code_changes = json.loads(content)
                return code_changes
            except json.JSONDecodeError:
                return {
                    "summary": "Создан базовый файл решения",
                    "changes": [{
                        "file_path": "solution.py",
                        "new_content": f'''# Решение для: {issue_body[:100]}

def solve_issue():
    """
    Автоматически сгенерированное решение.
    Задача: {issue_body[:200]}
    """
    return "Решение будет реализовано в следующих итерациях"

if __name__ == "__main__":
    result = solve_issue()
    print(f"Результат: {result}")'''
                    }]
                }
        else:
            print(f"❌ Ошибка генерации кода: {response.status_code}")
            return {"error": f"API error: {response.status_code}"}

    except Exception as e:
        print(f"❌ Ошибка генерации кода: {e}")
        return {"error": str(e)}
