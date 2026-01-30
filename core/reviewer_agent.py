"""
AI Reviewer Agent для автоматического code review.
Запуск из GitHub Actions при создании/обновлении PR.
"""
import os
import sys
import json
import requests
from github import Github

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def get_pr_context(repo_full_name: str, pr_number: int) -> Dict:
    """Получение контекста PR"""
    github_client = Github(GITHUB_TOKEN)
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    diff_url = pr.diff_url
    diff_response = requests.get(diff_url)
    diff_content = diff_response.text if diff_response.status_code == 200 else ""

    issue_number = None
    issue_content = ""
    if pr.body:
        import re
        issue_match = re.search(r'Issue.*?#(\d+)', pr.body)
        if issue_match:
            issue_number = int(issue_match.group(1))
            try:
                issue = repo.get_issue(issue_number)
                issue_content = f"{issue.title}\n\n{issue.body}"
            except:
                issue_content = "Issue не найдена"

    files = list(pr.get_files())
    file_changes = []

    for file in files[:10]:
        try:
            old_content = ""
            new_content = ""

            if file.previous_filename:
                try:
                    old_content = repo.get_contents(file.previous_filename, ref=pr.base.ref).decoded_content.decode()
                except:
                    pass

            try:
                new_content = repo.get_contents(file.filename, ref=pr.head.ref).decoded_content.decode()
            except:
                pass

            file_changes.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "patch": file.patch[:1000] if file.patch else "",
                "old_content": old_content[:2000],
                "new_content": new_content[:2000]
            })
        except Exception as e:
            print(f"⚠️ Ошибка обработки файла {file.filename}: {e}")

    return {
        "pr_title": pr.title,
        "pr_body": pr.body or "",
        "pr_author": pr.user.login,
        "issue_number": issue_number,
        "issue_content": issue_content,
        "file_changes": file_changes,
        "diff_summary": f"Изменено файлов: {len(files)}"
    }


def analyze_pr_with_ai(pr_context: Dict) -> Dict:
    """Анализ PR с помощью AI"""

    file_changes_str = ""
    for i, change in enumerate(pr_context["file_changes"], 1):
        file_changes_str += f"""
{i}. Файл: {change['filename']}
   Статус: {change['status']}
   Добавлено строк: {change['additions']}
   Удалено строк: {change['deletions']}

   Старое содержимое (первые 1000 символов):
   {change['old_content'][:1000]}

   Новое содержимое (первые 1000 символов):
   {change['new_content'][:1000]}
   """

    prompt = f"""
Ты - опытный code reviewer. Проведи анализ Pull Request.

**Информация о PR:**
Заголовок: {pr_context['pr_title']}
Автор: {pr_context['pr_author']}
Описание: {pr_context['pr_body']}

**Связанная Issue:**
{pr_context['issue_content']}

**Изменения в файлах:**
{file_changes_str}

**Проверь следующие аспекты:**
1. Соответствие кода требованиям Issue
2. Качество кода (PEP8, читаемость, структура)
3. Наличие ошибок или багов
4. Полнота реализации
5. Корректность тестов (если есть)

**Критерии оценки:**
- APPROVE: код соответствует всем требованиям, нет критических замечаний
- REQUEST_CHANGES: есть существенные проблемы, требующие исправления
- COMMENT: есть незначительные замечания, но код в целом рабочий

Верни ответ в формате JSON:
{{
    "verdict": "APPROVE | REQUEST_CHANGES | COMMENT",
    "summary": "Краткое резюме ревью",
    "issues_found": ["список найденных проблем"],
    "suggestions": ["предложения по улучшению"],
    "score": 1-10
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
                {"role": "system", "content": "Ты строгий но справедливый code reviewer. Будь объективным."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 3000
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']

            try:
                content = content.replace('```json', '').replace('```', '').strip()
                review = json.loads(content)
                return review
            except json.JSONDecodeError:
                # Фоллбэк
                return {
                    "verdict": "COMMENT",
                    "summary": "Не удалось полностью проанализировать изменения",
                    "issues_found": ["Проблема с парсингом AI-ответа"],
                    "suggestions": ["Проверьте код вручную"],
                    "score": 5
                }
        else:
            print(f"❌ Ошибка DeepSeek API: {response.status_code}")
            return {
                "verdict": "COMMENT",
                "summary": f"Ошибка AI анализа: {response.status_code}",
                "issues_found": [],
                "suggestions": [],
                "score": 5
            }

    except Exception as e:
        print(f"❌ Ошибка анализа PR: {e}")
        return {
            "verdict": "COMMENT",
            "summary": f"Ошибка: {str(e)}",
            "issues_found": [],
            "suggestions": [],
            "score": 5
        }


def post_review_comment(repo_full_name: str, pr_number: int, review_result: Dict):
    """Публикация результата ревью в PR"""
    github_client = Github(GITHUB_TOKEN)
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    emoji = "✅" if review_result["verdict"] == "APPROVE" else "⚠️" if review_result["verdict"] == "REQUEST_CHANGES" else "💬"

    comment = f"""
{emoji} **🤖 AI Code Review Report**

**Вердикт:** {review_result['verdict']}
**Оценка:** {review_result.get('score', 'N/A')}/10

### 📋 Краткое резюме:
{review_result['summary']}

"""

    if review_result.get('issues_found'):
        comment += """
### 🔍 Найденные проблемы:
"""
        for issue in review_result['issues_found'][:10]:
            comment += f"- {issue}\n"

    if review_result.get('suggestions'):
        comment += """
### 💡 Предложения по улучшению:
"""
        for suggestion in review_result['suggestions'][:10]:
            comment += f"- {suggestion}\n"

    comment += """
---
*Это автоматический review от AI Reviewer Agent.*
"""

    pr.create_issue_comment(comment)

    if review_result["verdict"] == "APPROVE":
        event = "APPROVE"
    elif review_result["verdict"] == "REQUEST_CHANGES":
        event = "REQUEST_CHANGES"
    else:
        event = "COMMENT"

    pr.create_review(
        body=review_result["summary"],
        event=event,
        comments=[]
    )

    print(f"✅ Review опубликован. Вердикт: {review_result['verdict']}")


def main():
    """Главная функция AI Reviewer"""
    if len(sys.argv) != 3:
        print("Использование: python reviewer_agent.py <repo> <pr_number>")
        print("Пример: python reviewer_agent.py username/repo 1")
        sys.exit(1)

    repo_full_name = sys.argv[1]
    try:
        pr_number = int(sys.argv[2])
    except ValueError:
        print("❌ Номер PR должен быть числом")
        sys.exit(1)

    print(f"🚀 Запуск AI Reviewer для PR #{pr_number} в {repo_full_name}")
    print("=" * 50)

    if not GITHUB_TOKEN:
        print("❌ Не найден GitHub Token")
        sys.exit(1)

    if not DEEPSEEK_API_KEY:
        print("❌ Не найден DeepSeek API Key")
        sys.exit(1)

    print("📋 Получение данных PR...")
    pr_context = get_pr_context(repo_full_name, pr_number)

    print(f"   Заголовок: {pr_context['pr_title']}")
    print(f"   Изменено файлов: {len(pr_context['file_changes'])}")

    print("🧠 Анализ изменений AI...")
    review_result = analyze_pr_with_ai(pr_context)

    print(f"   Вердикт: {review_result['verdict']}")
    print(f"   Оценка: {review_result.get('score', 'N/A')}/10")

    print("💬 Публикация review...")
    post_review_comment(repo_full_name, pr_number, review_result)

    print("=" * 50)
    print(f"✅ AI Reviewer завершил работу")
    print(f"   Результат: {review_result['verdict']}")


if __name__ == "__main__":
    main()
