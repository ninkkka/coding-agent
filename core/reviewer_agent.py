#!/usr/bin/env python3
"""
AI Reviewer Agent - проверяет Pull Request на соответствие Issue.
"""
import os
import sys
import json
import argparse
import requests
from github import Github

# Поддерживаем все варианты имен переменных
GITHUB_TOKEN = os.getenv("GH_PAT") or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")

if not GITHUB_TOKEN:
    print("❌ GitHub token not found")
    sys.exit(1)

if not DEEPSEEK_KEY:
    print("❌ DeepSeek API key not found")
    sys.exit(1)

github_client = Github(GITHUB_TOKEN)
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def analyze_pull_request(repo_full_name: str, pr_number: int) -> dict:
    """
    Анализирует Pull Request с помощью AI.
    """
    print(f"[reviewer] Анализ PR #{pr_number} в {repo_full_name}")
    
    try:
        repo = github_client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Получаем информацию о PR
        files_changed = []
        for file in pr.get_files():
            files_changed.append({
                "filename": file.filename,
                "additions": file.additions,
                "deletions": file.deletions,
                "status": file.status
            })
        
        # Получаем связанный Issue
        issue_body = "Не удалось получить описание Issue"
        try:
            if pr.body and "#" in pr.body:
                import re
                issue_match = re.search(r'#(\d+)', pr.body)
                if issue_match:
                    issue_num = int(issue_match.group(1))
                    issue = repo.get_issue(issue_num)
                    issue_body = issue.body or "Нет описания"
        except:
            pass
        
        # Подготавливаем контекст для AI
        context = f"""
        PULL REQUEST ИНФОРМАЦИЯ:
        - Заголовок: {pr.title}
        - Описание: {pr.body or 'Нет описания'}
        - Автор: {pr.user.login}
        - Изменений: +{pr.additions}/-{pr.deletions}
        - Файлов: {pr.changed_files}
        
        СВЯЗАННАЯ ISSUE:
        {issue_body}
        
        ИЗМЕНЕННЫЕ ФАЙЛЫ:
        """
        
        for file in files_changed[:10]:
            context += f"\n- {file['filename']} (+{file['additions']}/-{file['deletions']})"
        
        # Анализ с помощью AI через requests
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": """Ты — опытный код-ревьюер. Проверяй код на:
                1. Соответствие требованиям Issue
                2. Качество кода (стиль, структура, best practices)
                3. Потенциальные ошибки
                4. Полноту реализации
                
                Отвечай на русском в JSON формате."""},
                {"role": "user", "content": f"Проверь этот Pull Request:\n\n{context}"}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        llm_output = result["choices"][0]["message"]["content"]
        analysis = json.loads(llm_output)
        
        # Определяем вердикт
        issues = analysis.get("issues_found", [])
        if issues and len(issues) > 0:
            verdict = "REQUEST_CHANGES"
        else:
            verdict = "APPROVE"
        
        return {
            "verdict": verdict,
            "summary": analysis.get("summary", "Анализ завершен"),
            "analysis": analysis,
            "pr_info": {
                "title": pr.title,
                "files_changed": pr.changed_files,
                "additions": pr.additions,
                "deletions": pr.deletions
            }
        }
        
    except Exception as e:
        print(f"[reviewer] Ошибка анализа: {e}")
        return {
            "verdict": "COMMENT",
            "summary": f"Ошибка анализа: {e}",
            "analysis": {"issues_found": [f"Ошибка: {e}"]},
            "pr_info": {}
        }


def post_review_comment(repo_full_name: str, pr_number: int, review_data: dict) -> str:
    """
    Публикует результат анализа в Pull Request.
    """
    try:
        repo = github_client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        emoji = "✅" if review_data["verdict"] == "APPROVE" else "⚠️"
        analysis = review_data["analysis"]
        
        comment = f"""## 🤖 AI Reviewer Agent Report {emoji}

### **Вердикт: {review_data['verdict']}**
{review_data['summary']}

"""
        
        if analysis.get("issues_found"):
            comment += "### 🔍 Найденные проблемы:\n"
            for i, issue in enumerate(analysis["issues_found"], 1):
                comment += f"{i}. {issue}\n"
            comment += "\n"
        
        if analysis.get("suggestions"):
            comment += "### 💡 Предложения по улучшению:\n"
            for i, suggestion in enumerate(analysis["suggestions"][:5], 1):
                comment += f"{i}. {suggestion}\n"
            comment += "\n"
        
        # Добавляем статистику
        stats = review_data["pr_info"]
        comment += f"""### 📊 Статистика изменений:
- **Файлов изменено:** {stats.get('files_changed', 0)}
- **Добавлено строк:** {stats.get('additions', 0)}
- **Удалено строк:** {stats.get('deletions', 0)}

---
_Это автоматический обзор от AI Reviewer. При вердикте 'REQUEST_CHANGES' Coding Agent внесёт исправления._
"""
        
        # Публикуем комментарий
        github_comment = pr.create_issue_comment(comment)
        
        # Также добавляем formal review
        try:
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
        except:
            pass  # Если нет прав на formal review
        
        print(f"[reviewer] Комментарий опубликован: {github_comment.html_url}")
        return github_comment.html_url
        
    except Exception as e:
        print(f"[reviewer] Ошибка публикации комментария: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='AI Reviewer Agent')
    parser.add_argument('--pr-number', type=int, required=True, help='PR number')
    parser.add_argument('--repo', type=str, required=True, help='Repository (owner/name)')
    parser.add_argument('--test', action='store_true', help='Test mode without posting')
    
    args = parser.parse_args()
    
    print("=== AI REVIEWER AGENT ===")
    print(f"Repository: {args.repo}")
    print(f"PR: #{args.pr_number}")
    
    try:
        # Анализируем PR
        review = analyze_pull_request(args.repo, args.pr_number)
        
        print(f"\n📋 Результат анализа:")
        print(f"   Вердикт: {review['verdict']}")
        print(f"   Summary: {review['summary']}")
        
        if not args.test:
            # Публикуем результат
            print(f"\n📤 Публикую комментарий в PR #{args.pr_number}...")
            comment_url = post_review_comment(args.repo, args.pr_number, review)
            print(f"✅ Комментарий опубликован: {comment_url}")
        else:
            print(f"\n🧪 Тестовый режим - комментарий не публикуется")
        
        # Возвращаем вердикт
        sys.exit(0 if review['verdict'] == 'APPROVE' else 1)
        
    except Exception as e:
        print(f"💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
