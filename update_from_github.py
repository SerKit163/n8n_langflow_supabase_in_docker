#!/usr/bin/env python3
"""
Скрипт обновления проекта с GitHub с сохранением настроек
"""
import sys
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))

from installer.docker_manager import (
    docker_compose_down, docker_compose_up, get_docker_compose_command
)
from installer.utils import ensure_dir

console = Console()


def show_welcome():
    """Приветственное сообщение"""
    welcome_text = """
🔄 Обновление проекта с GitHub

Этот скрипт:
1. Обновит код с GitHub (git pull)
2. Сохранит ваши настройки (.env)
3. Перегенерирует конфигурационные файлы
4. Перезапустит сервисы с новой конфигурацией

Ваши данные (volumes) будут сохранены!
"""
    console.print(Panel(welcome_text, title="Обновление с GitHub", border_style="cyan"))


def check_git_repo():
    """Проверяет что это git репозиторий"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_current_branch():
    """Получает текущую ветку"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def update_from_github():
    """Обновляет код с GitHub"""
    console.print("\n[cyan]📥 Обновление кода с GitHub...[/cyan]")
    
    # Проверяем что это git репозиторий
    if not check_git_repo():
        console.print("[red]❌ Это не git репозиторий![/red]")
        console.print("   Клонируйте проект: git clone https://github.com/SerKit163/n8n_langflow_supabase_in_docker.git")
        return False
    
    # Получаем текущую ветку
    current_branch = get_current_branch()
    if not current_branch:
        console.print("[yellow]⚠ Не удалось определить текущую ветку[/yellow]")
        current_branch = "main"
    
    console.print(f"[cyan]Текущая ветка: {current_branch}[/cyan]")
    
    # Проверяем есть ли изменения
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            console.print("[yellow]⚠ У вас есть незакоммиченные изменения![/yellow]")
            if not Confirm.ask("Продолжить? (изменения могут быть потеряны)", default=False):
                return False
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось проверить статус: {e}[/yellow]")
    
    # Выполняем git pull
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Загрузка обновлений...", total=None)
            
            result = subprocess.run(
                ['git', 'pull', 'origin', current_branch],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            progress.update(task, completed=True)
            
            if result.returncode == 0:
                console.print("[green]✓ Код успешно обновлен с GitHub[/green]")
                if result.stdout.strip():
                    console.print(result.stdout)
                return True
            else:
                console.print(f"[red]❌ Ошибка при обновлении: {result.stderr}[/red]")
                return False
    except subprocess.TimeoutExpired:
        console.print("[red]❌ Таймаут при обновлении[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        return False


def backup_env():
    """Создает резервную копию .env"""
    env_file = Path(".env")
    if not env_file.exists():
        console.print("[yellow]⚠ Файл .env не найден[/yellow]")
        return None
    
    backup_dir = ensure_dir("backups")
    backup_file = backup_dir / ".env.backup"
    
    try:
        shutil.copy2(env_file, backup_file)
        console.print(f"[green]✓ Резервная копия .env создана: {backup_file}[/green]")
        return backup_file
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось создать резервную копию: {e}[/yellow]")
        return None


def load_env_config():
    """Загружает конфигурацию из существующего .env файла"""
    env_file = Path(".env")
    if not env_file.exists():
        console.print("[yellow]⚠ Файл .env не найден[/yellow]")
        console.print("   Будет использована новая установка через setup.py")
        return None
    
    console.print("\n[cyan]📖 Чтение текущей конфигурации из .env...[/cyan]")
    
    config = {}
    try:
        content = env_file.read_text(encoding='utf-8')
        
        # Парсим переменные из .env
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Убираем кавычки если есть
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                config[key] = value
        
        console.print(f"[green]✓ Загружено {len(config)} переменных из .env[/green]")
        return config
    except Exception as e:
        console.print(f"[red]❌ Ошибка при чтении .env: {e}[/red]")
        return None


def convert_env_to_config(env_config):
    """Конвертирует переменные .env в формат конфигурации для setup.py"""
    if not env_config:
        return None
    
    config = {}
    
    # Роутинг
    config['routing_mode'] = env_config.get('ROUTING_MODE', '')
    
    # Домены
    config['n8n_domain'] = env_config.get('N8N_DOMAIN', '')
    config['langflow_domain'] = env_config.get('LANGFLOW_DOMAIN', '')
    config['supabase_domain'] = env_config.get('SUPABASE_DOMAIN', '')
    config['ollama_domain'] = env_config.get('OLLAMA_DOMAIN', '')
    config['base_domain'] = env_config.get('BASE_DOMAIN', '')
    
    # Пути
    config['n8n_path'] = env_config.get('N8N_PATH', '/n8n')
    config['langflow_path'] = env_config.get('LANGFLOW_PATH', '/langflow')
    config['supabase_path'] = env_config.get('SUPABASE_PATH', '/supabase')
    config['ollama_path'] = env_config.get('OLLAMA_PATH', '/ollama')
    
    # Email для SSL
    config['letsencrypt_email'] = env_config.get('LETSENCRYPT_EMAIL', '')
    
    # Сервисы - проверяем какие включены (по умолчанию все включены для обратной совместимости)
    n8n_enabled_str = env_config.get('N8N_ENABLED', 'true').strip().lower()
    config['n8n_enabled'] = n8n_enabled_str != 'false'
    
    langflow_enabled_str = env_config.get('LANGFLOW_ENABLED', 'true').strip().lower()
    config['langflow_enabled'] = langflow_enabled_str != 'false'
    
    # Supabase всегда включен
    config['supabase_enabled'] = True
    
    # Ollama - только если явно включен в .env
    ollama_enabled_str = env_config.get('OLLAMA_ENABLED', '').strip().lower()
    config['ollama_enabled'] = ollama_enabled_str == 'true'
    
    # Порты - только для включенных сервисов, безопасное преобразование
    def safe_int(value, default):
        """Безопасно преобразует значение в int, возвращает default если пустое"""
        if not value or value.strip() == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def safe_float(value, default):
        """Безопасно преобразует значение в float, возвращает default если пустое"""
        if not value or value.strip() == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    # Порты - только для включенных сервисов
    if config['n8n_enabled']:
        config['n8n_port'] = safe_int(env_config.get('N8N_PORT', ''), 5678)
    if config['langflow_enabled']:
        config['langflow_port'] = safe_int(env_config.get('LANGFLOW_PORT', ''), 7860)
    # Supabase всегда включен
    config['supabase_port'] = safe_int(env_config.get('SUPABASE_PORT', ''), 8000)
    config['supabase_kb_port'] = safe_int(env_config.get('SUPABASE_KB_PORT', ''), 3000)
    if config['ollama_enabled']:
        config['ollama_port'] = safe_int(env_config.get('OLLAMA_PORT', ''), 11434)
    
    # Лимиты ресурсов - только для включенных сервисов
    if config['n8n_enabled']:
        config['n8n_memory_limit'] = env_config.get('N8N_MEMORY_LIMIT', '2g') or '2g'
        config['n8n_cpu_limit'] = safe_float(env_config.get('N8N_CPU_LIMIT', ''), 0.5)
    if config['langflow_enabled']:
        config['langflow_memory_limit'] = env_config.get('LANGFLOW_MEMORY_LIMIT', '4g') or '4g'
        config['langflow_cpu_limit'] = safe_float(env_config.get('LANGFLOW_CPU_LIMIT', ''), 0.5)
    # Supabase всегда включен
    config['supabase_memory_limit'] = env_config.get('SUPABASE_MEMORY_LIMIT', '1g') or '1g'
    config['supabase_cpu_limit'] = safe_float(env_config.get('SUPABASE_CPU_LIMIT', ''), 0.3)
    if config['ollama_enabled']:
        config['ollama_memory_limit'] = env_config.get('OLLAMA_MEMORY_LIMIT', '2g') or '2g'
        config['ollama_cpu_limit'] = safe_float(env_config.get('OLLAMA_CPU_LIMIT', ''), 1.0)
    
    # Supabase
    config['postgres_password'] = env_config.get('POSTGRES_PASSWORD', '')
    config['supabase_admin_login'] = env_config.get('SUPABASE_ADMIN_LOGIN', 'admin')
    config['supabase_admin_password'] = env_config.get('SUPABASE_ADMIN_PASSWORD', '')
    config['supabase_admin_password_hash'] = env_config.get('SUPABASE_ADMIN_PASSWORD_HASH', '')
    config['jwt_secret'] = env_config.get('JWT_SECRET', '')
    config['anon_key'] = env_config.get('ANON_KEY', '')
    config['service_role_key'] = env_config.get('SERVICE_ROLE_KEY', '')
    
    # Если сервисы не включены, не добавляем их настройки
    if not config['n8n_enabled']:
        config.pop('n8n_domain', None)
        config.pop('n8n_path', None)
        config.pop('n8n_port', None)
        config.pop('n8n_memory_limit', None)
        config.pop('n8n_cpu_limit', None)
    
    if not config['langflow_enabled']:
        config.pop('langflow_domain', None)
        config.pop('langflow_path', None)
        config.pop('langflow_port', None)
        config.pop('langflow_memory_limit', None)
        config.pop('langflow_cpu_limit', None)
    
    if not config['ollama_enabled']:
        # Очищаем настройки Ollama, чтобы они не попали в конфигурацию
        config.pop('ollama_domain', None)
        config.pop('ollama_path', None)
        config.pop('ollama_port', None)
        config.pop('ollama_memory_limit', None)
        config.pop('ollama_cpu_limit', None)
    
    return config


def regenerate_configs(config):
    """Перегенерирует конфигурационные файлы"""
    console.print("\n[cyan]⚙️ Перегенерация конфигурационных файлов...[/cyan]")
    
    try:
        from installer.config_generator import (
            generate_env_file, generate_docker_compose, generate_caddyfile
        )
        from installer.hardware_detector import detect_hardware
        
        # Определяем железо (для выбора правильного шаблона)
        console.print("Определение характеристик системы...")
        hardware = detect_hardware()
        
        # Генерируем .env
        console.print("Генерация .env...")
        generate_env_file(config)
        console.print("[green]✓ .env обновлен[/green]")
        
        # Генерируем docker-compose.yml
        console.print("Генерация docker-compose.yml...")
        generate_docker_compose(config, hardware)
        console.print("[green]✓ docker-compose.yml обновлен[/green]")
        
        # Генерируем Caddyfile
        console.print("Генерация Caddyfile...")
        generate_caddyfile(config)
        console.print("[green]✓ Caddyfile обновлен[/green]")
        
        return True
    except Exception as e:
        console.print(f"[red]❌ Ошибка при генерации конфигов: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


def restart_services():
    """Перезапускает сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    # Останавливаем
    console.print("Остановка сервисов...")
    if not docker_compose_down():
        console.print("[yellow]⚠ Не удалось остановить сервисы[/yellow]")
        if not Confirm.ask("Продолжить?", default=False):
            return False
    
    # Запускаем
    console.print("Запуск сервисов с новой конфигурацией...")
    if docker_compose_up():
        console.print("[green]✓ Сервисы успешно перезапущены![/green]")
        return True
    else:
        console.print("[red]❌ Ошибка при запуске сервисов[/red]")
        return False


def main():
    """Главная функция"""
    try:
        show_welcome()
        
        # Подтверждение
        if not Confirm.ask("\nПродолжить обновление?", default=True):
            console.print("[yellow]Обновление отменено[/yellow]")
            sys.exit(0)
        
        # 1. Создаем резервную копию .env
        backup_file = backup_env()
        
        # 2. Загружаем текущую конфигурацию
        env_config = load_env_config()
        
        if not env_config:
            console.print("\n[red]❌ Не удалось загрузить конфигурацию[/red]")
            console.print("   Запустите setup.py для первоначальной настройки")
            sys.exit(1)
        
        # 3. Обновляем код с GitHub
        if not update_from_github():
            console.print("\n[red]❌ Не удалось обновить код с GitHub[/red]")
            sys.exit(1)
        
        # 4. Конвертируем .env в формат конфигурации
        config = convert_env_to_config(env_config)
        
        if not config:
            console.print("\n[red]❌ Не удалось конвертировать конфигурацию[/red]")
            sys.exit(1)
        
        # 5. Перегенерируем конфигурационные файлы
        if not regenerate_configs(config):
            console.print("\n[red]❌ Не удалось перегенерировать конфигурацию[/red]")
            if backup_file:
                console.print(f"   Восстановите .env из резервной копии: {backup_file}")
            sys.exit(1)
        
        # 6. Перезапускаем сервисы
        if not restart_services():
            console.print("\n[red]❌ Не удалось перезапустить сервисы[/red]")
            if backup_file:
                console.print(f"   Восстановите .env из резервной копии: {backup_file}")
            sys.exit(1)
        
        console.print("\n[green]✓ Обновление завершено успешно![/green]")
        console.print("\n[cyan]Доступные сервисы:[/cyan]")
        
        # Показываем доступные сервисы
        if config.get('routing_mode') == 'subdomain':
            if config.get('n8n_domain'):
                console.print(f"  N8N: https://{config['n8n_domain']}")
            if config.get('langflow_domain'):
                console.print(f"  Langflow: https://{config['langflow_domain']}")
            if config.get('supabase_domain'):
                console.print(f"  Supabase: https://{config['supabase_domain']}")
        else:
            console.print(f"  N8N: http://localhost:{config.get('n8n_port', 5678)}")
            console.print(f"  Langflow: http://localhost:{config.get('langflow_port', 7860)}")
            console.print(f"  Supabase: http://localhost:{config.get('supabase_kb_port', 3000)}")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Обновление прервано пользователем[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Ошибка: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

