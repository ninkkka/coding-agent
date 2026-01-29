"""
Главный CLI-скрипт Coding Agent.
Запуск: python coding_agent.py --issue 1 --repo ваш_логин/репозиторий
"""
import argparse
import sys
import os
from dotenv import load_dotenv
import time

# ==================== 1. ЗАГРУЗКА И ПРОВЕРКА ТОКЕНОВ ====================
load_dotenv()  # Загружаем переменные из .env
# --- ПРОВЕРКА ТОКЕНОВ (ОБНОВЛЕНО ДЛЯ DEEPSEEK) ---
GITHUB_PAT = os.getenv("GITHUB_PAT")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not GITHUB_PAT:
    print("❌ Ошибка: Добавьте GITHUB_PAT в .env файл")
    print("   Как получить: GitHub → Settings → Developer settings → Personal access tokens")
    sys.exit(1)

if not DEEPSEEK_API_KEY:
    print("❌ Ошибка: Добавьте DEEPSEEK_API_KEY в .env файл")
    print("   Получите ключ: https://platform.deepseek.com/ → API Keys")
    sys.exit(1)

print("✅ Токены загружены: GITHUB_PAT и DEEPSEEK_API_KEY")
# --- КОНЕЦ ПРОВЕРКИ ---

# ==================== 2. НАСТРОЙКА ПУТЕЙ И ИМПОРТОВ ====================
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from core.github_client import get_issue_content, apply_code_changes, create_pull_request
    from core.llm_service import generate_code_changes
    print("✅ Модули загружены")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("   Убедитесь, что есть папка 'core' с файлами github_client.py и llm_service.py")
    sys.exit(1)


# ==================== 3. ОСНОВНАЯ ЛОГИКА АГЕНТА ====================
def main(issue_number, repo_full_name):
    print(f"\n🚀 Запуск Coding Agent для Issue #{issue_number} в {repo_full_name}")
    print("=" * 50)

    MAX_ATTEMPTS = 3
    current_attempt = 1
    pr_url = None

    try:
        # 1. Получаем задачу из Issue
        issue_title, issue_body = get_issue_content(repo_full_name, issue_number)
        print(f"📋 Задача: {issue_title}")
        print(f"📝 Описание: {issue_body[:100]}...")

        while current_attempt <= MAX_ATTEMPTS:
            print(f"\n🔄 ПОПЫТКА {current_attempt}/{MAX_ATTEMPTS}")
            print("-" * 40)

            if current_attempt > 1:
                print("👀 Жду вердикт от AI Reviewer...")
                time.sleep(10)  # Даём время на анализ

            # 2. Генерируем план изменений
            print("🧠 Генерация изменений с помощью LLM...")
            llm_response = generate_code_changes(issue_body)

            print(f"📝 План: {llm_response.get('plan', 'План не указан')}")

            # 3. Подготавливаем файлы
            files_to_change = {}
            changes = llm_response.get("changes", [])

            if not changes:
                print("⚠️ LLM не предложил изменений. Использую шаблон...")
                files_to_change = {
                    f"attempt_{current_attempt}.py": f"# Попытка {current_attempt}\nprint('Fix for Issue #{issue_number}')"
                }
            else:
                for change in changes:
                    file_path = change.get("file_path", f"generated_{current_attempt}.py")
                    files_to_change[file_path] = change.get("new_content", "# Файл создан агентом")

            # 4. Создаём/обновляем ветку и PR
            branch_name = f"agent/issue-{issue_number}"
            commit_message = f"Fix Issue #{issue_number} (attempt {current_attempt}): {issue_title[:30]}..."

            if current_attempt == 1:
                # Первая попытка: создаём новую ветку и PR
                print(f"🌳 Создаю ветку '{branch_name}'...")
                apply_code_changes(repo_full_name, branch_name, files_to_change, commit_message)

                print(f"🔗 Создаю Pull Request...")
                pr_url = create_pull_request(repo_full_name, branch_name, issue_title, issue_number)
                print(f"✅ PR создан: {pr_url}")
            else:
                # Последующие попытки: обновляем существующий PR
                print(f"✏️ Обновляю существующий PR (попытка {current_attempt})...")
                apply_code_changes(repo_full_name, branch_name, files_to_change, commit_message)
                print(f"✅ Код обновлён в существующем PR: {pr_url}")

            # 5. Проверяем вердикт Reviewer (если не первая попытка)
            if current_attempt == 1:
                print("\n⏳ Жду запуск AI Reviewer (может занять до 60 сек)...")
                time.sleep(30)  # Даём время GitHub Actions запуститься

            # Извлекаем номер PR из URL
            pr_number = int(pr_url.split("/")[-1]) if pr_url else None

            if pr_number:
                # Проверяем вердикт Reviewer
                verdict = get_latest_review_verdict(repo_full_name, pr_number)

                print(f"🤖 Вердикт AI Reviewer: {verdict}")

                if verdict == "APPROVE":
                    print("=" * 50)
                    print(f"🎉 УСПЕХ! Задача решена с {current_attempt} попытки.")
                    print(f"🔗 Pull Request: {pr_url}")
                    return pr_url
                elif verdict == "REQUEST_CHANGES":
                    print("⚠️ AI Reviewer запросил исправления. Готовлю новую попытку...")
                    current_attempt += 1
                    continue
                else:
                    print("⏳ AI Reviewer ещё не ответил. Жду...")
                    time.sleep(20)
                    continue
            else:
                print("❌ Не удалось получить номер PR")
                break

            current_attempt += 1

        # Если вышли из цикла (все попытки исчерпаны)
        print("=" * 50)
        print(f"🚨 ДОСТИГНУТ ЛИМИТ ПОПЫТОК ({MAX_ATTEMPTS})")
        print(f"⚠️ Задача не решена после всех попыток")
        print(f"🔗 Последний PR: {pr_url}")

        # Оставляем комментарий в Issue
        try:
            repo = github_client.get_repo(repo_full_name)
            issue = repo.get_issue(number=issue_number)
            issue.create_comment(f"## 🚨 Coding Agent остановлен\nДостигнут лимит в {MAX_ATTEMPTS} попыток. Последний PR: {pr_url}")
        except:
            pass

        return pr_url

    except Exception as e:
        print(f"\n💥 Критическая ошибка:")
        print(f"   Тип: {type(e).__name__}")
        print(f"   Сообщение: {e}")
        raise


# ==================== 4. CLI ИНТЕРФЕЙС ====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Coding Agent: автоматически создаёт Pull Request для GitHub Issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python %(prog)s --issue 1 --repo username/test-repo
  python %(prog)s --issue 5 --repo organization/project
        """
    )

    parser.add_argument(
        '--issue',
        type=int,
        required=True,
        help='Номер Issue в GitHub (обязательно)'
    )

    parser.add_argument(
        '--repo',
        type=str,
        required=True,
        help='Репозиторий в формате "владелец/название" (обязательно)'
    )

    args = parser.parse_args()

    # Запускаем главную функцию
    main(args.issue, args.repo)
