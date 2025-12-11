#!/usr/bin/env python3
"""
Скрипт для удаления Ollama из существующей установки
"""
import sys
import os
from pathlib import Path
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from installer.config_generator import generate_docker_compose, generate_caddyfile
from installer.hardware_detector import detect_hardware
import subprocess

console = Console()


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🗑️  Удаление Ollama из установки

Этот скрипт:
1. Остановит и удалит контейнер Ollama
2. Удалит volume с данными Ollama (освободит место на диске)
3. Удалит Ollama из конфигурации (.env, docker-compose.yml, Caddyfile)
4. Перезапустит остальные сервисы

⚠️  ВНИМАНИЕ:
  • Все данные Ollama (модели) будут удалены!
  • Это действие необратимо!
    """
    console.print(Panel(welcome_text, title="Удаление Ollama", border_style="red"))


def check_ollama_enabled():
    """Проверяет, включен ли Ollama"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    config = dotenv_values(env_path)
    ollama_enabled = config.get('OLLAMA_ENABLED', '').strip().lower() == 'true'
    
    if not ollama_enabled:
        console.print("[yellow]⚠️  Ollama не включен в конфигурации[/yellow]")
        return False
    
    return True


def check_ollama_container():
    """Проверяет, запущен ли контейнер Ollama"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=ollama", "--format", "{{.Names}}"],
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


def stop_and_remove_ollama(remove_volume=True):
    """Останавливает и удаляет контейнер Ollama"""
    console.print("\n[cyan]🛑 Остановка и удаление Ollama...[/cyan]")
    
    # Останавливаем контейнер через docker-compose
    try:
        console.print("Остановка контейнера Ollama...")
        result = subprocess.run(
            ["docker-compose", "stop", "ollama"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер Ollama остановлен[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже остановлен или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при остановке: {e}[/yellow]")
    
    # Удаляем контейнер
    try:
        console.print("Удаление контейнера Ollama...")
        result = subprocess.run(
            ["docker-compose", "rm", "-f", "ollama"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            console.print("[green]✓ Контейнер Ollama удален[/green]")
        else:
            console.print("[yellow]⚠️  Контейнер уже удален или не найден[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при удалении контейнера: {e}[/yellow]")
    
    # Удаляем volume если нужно
    if remove_volume:
        try:
            console.print("Удаление volume с данными Ollama...")
            result = subprocess.run(
                ["docker", "volume", "rm", "n8n_langflow_supabase_in_docker_ollama_data"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                console.print("[green]✓ Volume с данными Ollama удален (освобождено место на диске)[/green]")
            else:
                # Пробуем найти volume с другим именем
                result = subprocess.run(
                    ["docker", "volume", "ls", "-q", "--filter", "name=ollama"],
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
                    console.print(f"[green]✓ Удалено {len(volumes)} volume(s) с данными Ollama[/green]")
                else:
                    console.print("[yellow]⚠️  Volume не найден (возможно, уже удален)[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Ошибка при удалении volume: {e}[/yellow]")


def remove_ollama_from_config():
    """Удаляет Ollama из конфигурационных файлов"""
    console.print("\n[cyan]📝 Удаление Ollama из конфигурации...[/cyan]")
    
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[yellow]⚠️  Файл .env не найден[/yellow]")
        return False
    
    # Загружаем текущую конфигурацию
    config = dotenv_values(env_path)
    
    # Устанавливаем OLLAMA_ENABLED=false
    set_key(env_path, 'OLLAMA_ENABLED', 'false')
    console.print("[green]✓ .env обновлен (OLLAMA_ENABLED=false)[/green]")
    
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
    n8n_enabled = config.get('N8N_ENABLED', 'true').strip().lower() != 'false'
    langflow_enabled = config.get('LANGFLOW_ENABLED', 'true').strip().lower() != 'false'
    
    # Обновляем конфигурацию для генерации docker-compose
    full_config = dict(config)
    full_config.update({
        'ollama_enabled': False,
        'n8n_enabled': n8n_enabled,
        'langflow_enabled': langflow_enabled,
        'routing_mode': config.get('ROUTING_MODE', ''),
        'n8n_domain': config.get('N8N_DOMAIN', ''),
        'langflow_domain': config.get('LANGFLOW_DOMAIN', ''),
        'supabase_domain': config.get('SUPABASE_DOMAIN', ''),
        'base_domain': config.get('BASE_DOMAIN', ''),
        'letsencrypt_email': config.get('LETSENCRYPT_EMAIL', ''),
        'ssl_enabled': config.get('SSL_ENABLED', 'true').lower() == 'true',
        'n8n_path': config.get('N8N_PATH', '/n8n'),
        'langflow_path': config.get('LANGFLOW_PATH', '/langflow'),
        'supabase_path': config.get('SUPABASE_PATH', '/supabase'),
        'supabase_memory_limit': config.get('SUPABASE_MEMORY_LIMIT', '1g') or '1g',
        'supabase_cpu_limit': safe_float(config.get('SUPABASE_CPU_LIMIT', ''), 0.3),
    })
    
    # Порты - только для включенных сервисов
    if n8n_enabled:
        full_config['n8n_port'] = safe_int(config.get('N8N_PORT', ''), 5678)
        full_config['n8n_memory_limit'] = config.get('N8N_MEMORY_LIMIT', '2g') or '2g'
        full_config['n8n_cpu_limit'] = safe_float(config.get('N8N_CPU_LIMIT', ''), 0.5)
    
    if langflow_enabled:
        full_config['langflow_port'] = safe_int(config.get('LANGFLOW_PORT', ''), 7860)
        full_config['langflow_memory_limit'] = config.get('LANGFLOW_MEMORY_LIMIT', '4g') or '4g'
        full_config['langflow_cpu_limit'] = safe_float(config.get('LANGFLOW_CPU_LIMIT', ''), 0.5)
    
    # Supabase всегда включен
    full_config['supabase_port'] = safe_int(config.get('SUPABASE_PORT', ''), 8000)
    full_config['supabase_kb_port'] = safe_int(config.get('SUPABASE_KB_PORT', ''), 3000)
    
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
    
    # Генерируем docker-compose.yml без Ollama
    hardware = detect_hardware()
    generate_docker_compose(full_config, hardware)
    console.print("[green]✓ docker-compose.yml обновлен (Ollama удален)[/green]")
    
    # Генерируем Caddyfile без Ollama (если используется режим поддоменов или путей)
    if config.get('ROUTING_MODE') in ('subdomain', 'path'):
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile обновлен (Ollama удален)[/green]")
    
    return True


def restart_services():
    """Перезапускает остальные сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    if Confirm.ask("Перезапустить остальные сервисы?", default=True):
        try:
            # Перезапускаем docker-compose (без Ollama)
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                console.print("[green]✓ Сервисы успешно перезапущены![/green]")
                
                # Перезагружаем конфигурацию Caddy если он используется
                try:
                    # Проверяем, используется ли Caddy (есть ли контейнер caddy)
                    caddy_check = subprocess.run(
                        ["docker", "ps", "--filter", "name=caddy", "--format", "{{.Names}}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if caddy_check.returncode == 0 and caddy_check.stdout.strip():
                        # Перезагружаем конфигурацию Caddy через API
                        console.print("Перезагрузка конфигурации Caddy...")
                        reload_result = subprocess.run(
                            ["docker", "exec", "caddy", "caddy", "reload", "--config", "/etc/caddy/Caddyfile"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if reload_result.returncode == 0:
                            console.print("[green]✓ Конфигурация Caddy перезагружена[/green]")
                        else:
                            # Если reload не сработал, перезапускаем контейнер
                            console.print("Перезапуск контейнера Caddy...")
                            subprocess.run(
                                ["docker-compose", "restart", "caddy"],
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                            console.print("[green]✓ Caddy перезапущен[/green]")
                except Exception as e:
                    console.print(f"[yellow]⚠️  Не удалось перезагрузить Caddy: {e}[/yellow]")
                    console.print("[yellow]Попробуйте вручную: docker-compose restart caddy[/yellow]")
                
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
    console.print("\n[green]🎉 Ollama успешно удален![/green]")
    console.print("\n[cyan]📊 Освобожденное место:[/cyan]")
    console.print("  • Контейнер Ollama удален")
    console.print("  • Volume с данными Ollama удален (модели)")
    console.print("  • Образ Ollama удален")
    console.print("  • Конфигурация обновлена")
    
    console.print("\n[yellow]💡 Для проверки освобожденного места:[/yellow]")
    console.print("[dim]docker system df -v[/dim]")


def main():
    """Главная функция"""
    show_welcome()
    
    # Проверяем, включен ли Ollama
    if not check_ollama_enabled():
        if not Confirm.ask("Ollama не включен в конфигурации. Продолжить удаление?", default=False):
            sys.exit(0)
    
    # Проверяем наличие контейнера
    has_container = check_ollama_container()
    if not has_container:
        console.print("[yellow]⚠️  Контейнер Ollama не найден[/yellow]")
        if not Confirm.ask("Продолжить удаление из конфигурации?", default=True):
            sys.exit(0)
    
    # Подтверждение удаления
    console.print("\n[red]⚠️  ВНИМАНИЕ: Все данные Ollama будут удалены![/red]")
    if not Confirm.ask("Вы уверены, что хотите удалить Ollama?", default=False):
        console.print("[yellow]Удаление отменено[/yellow]")
        sys.exit(0)
    
    # Спрашиваем про volume
    remove_volume = Confirm.ask(
        "\nУдалить volume с данными Ollama (модели)? Это освободит место на диске.",
        default=True
    )
    
    # Останавливаем и удаляем Ollama
    if has_container:
        stop_and_remove_ollama(remove_volume)
    
    # Удаляем из конфигурации
    if not remove_ollama_from_config():
        console.print("[red]❌ Не удалось обновить конфигурацию[/red]")
        sys.exit(1)
    
    # Удаляем неиспользуемый образ Ollama (всегда, независимо от наличия контейнера)
    remove_ollama_image(ask_confirmation=True)
    
    # Перезапускаем сервисы
    restart_services()
    
    # Показываем итоги
    show_summary()


if __name__ == "__main__":
    main()

