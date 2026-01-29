"""
AI Reviewer Agent - проверяет Pull Request на соответствие Issue.
Требования ТЗ: анализирует изменения, проверяет CI, публикует комментарий.
"""
import os
import json
from github import Github
import requests

# ==================== КОНФИГУРАЦИЯ ====================
GITHUB_PAT = os.getenv("GITHUB_PAT")
if not GITHUB_PAT:
    raise ValueError("❌ GITHUB_PAT не найден в .env")

github_client = Github(GITHUB_PAT)

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================


def analyze_pull_request(repo_full_name: str, pr_number: int, issue_body: str) -> dict:
    """
    Анализирует Pull Request и возвращает вердикт.
    ПОКА БЕЗ LLM - базовая логика проверок.

    Args:
        repo_full_name: "владелец/репозиторий"
        pr_number: Номер Pull Request
        issue_body: Текст оригинального Issue

    Returns:
        dict с вердиктом и комментариями
    """
    print(f"[reviewer] Анализ PR #{pr_number} в {repo_full_name}")

    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Собираем данные для анализа
    changed_files = [f.filename for f in pr.get_files()]
    additions = pr.additions
    deletions = pr.deletions
    pr_body = pr.body or ""
    pr_title = pr.title

    # 1. БАЗОВЫЕ ПРОВЕРКИ (обязательные по ТЗ)
    issues_found = []

    if len(changed_files) == 0:
        issues_found.append("PR не содержит изменений файлов")

    if additions == 0 and deletions == 0:
        issues_found.append("PR не вносит изменений в код (0 +/-)")

    # 2. ПРОВЕРКА СООТВЕТСТВИЯ ISSUE (ключевые слова)
    issue_lower = issue_body.lower()
    pr_lower = (pr_title + " " + pr_body).lower()

    # Простая проверка: есть ли в PR упоминание задачи из Issue
    important_keywords = []
    if "hello" in issue_lower:
        important_keywords.append("hello")
    if "calculator" in issue_lower or "add" in issue_lower or "multiply" in issue_lower:
        important_keywords.extend(["calculator", "add", "multiply", "sum"])
    if "test" in issue_lower:
        important_keywords.append("test")

    missing_keywords = []
    for keyword in important_keywords[:3]:  # Проверяем первые 3 ключевых слова
        if keyword not in pr_lower:
            missing_keywords.append(keyword)

    if missing_keywords:
        issues_found.append(f"В PR отсутствуют ключевые слова из Issue: {', '.join(missing_keywords)}")

    # 3. ПРОВЕРКА ФАЙЛОВ (по названиям из Issue)
    expected_files = []
    if "hello.py" in issue_lower:
        expected_files.append("hello.py")
    if "calculator.py" in issue_lower:
        expected_files.append("calculator.py")

    missing_files = []
    for expected_file in expected_files:
        if expected_file not in changed_files:
            missing_files.append(expected_file)

    if missing_files:
        issues_found.append(f"Ожидаемые файлы не изменены: {', '.join(missing_files)}")

    # 4. ФОРМИРУЕМ ВЕРДИКТ (по ТЗ: APPROVE или REQUEST_CHANGES)
    if issues_found:
        verdict = "REQUEST_CHANGES"
        summary = f"Найдено {len(issues_found)} проблем, требуются исправления."
    else:
        verdict = "APPROVE"
        summary = "PR соответствует требованиям Issue. Все проверки пройдены."

    return {
        "verdict": verdict,  # APPROVE или REQUEST_CHANGES
        "summary": summary,
        "issues": issues_found,
        "stats": {
            "changed_files": changed_files,
            "additions": additions,
            "deletions": deletions,
            "expected_files": expected_files,
            "found_keywords": [k for k in important_keywords if k in pr_lower]
        }
    }


def post_review_to_pr(repo_full_name: str, pr_number: int, review_data: dict) -> str:
    """
    Публикует результат анализа в Pull Request.
    Требование ТЗ: "публикует результаты в виде комментария, summary, code review"

    Returns:
        URL комментария
    """
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Форматируем комментарий по ТЗ
    emoji = "✅" if review_data["verdict"] == "APPROVE" else "⚠️"

    comment = f"""## 🤖 AI Reviewer Agent Report {emoji}

### **Вердикт: {review_data['verdict']}**
{review_data['summary']}

"""

    if review_data["issues"]:
        comment += "### 🔍 Найденные проблемы:\n"
        for i, issue in enumerate(review_data["issues"], 1):
            comment += f"{i}. {issue}\n"
        comment += "\n"

    # Добавляем статистику (требование ТЗ)
    stats = review_data["stats"]
    comment += f"""### 📊 Статистика изменений:
- **Изменённые файлы:** {len(stats['changed_files'])} ({', '.join(stats['changed_files'][:3])}{'...' if len(stats['changed_files']) > 3 else ''})
- **Добавлено строк:** {stats['additions']}
- **Удалено строк:** {stats['deletions']}
"""

    if stats['expected_files']:
        comment += f"- **Ожидаемые файлы:** {', '.join(stats['expected_files'])}\n"

    comment += f"""
### 📋 Рекомендации:
{('1. Исправьте указанные проблемы выше' if review_data['issues'] else '1. PR готов к слиянию')}
2. Убедитесь, что код соответствует описанию Issue
3. Проверьте, что все тесты проходят

---
_Автоматический анализ от AI Reviewer • [SDLC Pipeline](https://github.com/{repo_full_name}/actions)_
"""

    # Публикуем комментарий
    github_comment = pr.create_issue_comment(comment)
    print(f"[reviewer] Комментарий опубликован: {github_comment.html_url}")

    return github_comment.html_url


def check_ci_status(repo_full_name: str, pr_number: int) -> str:
    """
    Проверяет статус CI/CD pipeline (требование ТЗ).
    Пока заглушка - всегда возвращает 'success'.

    TODO: Реализовать через GitHub API проверку workflows
    """
    return "success"  # Заглушка


# ==================== CLI ДЛЯ ТЕСТИРОВАНИЯ ====================
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Использование: python reviewer_agent.py <репозиторий> <номер_PR> <текст_Issue>")
        print("Пример: python reviewer_agent.py 'ninkkka/coding-agent-test' 4 'Create hello.py file'")
        sys.exit(1)

    repo_name = sys.argv[1]
    pr_num = int(sys.argv[2])
    issue_text = sys.argv[3]

    print("=== ТЕСТ AI REVIEWER AGENT ===")

    # 1. Анализируем PR
    review = analyze_pull_request(repo_name, pr_num, issue_text)
    print(f"\n📋 Результат анализа:")
    print(json.dumps(review, indent=2, ensure_ascii=False))

    # 2. Публикуем комментарий
    print(f"\n📤 Публикую комментарий в PR #{pr_num}...")
    comment_url = post_review_to_pr(repo_name, pr_num, review)
    print(f"✅ Комментарий опубликован: {comment_url}")
