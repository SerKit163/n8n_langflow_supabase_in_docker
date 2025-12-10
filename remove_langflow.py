#!/usr/bin/env python3
"""
Скрипт для удаления Langflow из существующей установки
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
🗑️  Удаление Langflow из установки

Этот скрипт:
1. Остановит и удалит контейнер Langflow
2. Удалит volume с данными Langflow (освободит место на диске)
3. Удалит Langflow из конфигурации (.env, docker-compose.yml, Caddyfile)
4. Перезапустит остальные сервисы

⚠️  ВНИМАНИЕ:
  • Все данные Langflow (flows, компоненты) будут удалены!
  • Это действие необратимо!
    """
    console.print(Panel(welcome_text, title="Удаление Langflow", border_style="red"))


def check_langflow_enabled():
    """Проверяет, включен ли Langflow"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    config = dotenv_values(env_path)
    langflow_enabled = config.get('LANGFLOW_ENABLED', 'true').strip().lower() != 'false'
    
    if not langflow_enabled:
        console.print("[yellow]⚠️  Langflow не включен в конфигурации[/yellow]")
        return False
    
    return True


def check_langflow_container():
    """Проверяет, запущен ли контейнер Langflow"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=langflow", "--format", "{{.Names}}"],
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


def stop_and_remove_langflow(remove_volume=True):
    """Останавливает и удаляет контейнер Langflow"""
    console.print("\n[cyan]🛑 Остановка и удаление Langflow...[/cyan]")
    
    # Останавливаем контейнер через docker-compose
    try:
        console.print("Остановка контейнера Langflow...")
        result = subprocess.run(
            ["docker-compose", "stop", "langflow"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер Langflow остановлен[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже остановлен или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при остановке: {e}[/yellow]")
    
    # Удаляем контейнер
    try:
        console.print("Удаление контейнера Langflow...")
        result = subprocess.run(
            ["docker-compose", "rm", "-f", "langflow"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер Langflow удален[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже удален или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при удалении контейнера: {e}[/yellow]")
    
    # Удаляем volume если нужно
    if remove_volume:
        try:
            console.print("Удаление volume с данными Langflow...")
            # Пробуем найти volume с именем langflow_data
            result = subprocess.run(
                ["docker", "volume", "ls", "-q", "--filter", "name=langflow"],
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
                console.print(f"[green]✓ Удалено {len(volumes)} volume(s) с данными Langflow[/green]")
            else:
                console.print("[yellow]⚠️  Volume не найден (возможно, уже удален)[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Ошибка при удалении volume: {e}[/yellow]")


def remove_langflow_from_config():
    """Удаляет Langflow из конфигурационных файлов"""
    console.print("\n[cyan]📝 Удаление Langflow из конфигурации...[/cyan]")
    
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    # Загружаем текущую конфигурацию
    config = dotenv_values(env_path)
    
    # Устанавливаем LANGFLOW_ENABLED=false
    set_key(env_path, 'LANGFLOW_ENABLED', 'false')
    console.print("[green]✓ .env обновлен (LANGFLOW_ENABLED=false)[/green]")
    
    # Обновляем конфигурацию для генерации docker-compose
    full_config = dict(config)
    full_config.update({
        'n8n_enabled': config.get('N8N_ENABLED', 'true').strip().lower() != 'false',
        'langflow_enabled': False,
        'ollama_enabled': config.get('OLLAMA_ENABLED', '').strip().lower() == 'true',
        'routing_mode': config.get('ROUTING_MODE', ''),
        'n8n_domain': config.get('N8N_DOMAIN', ''),
        'langflow_domain': config.get('LANGFLOW_DOMAIN', ''),
        'supabase_domain': config.get('SUPABASE_DOMAIN', ''),
        'ollama_domain': config.get('OLLAMA_DOMAIN', ''),
        'base_domain': config.get('BASE_DOMAIN', ''),
        'letsencrypt_email': config.get('LETSENCRYPT_EMAIL', ''),
        'ssl_enabled': config.get('SSL_ENABLED', 'true').lower() == 'true',
        'n8n_port': int(config.get('N8N_PORT', '5678')),
        'langflow_port': int(config.get('LANGFLOW_PORT', '7860')),
        'supabase_port': int(config.get('SUPABASE_PORT', '8000')),
        'supabase_kb_port': int(config.get('SUPABASE_KB_PORT', '3000')),
        'ollama_port': int(config.get('OLLAMA_PORT', '11434')),
        'n8n_path': config.get('N8N_PATH', '/n8n'),
        'langflow_path': config.get('LANGFLOW_PATH', '/langflow'),
        'supabase_path': config.get('SUPABASE_PATH', '/supabase'),
        'ollama_path': config.get('OLLAMA_PATH', '/ollama'),
        'n8n_memory_limit': config.get('N8N_MEMORY_LIMIT', '2g'),
        'n8n_cpu_limit': float(config.get('N8N_CPU_LIMIT', '0.5')),
        'langflow_memory_limit': config.get('LANGFLOW_MEMORY_LIMIT', '4g'),
        'langflow_cpu_limit': float(config.get('LANGFLOW_CPU_LIMIT', '0.5')),
        'supabase_memory_limit': config.get('SUPABASE_MEMORY_LIMIT', '1g'),
        'supabase_cpu_limit': float(config.get('SUPABASE_CPU_LIMIT', '0.3')),
        'ollama_memory_limit': config.get('OLLAMA_MEMORY_LIMIT', '2g'),
        'ollama_cpu_limit': float(config.get('OLLAMA_CPU_LIMIT', '1.0')),
        'postgres_password': config.get('POSTGRES_PASSWORD', ''),
        'supabase_admin_login': config.get('SUPABASE_ADMIN_LOGIN', 'admin'),
        'supabase_admin_password': config.get('SUPABASE_ADMIN_PASSWORD', ''),
        'supabase_admin_password_hash': config.get('SUPABASE_ADMIN_PASSWORD_HASH', ''),
        'jwt_secret': config.get('JWT_SECRET', ''),
        'anon_key': config.get('ANON_KEY', ''),
        'service_role_key': config.get('SERVICE_ROLE_KEY', ''),
    })
    
    # Генерируем docker-compose.yml без Langflow
    hardware = detect_hardware()
    generate_docker_compose(full_config, hardware)
    console.print("[green]✓ docker-compose.yml обновлен (Langflow удален)[/green]")
    
    # Генерируем Caddyfile без Langflow (если используется режим поддоменов)
    if config.get('ROUTING_MODE') in ('subdomain', 'path'):
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile обновлен (Langflow удален)[/green]")
    
    # Перегенерируем .env с обновленными настройками
    generate_env_file(full_config)
    console.print("[green]✓ .env перегенерирован[/green]")
    
    return True


def restart_services():
    """Перезапускает остальные сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    if Confirm.ask("Перезапустить остальные сервисы?", default=True):
        try:
            # Перезапускаем docker-compose (без Langflow)
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
    console.print("\n[green]🎉 Langflow успешно удален![/green]")
    console.print("\n[cyan]📊 Освобожденное место:[/cyan]")
    console.print("  • Контейнер Langflow удален")
    console.print("  • Volume с данными Langflow удален (flows, компоненты)")
    console.print("  • Конфигурация обновлена")
    
    console.print("\n[yellow]💡 Для проверки освобожденного места:[/yellow]")
    console.print("[dim]docker system df -v[/dim]")


def main():
    """Главная функция"""
    show_welcome()
    
    # Проверяем, включен ли Langflow
    if not check_langflow_enabled():
        if not Confirm.ask("Langflow не включен в конфигурации. Продолжить удаление?", default=False):
            sys.exit(0)
    
    # Проверяем наличие контейнера
    has_container = check_langflow_container()
    if not has_container:
        console.print("[yellow]⚠️  Контейнер Langflow не найден[/yellow]")
        if not Confirm.ask("Продолжить удаление из конфигурации?", default=True):
            sys.exit(0)
    
    # Подтверждение удаления
    console.print("\n[red]⚠️  ВНИМАНИЕ: Все данные Langflow будут удалены![/red]")
    if not Confirm.ask("Вы уверены, что хотите удалить Langflow?", default=False):
        console.print("[yellow]Удаление отменено[/yellow]")
        sys.exit(0)
    
    # Спрашиваем про volume
    remove_volume = Confirm.ask(
        "\nУдалить volume с данными Langflow (flows, компоненты)? Это освободит место на диске.",
        default=True
    )
    
    # Останавливаем и удаляем Langflow
    if has_container:
        stop_and_remove_langflow(remove_volume)
    
    # Удаляем из конфигурации
    if not remove_langflow_from_config():
        console.print("[red]❌ Не удалось обновить конфигурацию[/red]")
        sys.exit(1)
    
    # Перезапускаем сервисы
    restart_services()
    
    # Показываем итоги
    show_summary()


if __name__ == "__main__":
    main()

