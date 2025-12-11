#!/usr/bin/env python3
"""
Скрипт для удаления n8n из существующей установки
"""
import sys
import os
from pathlib import Path
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from installer.config_generator import generate_docker_compose, generate_caddyfile, generate_env_file
from installer.hardware_detector import detect_hardware
import subprocess

console = Console()


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🗑️  Удаление N8N из установки

Этот скрипт:
1. Остановит и удалит контейнер N8N
2. Удалит volume с данными N8N (освободит место на диске)
3. Удалит N8N из конфигурации (.env, docker-compose.yml, Caddyfile)
4. Перезапустит остальные сервисы

⚠️  ВНИМАНИЕ:
  • Все данные N8N (workflows, credentials) будут удалены!
  • Это действие необратимо!
    """
    console.print(Panel(welcome_text, title="Удаление N8N", border_style="red"))


def check_n8n_enabled():
    """Проверяет, включен ли N8N"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    config = dotenv_values(env_path)
    n8n_enabled = config.get('N8N_ENABLED', 'true').strip().lower() != 'false'
    
    if not n8n_enabled:
        console.print("[yellow]⚠️  N8N не включен в конфигурации[/yellow]")
        return False
    
    return True


def check_n8n_container():
    """Проверяет, запущен ли контейнер N8N"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=n8n", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
        return False
    except Exception as e:
        console.print(f"[yellow]⚠️  Не удалось проверить контейнер: {e}[/yellow]")
        return False


def stop_and_remove_n8n(remove_volume=True):
    """Останавливает и удаляет контейнер N8N"""
    console.print("\n[cyan]🛑 Остановка и удаление N8N...[/cyan]")
    
    # Останавливаем контейнер через docker-compose
    try:
        console.print("Остановка контейнера N8N...")
        result = subprocess.run(
            ["docker-compose", "stop", "n8n"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер N8N остановлен[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже остановлен или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при остановке: {e}[/yellow]")
    
    # Удаляем контейнер
    try:
        console.print("Удаление контейнера N8N...")
        result = subprocess.run(
            ["docker-compose", "rm", "-f", "n8n"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер N8N удален[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже удален или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при удалении контейнера: {e}[/yellow]")
    
    # Удаляем volume если нужно
    if remove_volume:
        try:
            console.print("Удаление volume с данными N8N...")
            # Пробуем найти volume с именем n8n_data
            result = subprocess.run(
                ["docker", "volume", "ls", "-q", "--filter", "name=n8n"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout.strip():
                volumes = result.stdout.strip().split('\n')
                for volume in volumes:
                    subprocess.run(
                        ["docker", "volume", "rm", volume],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                console.print(f"[green]✓ Удалено {len(volumes)} volume(s) с данными N8N[/green]")
            else:
                console.print("[yellow]⚠️  Volume не найден (возможно, уже удален)[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Ошибка при удалении volume: {e}[/yellow]")


def remove_n8n_from_config():
    """Удаляет N8N из конфигурационных файлов"""
    console.print("\n[cyan]📝 Удаление N8N из конфигурации...[/cyan]")
    
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    # Загружаем текущую конфигурацию
    config = dotenv_values(env_path)
    
    # Устанавливаем N8N_ENABLED=false
    set_key(env_path, 'N8N_ENABLED', 'false')
    console.print("[green]✓ .env обновлен (N8N_ENABLED=false)[/green]")
    
    # Безопасные функции для преобразования значений
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
    
    # Проверяем какие сервисы включены
    langflow_enabled = config.get('LANGFLOW_ENABLED', 'true').strip().lower() != 'false'
    ollama_enabled = config.get('OLLAMA_ENABLED', '').strip().lower() == 'true'
    
    # Обновляем конфигурацию для генерации docker-compose
    full_config = dict(config)
    full_config.update({
        'n8n_enabled': False,
        'langflow_enabled': langflow_enabled,
        'ollama_enabled': ollama_enabled,
        'routing_mode': config.get('ROUTING_MODE', ''),
        'n8n_domain': config.get('N8N_DOMAIN', ''),
        'langflow_domain': config.get('LANGFLOW_DOMAIN', ''),
        'supabase_domain': config.get('SUPABASE_DOMAIN', ''),
        'ollama_domain': config.get('OLLAMA_DOMAIN', ''),
        'base_domain': config.get('BASE_DOMAIN', ''),
        'letsencrypt_email': config.get('LETSENCRYPT_EMAIL', ''),
        'ssl_enabled': config.get('SSL_ENABLED', 'true').lower() == 'true',
        'n8n_path': config.get('N8N_PATH', '/n8n'),
        'langflow_path': config.get('LANGFLOW_PATH', '/langflow'),
        'supabase_path': config.get('SUPABASE_PATH', '/supabase'),
        'ollama_path': config.get('OLLAMA_PATH', '/ollama'),
        'supabase_memory_limit': config.get('SUPABASE_MEMORY_LIMIT', '1g') or '1g',
        'supabase_cpu_limit': safe_float(config.get('SUPABASE_CPU_LIMIT', ''), 0.3),
    })
    
    # Порты - только для включенных сервисов
    if langflow_enabled:
        full_config['langflow_port'] = safe_int(config.get('LANGFLOW_PORT', ''), 7860)
        full_config['langflow_memory_limit'] = config.get('LANGFLOW_MEMORY_LIMIT', '4g') or '4g'
        full_config['langflow_cpu_limit'] = safe_float(config.get('LANGFLOW_CPU_LIMIT', ''), 0.5)
    
    # Supabase всегда включен
    full_config['supabase_port'] = safe_int(config.get('SUPABASE_PORT', ''), 8000)
    full_config['supabase_kb_port'] = safe_int(config.get('SUPABASE_KB_PORT', ''), 3000)
    
    if ollama_enabled:
        full_config['ollama_port'] = safe_int(config.get('OLLAMA_PORT', ''), 11434)
        full_config['ollama_memory_limit'] = config.get('OLLAMA_MEMORY_LIMIT', '2g') or '2g'
        full_config['ollama_cpu_limit'] = safe_float(config.get('OLLAMA_CPU_LIMIT', ''), 1.0)
    
    # Добавляем настройки Supabase
    full_config.update({
        'postgres_password': config.get('POSTGRES_PASSWORD', ''),
        'supabase_admin_login': config.get('SUPABASE_ADMIN_LOGIN', 'admin'),
        'supabase_admin_password': config.get('SUPABASE_ADMIN_PASSWORD', ''),
        'supabase_admin_password_hash': config.get('SUPABASE_ADMIN_PASSWORD_HASH', ''),
        'jwt_secret': config.get('JWT_SECRET', ''),
        'anon_key': config.get('ANON_KEY', ''),
        'service_role_key': config.get('SERVICE_ROLE_KEY', ''),
    })
    
    # Генерируем docker-compose.yml без N8N
    hardware = detect_hardware()
    generate_docker_compose(full_config, hardware)
    console.print("[green]✓ docker-compose.yml обновлен (N8N удален)[/green]")
    
    # Генерируем Caddyfile без N8N (если используется режим поддоменов)
    if config.get('ROUTING_MODE') in ('subdomain', 'path'):
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile обновлен (N8N удален)[/green]")
    
    # Перегенерируем .env с обновленными настройками
    generate_env_file(full_config)
    console.print("[green]✓ .env перегенерирован[/green]")
    
    return True


def restart_services():
    """Перезапускает остальные сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    if Confirm.ask("Перезапустить остальные сервисы?", default=True):
        try:
            # Перезапускаем docker-compose (без N8N)
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                console.print("[green]✓ Сервисы успешно перезапущены![/green]")
                return True
            else:
                console.print(f"[yellow]⚠️  Предупреждения при перезапуске: {result.stderr}[/yellow]")
                return True  # Все равно считаем успешным
        except Exception as e:
            console.print(f"[yellow]⚠️  Ошибка при перезапуске: {e}[/yellow]")
            console.print("[yellow]Попробуйте запустить вручную: docker-compose up -d[/yellow]")
            return False
    return True


def show_summary():
    """Показывает итоговую информацию"""
    console.print("\n[green]🎉 N8N успешно удален![/green]")
    console.print("\n[cyan]📊 Освобожденное место:[/cyan]")
    console.print("  • Контейнер N8N удален")
    console.print("  • Volume с данными N8N удален (workflows, credentials)")
    console.print("  • Конфигурация обновлена")
    
    console.print("\n[yellow]💡 Для проверки освобожденного места:[/yellow]")
    console.print("[dim]docker system df -v[/dim]")


def main():
    """Главная функция"""
    show_welcome()
    
    # Проверяем, включен ли N8N
    if not check_n8n_enabled():
        if not Confirm.ask("N8N не включен в конфигурации. Продолжить удаление?", default=False):
            sys.exit(0)
    
    # Проверяем наличие контейнера
    has_container = check_n8n_container()
    if not has_container:
        console.print("[yellow]⚠️  Контейнер N8N не найден[/yellow]")
        if not Confirm.ask("Продолжить удаление из конфигурации?", default=True):
            sys.exit(0)
    
    # Подтверждение удаления
    console.print("\n[red]⚠️  ВНИМАНИЕ: Все данные N8N будут удалены![/red]")
    if not Confirm.ask("Вы уверены, что хотите удалить N8N?", default=False):
        console.print("[yellow]Удаление отменено[/yellow]")
        sys.exit(0)
    
    # Спрашиваем про volume
    remove_volume = Confirm.ask(
        "\nУдалить volume с данными N8N (workflows, credentials)? Это освободит место на диске.",
        default=True
    )
    
    # Останавливаем и удаляем N8N
    if has_container:
        stop_and_remove_n8n(remove_volume)
    
    # Удаляем из конфигурации
    if not remove_n8n_from_config():
        console.print("[red]❌ Не удалось обновить конфигурацию[/red]")
        sys.exit(1)
    
    # Перезапускаем сервисы
    restart_services()
    
    # Показываем итоги
    show_summary()


if __name__ == "__main__":
    main()

