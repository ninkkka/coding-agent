import os
from github import Github, GithubException
import git
import tempfile
import shutil
import base64
import json

GITHUB_TOKEN = os.getenv("GH_PAT") or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")


def test_github_connection():
    """Проверка подключения к GitHub"""
    try:
        github_client = Github(GITHUB_TOKEN)
        user = github_client.get_user()
        print(f"✅ Подключено к GitHub как: {user.login}")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к GitHub: {e}")
        return False


def get_issue_content(repo_full_name, issue_number):
    """Получение контента Issue"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)
        issue = repo.get_issue(number=issue_number)
        return issue.title, issue.body or ""
    except Exception as e:
        print(f"❌ Ошибка получения Issue: {e}")
        return "", ""


def get_repo_files(repo_full_name, max_files=50):
    """Получение списка файлов в репозитории"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)

        contents = repo.get_contents("")
        files = []

        def traverse_contents(contents, path=""):
            for content in contents:
                if content.type == "dir":
                    try:
                        sub_contents = repo.get_contents(content.path)
                        traverse_contents(sub_contents, content.path)
                    except:
                        pass
                else:
                    if content.path.endswith(('.py', '.md', '.txt', '.json', '.yml', '.yaml')):
                        files.append({
                            'path': content.path,
                            'name': content.name,
                            'size': content.size
                        })
                        if len(files) >= max_files:
                            return

        traverse_contents(contents)
        return files[:max_files]
    except Exception as e:
        print(f"⚠️ Не удалось получить файлы репозитория: {e}")
        return []


def create_branch(repo_full_name, branch_name):
    """Создание новой ветки от main"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)

        main_ref = repo.get_git_ref("heads/main")
        main_sha = repo.get_branch("main").commit.sha

        repo.create_git_ref(f"refs/heads/{branch_name}", main_sha)
        print(f"✅ Ветка '{branch_name}' создана")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания ветки: {e}")

        try:
            repo.get_branch(branch_name)
            print(f"✅ Ветка '{branch_name}' уже существует")
            return True
        except:
            return False


def apply_code_changes(repo_full_name, branch_name, files_to_change, commit_message):
    """Применение изменений к коду в репозитории"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)

        branch = repo.get_branch(branch_name)
        base_tree = repo.get_git_tree(branch.commit.sha)

        tree_elements = []

        for file_path, new_content in files_to_change.items():
            try:
                try:
                    file_content = repo.get_contents(file_path, ref=branch_name)
                    repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        sha=file_content.sha,
                        branch=branch_name
                    )
                except:
                    # Создаем новый файл
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=new_content,
                        branch=branch_name
                    )

                print(f"✅ Файл '{file_path}' обновлен")

            except Exception as e:
                print(f"⚠️ Ошибка обновления файла '{file_path}': {e}")

        return True

    except Exception as e:
        print(f"❌ Ошибка применения изменений: {e}")
        return False


def create_pull_request(repo_full_name, branch_name, issue_title, issue_number):
    """Создание Pull Request"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)
        
        pr_title = f"Fix Issue #{issue_number}: {issue_title}"
        pr_body = f"""
## Автоматически созданный Pull Request

**Связан с Issue: #{issue_number}**

Этот PR был автоматически создан Coding Agent.

### Изменения:
- Автоматическое решение задачи из Issue #{issue_number}
- Внесены изменения согласно анализу AI

### Для ревьюера:
1. Проверьте соответствие кода требованиям Issue
2. Убедитесь, что код работает корректно
3. Проверьте стиль и качество кода

*Этот PR создан автоматически системой SDLC.*
"""

        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base="main"
        )

        pr.create_issue_comment(f"Этот PR связан с Issue #{issue_number}")

        return pr.html_url

    except Exception as e:
        print(f"❌ Ошибка создания PR: {e}")
        return None


def get_latest_ai_review_verdict(repo_full_name, pr_number):
    """Получение вердикта от AI Reviewer"""
    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)

        comments = pr.get_issue_comments()

        ai_reviewer_comments = []
        for comment in comments:
            if "🤖 AI Code Review Report" in comment.body or "AI Reviewer" in comment.body:
                ai_reviewer_comments.append({
                    'created_at': comment.created_at,
                    'body': comment.body,
                    'user': comment.user.login
                })

        if not ai_reviewer_comments:
            return "PENDING"

        latest_comment = sorted(ai_reviewer_comments, 
                              key=lambda x: x['created_at'])[-1]['body']

        if "✅ Все проверки пройдены" in latest_comment or "APPROVE" in latest_comment:
            return "APPROVE"
        elif "❌ Требуются изменения" in latest_comment or "REQUEST_CHANGES" in latest_comment:
            return "REQUEST_CHANGES"
        else:
            return "COMMENT"

    except Exception as e:
        print(f"⚠️ Ошибка получения вердикта ревьюера: {e}")
        return "PENDING"
