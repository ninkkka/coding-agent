"""
AI Reviewer Agent - проверяет Pull Request на соответствие Issue.
Требования ТЗ: анализирует изменения, проверяет CI, публикует комментарий.
"""
import os
import json
import sys
from github import Github
from openai import OpenAI
import requests
import re

# ==================== КОНФИГУРАЦИЯ ====================
# Поддерживаем оба варианта токенов для GitHub Actions
GITHUB_TOKEN = os.getenv("GH_PAT") or os.getenv("GITHUB_PAT")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not GITHUB_TOKEN:
    raise ValueError("❌ GitHub token not found. Set GH_PAT or GITHUB_PAT")
if not DEEPSEEK_API_KEY:
    raise ValueError("❌ DeepSeek API key not found. Set DEEPSEEK_API_KEY")

github_client = Github(GITHUB_TOKEN)
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================


def get_pr_details(repo_full_name: str, pr_number: int) -> dict:
    """Получает детальную информацию о PR."""
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Получаем diff
    diff_url = pr.diff_url
    diff_response = requests.get(diff_url)
    diff_content = diff_response.text if diff_response.status_code == 200 else ""

    # Получаем измененные файлы с содержимым
    files = []
    for file in pr.get_files():
        files.append({
            "filename": file.filename,
            "additions": file.additions,
            "deletions": file.deletions,
            "status": file.status,
            "patch": file.patch[:1000] if file.patch else ""  # Ограничиваем размер
        })

    # Получаем коммиты
    commits = [c.commit.message for c in pr.get_commits()[:5]]

    return {
        "title": pr.title,
        "body": pr.body or "",
        "author": pr.user.login,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "changed_files": pr.changed_files,
        "diff": diff_content[:3000],  # Ограничиваем для контекста LLM
        "files": files,
        "commits": commits,
        "html_url": pr.html_url
    }


def get_issue_content_from_pr(repo_full_name: str, pr_number: int) -> str:
    """Извлекает описание Issue из связанного с PR."""
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Ищем ссылку на Issue в описании PR
    issue_pattern = r"#(\d+)"
    matches = re.findall(issue_pattern, pr.body or "")

    if matches:
        issue_number = int(matches[0])
        issue = repo.get_issue(issue_number)
        return issue.body or ""

    # Если Issue не найден, используем заголовок PR
    return f"Task from PR: {pr.title}"


def check_ci_status(repo_full_name: str, pr_number: int) -> dict:
    """
    Проверяет статус CI/CD pipeline (требование ТЗ).
    """
    try:
        repo = github_client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)

        # Получаем последние статусы проверок
        statuses = list(repo.get_commit(pr.head.sha).get_statuses())

        ci_status = {
            "total": len(statuses),
            "success": 0,
            "pending": 0,
            "failure": 0,
            "details": []
        }

        for status in statuses:
            ci_status["details"].append({
                "context": status.context,
                "state": status.state,
                "description": status.description or "",
                "target_url": status.target_url or ""
            })

            if status.state == "success":
                ci_status["success"] += 1
            elif status.state == "pending":
                ci_status["pending"] += 1
            elif status.state == "failure":
                ci_status["failure"] += 1

        # Определяем общий статус
        if ci_status["failure"] > 0:
            ci_status["overall"] = "failure"
        elif ci_status["pending"] > 0:
            ci_status["overall"] = "pending"
        elif ci_status["success"] > 0:
            ci_status["overall"] = "success"
        else:
            ci_status["overall"] = "no_checks"

        return ci_status

    except Exception as e:
        print(f"⚠️ Ошибка при проверке CI: {e}")
        return {"overall": "error", "details": []}


def analyze_with_ai(issue_body: str, pr_details: dict, ci_status: dict) -> dict:
    """
    Анализирует PR с помощью DeepSeek AI.
    """
    try:
        # Подготовка контекста для AI
        context = f"""
        ЗАДАЧА ИЗ ISSUE:
        {issue_body}

        ДЕТАЛИ PULL REQUEST:
        - Заголовок: {pr_details['title']}
        - Описание: {pr_details['body']}
        - Автор: {pr_details['author']}
        - Изменения: +{pr_details['additions']}/-{pr_details['deletions']} строк
        - Файлов изменено: {pr_details['changed_files']}

        CI/CD СТАТУС:
        - Общий статус: {ci_status.get('overall', 'unknown')}
        - Успешно: {ci_status.get('success', 0)}
        - В процессе: {ci_status.get('pending', 0)}
        - Провалено: {ci_status.get('failure', 0)}

        ДИФФ ИЗМЕНЕНИЙ:
        {pr_details['diff'][:2000]}

        Пожалуйста, проанализируй:
        1. Соответствуют ли изменения требованиям Issue?
        2. Качество кода (стиль, структура, best practices)
        3. Потенциальные проблемы или баги
        4. Полнота реализации
        5. Учет результатов CI

        Верни ответ в JSON формате:
        {{
            "summary": "Общая оценка",
            "issues_found": ["список проблем"],
            "suggestions": ["предложения по улучшению"],
            "code_quality": "оценка качества кода (1-5)",
            "requirements_match": "соответствие требованиям (1-5)",
            "verdict": "APPROVE или REQUEST_CHANGES",
            "detailed_review": "подробный анализ изменений"
        }}
        """

        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты - опытный код-ревьюер на Python. Будь строгим, но конструктивным."},
                {"role": "user", "content": context}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        ai_response = json.loads(response.choices[0].message.content)

        # Учитываем CI статус в вердикте
        if ci_status.get("overall") == "failure":
            ai_response["verdict"] = "REQUEST_CHANGES"
            ai_response["issues_found"].append("CI/CD проверки провалены")

        return ai_response

    except Exception as e:
        print(f"⚠️ Ошибка AI анализа: {e}")
        # Резервный ответ
        return {
            "summary": "Анализ не удался из-за ошибки AI",
            "issues_found": ["Не удалось выполнить AI анализ"],
            "suggestions": ["Проверьте вручную"],
            "code_quality": "3",
            "requirements_match": "3",
            "verdict": "REQUEST_CHANGES",
            "detailed_review": f"Ошибка: {e}"
        }

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================


def analyze_pull_request(repo_full_name: str, pr_number: int) -> dict:
    """
    Анализирует Pull Request и возвращает вердикт.
    """
    print(f"[reviewer] Анализ PR #{pr_number} в {repo_full_name}")

    # 1. Получаем данные
    issue_body = get_issue_content_from_pr(repo_full_name, pr_number)
    pr_details = get_pr_details(repo_full_name, pr_number)
    ci_status = check_ci_status(repo_full_name, pr_number)

    # 2. AI анализ
    ai_analysis = analyze_with_ai(issue_body, pr_details, ci_status)

    # 3. Формируем итоговый результат
    return {
        "verdict": ai_analysis.get("verdict", "REQUEST_CHANGES"),
        "summary": ai_analysis.get("summary", "Анализ не завершен"),
        "ai_analysis": ai_analysis,
        "ci_status": ci_status,
        "pr_details": {
            "title": pr_details["title"],
            "changed_files": pr_details["changed_files"],
            "additions": pr_details["additions"],
            "deletions": pr_details["deletions"]
        }
    }


def post_review_to_pr(repo_full_name: str, pr_number: int, review_data: dict) -> str:
    """
    Публикует результат анализа в Pull Request.
    """
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Эмодзи для вердикта
    emoji = "✅" if review_data["verdict"] == "APPROVE" else "⚠️"

    # Форматируем комментарий
    comment = f"""## 🤖 AI Reviewer Agent Report {emoji}

### **Вердикт: {review_data['verdict']}**
{review_data['summary']}

"""

    ai_data = review_data["ai_analysis"]

    # Проблемы и предложения
    if ai_data.get("issues_found"):
        comment += "### 🔍 Найденные проблемы:\n"
        for i, issue in enumerate(ai_data["issues_found"][:5], 1):
            comment += f"{i}. {issue}\n"
        comment += "\n"

    if ai_data.get("suggestions"):
        comment += "### 💡 Предложения по улучшению:\n"
        for i, suggestion in enumerate(ai_data["suggestions"][:3], 1):
            comment += f"{i}. {suggestion}\n"
        comment += "\n"

    # CI/CD статус
    ci = review_data["ci_status"]
    comment += f"""### ⚙️ CI/CD Статус:
- **Общий статус:** {ci.get('overall', 'unknown').upper()}
- **Успешных проверок:** {ci.get('success', 0)}
- **Проваленных:** {ci.get('failure', 0)}
"""

    if ci.get('details'):
        comment += "- **Проверки:** "
        for check in ci['details'][:3]:
            state_emoji = "✅" if check['state'] == 'success' else "❌" if check['state'] == 'failure' else "⏳"
            comment += f"{state_emoji} {check['context']} "
        comment += "\n\n"

    # Статистика
    stats = review_data["pr_details"]
    comment += f"""### 📊 Статистика изменений:
- **Изменённые файлы:** {stats['changed_files']}
- **Добавлено строк:** {stats['additions']}
- **Удалено строк:** {stats['deletions']}
- **Качество кода:** {ai_data.get('code_quality', 'N/A')}/5
- **Соответствие требованиям:** {ai_data.get('requirements_match', 'N/A')}/5

---
**Подробный анализ:**
{ai_data.get('detailed_review', 'Нет подробного анализа')[:500]}...

_Это автоматический обзор от AI Reviewer. Если вердикт 'REQUEST_CHANGES', Coding Agent внесёт исправления._
_Ссылка на workflow: {pr.html_url}/checks_
"""

    # Публикуем комментарий
    github_comment = pr.create_issue_comment(comment)

    # Также добавляем review (требование GitHub)
    if review_data["verdict"] == "APPROVE":
        pr.create_review(
            body="✅ AI Reviewer: Изменения одобрены",
            event="APPROVE"
        )
    else:
        pr.create_review(
            body="⚠️ AI Reviewer: Требуются исправления",
            event="REQUEST_CHANGES"
        )

    print(f"[reviewer] Комментарий опубликован: {github_comment.html_url}")
    return github_comment.html_url

# ==================== CLI ИНТЕРФЕЙС ====================


def main():
    """Главная функция для CLI и GitHub Actions."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Reviewer Agent')
    parser.add_argument('--pr-number', type=int, required=True, help='PR number')
    parser.add_argument('--repo', type=str, required=True, help='Repository (owner/name)')
    parser.add_argument('--test', action='store_true', help='Test mode without posting')

    args = parser.parse_args()

    print(f"=== AI REVIEWER AGENT ===")
    print(f"Repository: {args.repo}")
    print(f"PR: #{args.pr_number}")

    try:
        # Анализируем PR
        review = analyze_pull_request(args.repo, args.pr_number)

        print(f"\n📋 Результат анализа:")
        print(f"   Вердикт: {review['verdict']}")
        print(f"   Summary: {review['summary']}")
        print(f"   CI Status: {review['ci_status'].get('overall', 'unknown')}")

        if not args.test:
            # Публикуем результат
            print(f"\n📤 Публикую комментарий в PR #{args.pr_number}...")
            comment_url = post_review_to_pr(args.repo, args.pr_number, review)
            print(f"✅ Комментарий опубликован: {comment_url}")
        else:
            print(f"\n🧪 Тестовый режим - комментарий не публикуется")

        # Возвращаем вердикт для GitHub Actions
        sys.exit(0 if review['verdict'] == 'APPROVE' else 1)

    except Exception as e:
        print(f"💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
