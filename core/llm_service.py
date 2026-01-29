import os
import json
import requests

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("❌ Не найден DEEPSEEK_API_KEY в .env")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"  # Или "deepseek-coder" для кода


def generate_code_changes(issue_description, existing_code_context=""):
    """
    Анализирует Issue и возвращает изменения кода через DeepSeek API.
    """
    prompt = f"""
Ты — ассистент разработчика (Coding Agent). Твоя задача — проанализировать описание Issue в GitHub и предложить изменения в коде.

ОПИСАНИЕ ЗАДАЧИ ИЗ ISSUE:
{issue_description}

КОНТЕКСТ (если есть):
{existing_code_context}

ИНСТРУКЦИИ:
1. Проанализируй задачу и определи, какие файлы нужно изменить или создать.
2. Верни ответ в СТРОГОМ JSON-формате:
{{
  "plan": "краткий план из 2-3 шагов",
  "changes": [
    {{
      "file_path": "путь/к/файлу.py",
      "action": "create" или "modify",
      "new_content": "полный новый код файла"
    }}
  ]
}}
3. Если нужно изменить существующий файл, new_content должен содержать ПОЛНЫЙ текст файла после изменений.
4. Изменяй только то, что необходимо для решения задачи.
5. Если в задаче явно указано имя файла (например, 'hello.py'), используй его.
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Ты — точный ассистент разработчика. Отвечай только валидным JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 4000,
        "stream": False
    }

    try:
        print(f"[llm] Отправляю запрос к DeepSeek ({MODEL_NAME})...")
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        llm_output = result["choices"][0]["message"]["content"]
        print(f"[llm] Получен ответ от DeepSeek")

        # Парсим JSON
        parsed_response = json.loads(llm_output)
        return parsed_response

    except json.JSONDecodeError as e:
        print(f"[!] DeepSeek вернул невалидный JSON: {e}")
        print(f"[!] Ответ модели: {llm_output[:200]}...")
        raise
    except Exception as e:
        print(f"[!] DeepSeek API error: {e}")

        # Fallback
        if "hello" in issue_description.lower():
            file_name = "hello.py"
            file_content = '''def say_hello():
    return "Hello from AI Agent!"

if __name__ == "__main__":
    print(say_hello())'''
        else:
            file_name = "generated.py"
            file_content = f'''# Generated for: {issue_description[:50]}

def solution():
    pass

if __name__ == "__main__":
    solution()'''

        return {
            "plan": f"Fallback: создан {file_name}",
            "changes": [{
                "file_path": file_name,
                "action": "create",
                "new_content": file_content
            }]
        }
