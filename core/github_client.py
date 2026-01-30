"""Клиент для работы с GitHub API."""
from github import Github, GithubException
import os
import json
import time
from datetime import datetime

# Используем токен из окружения
github_token = os.getenv("GH_PAT") or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
if not github_token:
    raise ValueError("❌ GitHub token not found. Set GH_PAT, GITHUB_PAT or GITHUB_TOKEN")

github_client = Github(github_token)


def test_github_connection():
    """Тестирует подключение к GitHub API."""
    try:
        user = github_client.get_user()
        rate_limit = github_client.get_rate_limit().core
        print(f"✅ GitHub подключен: {user.login}")
        print(f"   Осталось запросов: {rate_limit.remaining}/{rate_limit.limit}")
        print(f"   Сброс через: {rate_limit.reset}")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к GitHub: {e}")
        return False


def get_issue_content(repo_full_name, issue_number):
    """Получает заголовок и описание Issue."""
    try:
        print(f"[github] Получение Issue #{issue_number} из {repo_full_name}")
        repo = github_client.get_repo(repo_full_name)
        issue = repo.get_issue(number=issue_number)
        
        if not issue:
            raise Exception(f"Issue #{issue_number} не найдена")
        
        title = issue.title
        body = issue.body or "Описание отсутствует"
        
        print(f"[github] Issue получена: {title[:50]}...")
        return title, body
        
    except GithubException as e:
        if e.status == 404:
            raise Exception(f"Issue #{issue_number} не найдена в репозитории {repo_full_name}")
        else:
            raise Exception(f"Ошибка GitHub API при получении Issue: {e}")
    except Exception as e:
        raise Exception(f"Неожиданная ошибка: {e}")


def create_branch(repo_full_name, branch_name, base_branch="main"):
    """Создаёт новую ветку в репозитории."""
    try:
        print(f"[github] Создание ветки '{branch_name}' от '{base_branch}'")
        repo = github_client.get_repo(repo_full_name)
        
        # Получаем коммит основной ветки
        try:
            base_branch_ref = repo.get_branch(base_branch)
            base_sha = base_branch_ref.commit.sha
        except GithubException:
            # Если основной ветки нет, используем дефолтную
            base_sha = repo.get_branch(repo.default_branch).commit.sha
        
        # Создаём ветку
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
            print(f"[github] Ветка '{branch_name}' создана успешно")
            return True
        except GithubException as e:
            if "Reference already exists" in str(e):
                print(f"[github] Ветка '{branch_name}' уже существует")
                return True
            else:
                raise e
                
    except Exception as e:
        raise Exception(f"Ошибка при создании ветки: {e}")


def apply_code_changes(repo_full_name, branch_name, files_to_change, commit_message):
    """Применяет изменения кода в указанной ветке."""
    try:
        print(f"[github] Применение изменений в ветку '{branch_name}'")
        repo = github_client.get_repo(repo_full_name)
        
        files_processed = 0
        errors = []
        
        for file_path, content in files_to_change.items():
            try:
                # Пытаемся получить текущий файл
                try:
                    file = repo.get_contents(file_path, ref=branch_name)
                    # Файл существует - обновляем
                    result = repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        sha=file.sha,
                        branch=branch_name
                    )
                    print(f"   ✅ Обновлён файл: {file_path}")
                    files_processed += 1
                    
                except GithubException as e:
                    if e.status == 404:
                        # Файл не существует - создаём новый
                        result = repo.create_file(
                            path=file_path,
                            message=commit_message,
                            content=content,
                            branch=branch_name
                        )
                        print(f"   ✅ Создан файл: {file_path}")
                        files_processed += 1
                    else:
                        errors.append(f"{file_path}: {e}")
                        print(f"   ❌ Ошибка с файлом {file_path}: {e}")
                        
            except Exception as e:
                errors.append(f"{file_path}: {e}")
                print(f"   ❌ Неожиданная ошибка с файлом {file_path}: {e}")
        
        if errors:
            print(f"[github] Обработано {files_processed} файлов, ошибок: {len(errors)}")
            if len(errors) > 0:
                raise Exception(f"Ошибки при обработке файлов: {errors[:3]}")
        
        print(f"[github] Успешно обработано {files_processed} файлов")
        return True
        
    except Exception as e:
        raise Exception(f"Ошибка при применении изменений: {e}")


def create_pull_request(repo_full_name, branch_name, issue_title, issue_number):
    """Создаёт Pull Request."""
    try:
        print(f"[github] Создание Pull Request для ветки '{branch_name}'")
        repo = github_client.get_repo(repo_full_name)
        
        # Создаём заголовок и описание PR
        pr_title = f"Fix Issue #{issue_number}: {issue_title[:100]}"
        
        pr_body = f"""
## 🤖 Автоматическое исправление Issue #{issue_number}

**Задача:** {issue_title}

### Что сделано:
- Проанализированы требования Issue
- Сгенерирован соответствующий код
- Созданы/обновлены необходимые файлы

### Детали реализации:
- **Ветка:** `{branch_name}`
- **Целевая ветка:** `{repo.default_branch}`
- **Создано:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Следующие шаги:
1. AI Reviewer проверит изменения
2. При необходимости будут внесены исправления
3. Процесс повторится до успешного завершения

---
*Этот Pull Request создан автоматически **Coding Agent** как часть SDLC pipeline.*
"""
        
        # Создаём PR
        try:
            pr = repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=repo.default_branch
            )
            
            print(f"[github] Pull Request создан: #{pr.number} - {pr.title}")
            
            # Связываем PR с Issue
            try:
                pr.create_issue_comment(f"Связано с Issue #{issue_number}")
                print(f"[github] PR #{pr.number} связан с Issue #{issue_number}")
            except:
                print(f"[github] Не удалось связать PR с Issue (может не быть прав)")
            
            # Добавляем метки
            try:
                pr.add_to_labels("automated", "coding-agent", "ai-generated")
                print(f"[github] Метки добавлены к PR #{pr.number}")
            except:
                print(f"[github] Не удалось добавить метки (может не быть прав)")
            
            # Получаем URL PR
            pr_url = pr.html_url
            print(f"[github] URL PR: {pr_url}")
            
            return pr_url
            
        except GithubException as e:
            if "A pull request already exists" in str(e):
                print(f"[github] PR для ветки '{branch_name}' уже существует")
                # Пытаемся найти существующий PR
                pulls = repo.get_pulls(state='open', head=branch_name)
                for pull in pulls:
                    if pull.head.ref == branch_name:
                        print(f"[github] Найден существующий PR: #{pull.number}")
                        return pull.html_url
                raise Exception(f"PR уже существует, но не удалось найти его")
            else:
                raise e
                
    except Exception as e:
        raise Exception(f"Ошибка при создании Pull Request: {e}")


def get_latest_ai_review_verdict(repo_full_name, pr_number):
    """Получает последний вердикт от AI Reviewer из комментариев PR."""
    try:
        print(f"[github] Получение вердикта AI Reviewer для PR #{pr_number}")
        repo = github_client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Получаем последние комментарии (новые в начале)
        comments = list(pr.get_issue_comments())
        comments.reverse()  # Начинаем с самых новых
        
        for comment in comments:
            body = comment.body or ""
            
            # Ищем комментарии от AI Reviewer
            if "🤖 AI Reviewer Agent Report" in body or "AI Reviewer" in body:
                # Извлекаем вердикт
                if "Вердикт: APPROVE" in body or "VERDICT: APPROVE" in body:
                    print(f"[github] Найден вердикт APPROVE от AI Reviewer")
                    return "APPROVE"
                elif "Вердикт: REQUEST_CHANGES" in body or "VERDICT: REQUEST_CHANGES" in body:
                    print(f"[github] Найден вердикт REQUEST_CHANGES от AI Reviewer")
                    return "REQUEST_CHANGES"
                elif "Вердикт: COMMENT" in body or "VERDICT: COMMENT" in body:
                    print(f"[github] Найден вердикт COMMENT от AI Reviewer")
                    return "COMMENT"
        
        # Если AI Reviewer ещё не ответил, проверяем reviews
        try:
            reviews = list(pr.get_reviews())
            for review in reviews:
                if review.state == "APPROVED":
                    print(f"[github] Найден APPROVE в reviews")
                    return "APPROVE"
                elif review.state == "CHANGES_REQUESTED":
                    print(f"[github] Найден REQUEST_CHANGES в reviews")
                    return "REQUEST_CHANGES"
        except:
            pass
        
        print(f"[github] AI Reviewer ещё не ответил")
        return "PENDING"
        
    except Exception as e:
        print(f"[github] Ошибка при получении вердикта: {e}")
        return "ERROR"


def get_repo_files(repo_full_name, branch="main"):
    """Получает список файлов в репозитории."""
    try:
        print(f"[github] Получение списка файлов из {repo_full_name}")
        repo = github_client.get_repo(repo_full_name)
        
        def get_contents(path=""):
            contents = repo.get_contents(path, ref=branch)
            files = []
            
            for content in contents:
                if content.type == "file":
                    files.append(content.path)
                elif content.type == "dir":
                    # Рекурсивно получаем файлы из поддиректорий
                    if path.count("/") < 2:  # Максимум 3 уровня вложенности
                        files.extend(get_contents(content.path))
                    else:
                        files.append(f"{content.path}/")
            
            return files
        
        files = get_contents()
        print(f"[github] Найдено {len(files)} файлов")
        return files[:50]  # Ограничиваем для контекста
        
    except Exception as e:
        print(f"[github] Ошибка при получении файлов: {e}")
        return []


if __name__ == "__main__":
    # Тестовый запуск
    print("=== ТЕСТ GITHUB CLIENT ===")
    
    if test_github_connection():
        print("✅ GitHub client работает")
    else:
        print("❌ GitHub client не работает")