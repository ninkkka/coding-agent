"""
Модуль для работы с GitHub API.
Содержит все функции, необходимые Coding Agent'у:
- чтение Issue,
- создание ветки,
- применение изменений в коде,
- создание Pull Request.
"""
import os
from github import Github, UnknownObjectException
from dotenv import load_dotenv
load_dotenv()

# -------------------- КОНФИГУРАЦИЯ --------------------
# Используем GITHUB_PAT из .env (совместимость с исходным проектом)
GITHUB_TOKEN = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("❌ Не найден GitHub токен. Добавьте GITHUB_PAT в .env файл.")

# Инициализируем клиент GitHub
github_client = Github(GITHUB_TOKEN)


# -------------------- ОСНОВНЫЕ ФУНКЦИИ --------------------

def get_issue_content(repo_full_name: str, issue_number: int) -> tuple[str, str]:
    """
    Получает заголовок и описание Issue из репозитория.

    Args:
        repo_full_name: Полное имя репозитория в формате 'логин/название-репо'
        issue_number: Номер Issue

    Returns:
        Кортеж (title, body) — заголовок и описание Issue

    Raises:
        Exception: Если Issue не найдена или нет доступа
    """
    print(f"[github] Получаем Issue #{issue_number} из {repo_full_name}...")
    repo = github_client.get_repo(repo_full_name)
    issue = repo.get_issue(number=issue_number)
    return issue.title, issue.body


def apply_code_changes(
    repo_full_name: str,
    branch_name: str,
    files_dict: dict,
    commit_message: str
) -> None:
    """
    Создаёт новую ветку, применяет изменения в файлах и создаёт коммит.

    Args:
        repo_full_name: Полное имя репозитория
        branch_name: Имя новой ветки (например, 'agent/issue-1')
        files_dict: Словарь {путь_к_файлу: новое_содержимое}
        commit_message: Сообщение коммита

    Raises:
        Exception: При ошибках работы с GitHub API
    """
    repo = github_client.get_repo(repo_full_name)

    # 1. Получаем SHA последнего коммита основной ветки
    try:
        main_branch = repo.get_branch("main")
        base_sha = main_branch.commit.sha
    except UnknownObjectException:
        # Если ветка называется 'master' вместо 'main'
        main_branch = repo.get_branch("master")
        base_sha = main_branch.commit.sha

    # 2. Создаём новую ветку (или используем существующую)
    ref_name = f"refs/heads/{branch_name}"
    try:
        repo.create_git_ref(ref=ref_name, sha=base_sha)
        print(f"[github] Создана новая ветка: {branch_name}")
    except Exception:
        # Если ветка уже существует, ничего страшного — будем использовать её
        print(f"[github] Ветка {branch_name} уже существует, используем её")

    # 3. Применяем изменения к каждому файлу
    for file_path, new_content in files_dict.items():
        try:
            # Пытаемся получить текущее содержимое файла в целевой ветке
            existing_file = repo.get_contents(file_path, ref=branch_name)
            # Файл существует — обновляем
            repo.update_file(
                path=file_path,
                message=f"{commit_message}",
                content=new_content,
                sha=existing_file.sha,
                branch=branch_name
            )
            print(f"  ✓ Обновлён файл: {file_path}")
        except UnknownObjectException:
            # Файл не существует — создаём новый
            repo.create_file(
                path=file_path,
                message=f"{commit_message}",
                content=new_content,
                branch=branch_name
            )
            print(f"  ✓ Создан файл: {file_path}")

    print(f"[github] Все изменения закоммичены в ветку '{branch_name}'")


def create_pull_request(
    repo_full_name: str,
    branch_name: str,
    issue_title: str,
    issue_number: int
) -> str:
    """
    Создаёт Pull Request из рабочей ветки в основную ветку.

    Args:
        repo_full_name: Полное имя репозитория
        branch_name: Имя ветки с изменениями
        issue_title: Заголовок Issue (для названия PR)
        issue_number: Номер Issue (для ссылки в описании)

    Returns:
        URL созданного Pull Request

    Raises:
        Exception: При ошибке создания PR
    """
    repo = github_client.get_repo(repo_full_name)

    # Формируем название и описание PR
    pr_title = f"Fix Issue #{issue_number}: {issue_title[:50]}..."
    pr_body = f"""
## Описание
Этот Pull Request был автоматически сгенерирован Coding Agent'ом для решения Issue #{issue_number}.

## Ссылки
- **Issue**: #{issue_number}
- **Ветка с изменениями**: {branch_name}

## Изменения
Автоматически сгенерированные изменения на основе описания задачи.
"""

    # Создаём Pull Request
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base="main"  # Пробуем 'main', если нет — будет ошибка
    )

    print(f"[github] Создан Pull Request: {pr.html_url}")
    return pr.html_url


def get_repo_file_list(repo_full_name: str, path: str = "") -> list:
    """
    Получает список файлов в репозитории (для будущего расширения).

    Args:
        repo_full_name: Полное имя репозитория
        path: Путь внутри репозитория (по умолчанию — корень)

    Returns:
        Список путей к файлам
    """
    repo = github_client.get_repo(repo_full_name)
    contents = repo.get_contents(path)

    file_list = []
    for content in contents:
        if content.type == "file":
            file_list.append(content.path)
        elif content.type == "dir":
            # Рекурсивно получаем файлы из поддиректорий
            file_list.extend(get_repo_file_list(repo_full_name, content.path))

    return file_list


def get_latest_review_verdict(repo_full_name: str, pr_number: int) -> str:
    """
    Проверяет последний комментарий AI Reviewer и возвращает вердикт.
    Ищет комментарии, содержащие 'AI Reviewer Agent Report'.

    Returns:
        "APPROVE", "REQUEST_CHANGES" или "PENDING" (если нет комментария)
    """
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    # Получаем все комментарии
    comments = pr.get_issue_comments()

    # Ищем комментарий от нашего Reviewer
    for comment in reversed(list(comments)):  # С конца (последние сначала)
        if "AI Reviewer Agent Report" in comment.body:
            if "Вердикт: APPROVE" in comment.body:
                return "APPROVE"
            elif "Вердикт: REQUEST_CHANGES" in comment.body:
                return "REQUEST_CHANGES"

    return "PENDING"  # Если комментария ещё нет


# -------------------- ТЕСТОВЫЙ ВЫЗОВ --------------------
if __name__ == "__main__":
    # Быстрая проверка, что модуль работает
    print("=== Тест github_client.py ===")
    print(f"GitHub клиент инициализирован: {'✅' if github_client else '❌'}")
    print(f"Токен установлен: {'✅' if GITHUB_TOKEN else '❌'}")

    # Проверяем, что можем получить пользователя
    try:
        user = github_client.get_user()
        print(f"Текущий пользователь: {user.login}")
        print("✅ Модуль готов к работе!")
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
