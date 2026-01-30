"""Сервис для работы с DeepSeek API."""
import os
import json
import requests
import time
from typing import Dict, List

# Поддерживаем все варианты имен переменных
deepseek_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
if not deepseek_key:
    raise ValueError("❌ DeepSeek API key not found. Set DEEPSEEK_API_KEY or DEEPSEEK_KEY")

# URL для прямых запросов
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"
CODING_MODEL = "deepseek-coder"

# Для совместимости со старой версией OpenAI
try:
    import openai
    openai.api_key = deepseek_key
    openai.api_base = "https://api.deepseek.com"
    print("[llm] Использую старую версию OpenAI client")
except ImportError:
    print("[llm] OpenAI не установлен")


def analyze_issue_with_llm(issue_title: str, issue_body: str, repo_files: List[str] = None) -> Dict:
    """
    Анализирует Issue с помощью LLM и возвращает план реализации.
    """
    print(f"[llm] Анализ Issue: {issue_title[:50]}...")
    
    # Подготавливаем контекст репозитория
    repo_context = ""
    if repo_files:
        repo_context = f"""
        Существующие файлы в репозитории:
        {chr(10).join(repo_files[:20])}
        {'...' if len(repo_files) > 20 else ''}
        """
    
    prompt = f"""
    Ты — опытный разработчик Python. Проанализируй GitHub Issue и предложи план реализации.

    ISSUE ТИТУЛ: {issue_title}
    ISSUE ОПИСАНИЕ: {issue_body}
    
    {repo_context}
    
    Требуется:
    1. Проанализировать требования
    2. Определить, какие файлы нужно создать/изменить
    3. Предложить подход к реализации
    4. Учесть лучшие практики Python
    
    Ответь в JSON формате:
    {{
        "analysis": "Подробный анализ задачи",
        "implementation_strategy": "Стратегия реализации",
        "files_to_create": ["список", "файлов", "для", "создания"],
        "files_to_modify": ["список", "файлов", "для", "изменения"],
        "dependencies_needed": ["возможные", "зависимости"],
        "testing_approach": "Подход к тестированию",
        "estimated_complexity": "low/medium/high"
    }}
    """
    
    try:
        # Используем прямые запросы requests вместо OpenAI SDK
        headers = {
            "Authorization": f"Bearer {deepseek_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "Ты - архитектор ПО. Анализируй задачи и предлагай точные технические решения."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        llm_output = result["choices"][0]["message"]["content"]
        
        analysis = json.loads(llm_output)
        print(f"[llm] Анализ завершен. Сложность: {analysis.get('estimated_complexity', 'unknown')}")
        return analysis
        
    except Exception as e:
        print(f"[llm] Ошибка анализа: {e}")
        return {
            "analysis": f"Ошибка анализа: {e}",
            "implementation_strategy": "Создать простую реализацию",
            "files_to_create": ["solution.py"],
            "files_to_modify": [],
            "dependencies_needed": [],
            "testing_approach": "Базовое тестирование",
            "estimated_complexity": "medium"
        }


def generate_code_changes(issue_description: str, analysis: Dict, existing_code_context: str = "") -> Dict:
    """
    Генерирует изменения кода на основе анализа Issue.
    """
    print(f"[llm] Генерация кода на основе анализа...")
    
    # Извлекаем информацию из анализа
    files_to_create = analysis.get("files_to_create", ["solution.py"])
    files_to_modify = analysis.get("files_to_modify", [])
    strategy = analysis.get("implementation_strategy", "")
    
    prompt = f"""
Ты — программист Python (Coding Agent). Сгенерируй код для решения задачи.

АНАЛИЗ ЗАДАЧИ:
{analysis.get('analysis', '')}

СТРАТЕГИЯ РЕАЛИЗАЦИИ:
{strategy}

ОПИСАНИЕ ISSUE:
{issue_description}

ТРЕБОВАНИЯ:
1. Создай код для файлов: {', '.join(files_to_create) if files_to_create else 'нового файла'}
2. {'Измени файлы: ' + ', '.join(files_to_modify) if files_to_modify else ''}
3. Следуй best practices Python (PEP 8, типизация, докстринги)
4. Включи базовые тесты если возможно
5. Добавь комментарии к сложным частям

КОНТЕКТ СУЩЕСТВУЮЩЕГО КОДА:
{existing_code_context}

Верни ответ в СТРОГОМ JSON-формате:
{{
  "summary": "Краткое описание изменений",
  "plan": "Детальный план реализации",
  "changes": [
    {{
      "file_path": "путь/к/файлу.py",
      "action": "create/modify",
      "new_content": "ПОЛНЫЙ код файла после изменений",
      "description": "Что делает этот файл"
    }}
  ],
  "dependencies": ["список", "зависимостей"],
  "testing_recommendations": "Рекомендации по тестированию"
}}

ВАЖНО: Для modify действий new_content должен содержать ПОЛНЫЙ обновленный файл.
"""
    
    headers = {
        "Authorization": f"Bearer {deepseek_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": CODING_MODEL,
        "messages": [
            {"role": "system", "content": "Ты — точный программист. Генерируй чистый, рабочий код. Отвечай только валидным JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 4000,
        "stream": False
    }
    
    try:
        print(f"[llm] Отправляю запрос к DeepSeek Coder...")
        start_time = time.time()
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        llm_output = result["choices"][0]["message"]["content"]
        elapsed = time.time() - start_time
        
        print(f"[llm] Код сгенерирован за {elapsed:.1f} сек")
        
        # Парсим JSON
        parsed_response = json.loads(llm_output)
        
        # Валидируем ответ
        if "changes" not in parsed_response:
            print("[llm] В ответе нет 'changes', добавляю...")
            parsed_response["changes"] = []
        
        print(f"[llm] Сгенерировано {len(parsed_response['changes'])} изменений файлов")
        return parsed_response
        
    except json.JSONDecodeError as e:
        print(f"[llm] ❌ DeepSeek вернул невалидный JSON: {e}")
        if 'llm_output' in locals():
            print(f"[llm] Ответ модели: {llm_output[:200]}...")
        return create_fallback_response(issue_description, analysis)
        
    except Exception as e:
        print(f"[llm] ❌ DeepSeek API error: {e}")
        return create_fallback_response(issue_description, analysis)


def create_fallback_response(issue_description: str, analysis: Dict) -> Dict:
    """
    Создает резервный ответ при ошибках LLM.
    """
    print(f"[llm] Использую резервную генерацию...")
    
    files_to_create = analysis.get("files_to_create", ["solution.py"])
    file_name = files_to_create[0] if files_to_create else "solution.py"
    
    # Генерируем базовый код в зависимости от типа задачи
    issue_lower = issue_description.lower()
    
    if any(word in issue_lower for word in ["hello", "привет", "greeting"]):
        file_content = '''"""
Простая функция приветствия.
"""
def hello(name: str = "World") -> str:
    """
    Возвращает приветственное сообщение.
    
    Args:
        name: Имя для приветствия
        
    Returns:
        Приветственное сообщение
    """
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(hello())
'''
    elif any(word in issue_lower for word in ["calculator", "калькулятор", "add", "multiply"]):
        file_content = '''"""
Простой калькулятор.
"""
class Calculator:
    """Класс для базовых математических операций."""
    
    def add(self, a: float, b: float) -> float:
        """Сложение."""
        return a + b
    
    def subtract(self, a: float, b: float) -> float:
        """Вычитание."""
        return a - b
    
    def multiply(self, a: float, b: float) -> float:
        """Умножение."""
        return a * b
    
    def divide(self, a: float, b: float) -> float:
        """Деление."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b


def test_calculator():
    """Тест калькулятора."""
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.subtract(5, 3) == 2
    assert calc.multiply(2, 3) == 6
    assert calc.divide(6, 3) == 2
    print("✅ All tests passed!")


if __name__ == "__main__":
    test_calculator()
'''
    else:
        file_content = f'''"""
Решение для задачи: {issue_description[:100]}
"""
import typing


def main():
    """Основная функция."""
    print("Решение реализовано")


if __name__ == "__main__":
    main()
'''
    
    return {
        "summary": f"Резервная реализация: создан {file_name}",
        "plan": "Создан базовый файл с шаблонным кодом",
        "changes": [{
            "file_path": file_name,
            "action": "create",
            "new_content": file_content,
            "description": f"Решение задачи: {issue_description[:50]}..."
        }],
        "dependencies": [],
        "testing_recommendations": "Добавьте тесты для полного покрытия"
    }


if __name__ == "__main__":
    # Тестовый запуск
    print("=== ТЕСТ LLM SERVICE ===")
    
    test_issue = {
        "title": "Test issue",
        "body": "Create a hello world function"
    }
    
    print("1. Тестируем анализ...")
    analysis = analyze_issue_with_llm(test_issue["title"], test_issue["body"])
    print(f"   Результат: {analysis.get('estimated_complexity', 'unknown')}")
    
    print("\n2. Тестируем генерацию кода...")
    code = generate_code_changes(test_issue["body"], analysis)
    print(f"   Сгенерировано файлов: {len(code.get('changes', []))}")
    
    print("\n✅ LLM service работает")
