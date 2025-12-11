#!/usr/bin/env python3
"""
Скрипт для диагностики и исправления проблем с Langflow
"""
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from installer.config_generator import generate_docker_compose, generate_caddyfile
from installer.hardware_detector import detect_hardware
from installer.docker_manager import docker_compose_up, docker_compose_restart

console = Console()


def check_langflow_status():
    """Проверяет статус Langflow"""
    console.print("\n[cyan]🔍 Проверка статуса Langflow...[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=langflow", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            console.print(f"  Статус контейнера: {status}")
            
            if "Up" in status:
                console.print("[green]✓ Контейнер Langflow запущен[/green]")
                return True
            else:
                console.print("[yellow]⚠ Контейнер Langflow не запущен[/yellow]")
                return False
        else:
            console.print("[red]❌ Контейнер Langflow не найден[/red]")
            return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка при проверке статуса: {e}[/red]")
        return False


def check_langflow_health():
    """Проверяет здоровье Langflow"""
    console.print("\n[cyan]🏥 Проверка здоровья Langflow...[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "exec", "langflow", "curl", "-f", "http://localhost:7860/health"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Langflow отвечает на health check[/green]")
            return True
        else:
            console.print("[yellow]⚠ Langflow не отвечает на health check[/yellow]")
            console.print(f"  Ошибка: {result.stderr}")
            return False
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось проверить здоровье: {e}[/yellow]")
        return False


def check_caddyfile():
    """Проверяет конфигурацию Caddyfile"""
    console.print("\n[cyan]📄 Проверка Caddyfile...[/cyan]")
    
    caddyfile = Path("Caddyfile")
    if not caddyfile.exists():
        console.print("[red]❌ Caddyfile не найден![/red]")
        return False
    
    content = caddyfile.read_text(encoding='utf-8')
    
    # Проверяем наличие блока Langflow
    if "langflow" in content.lower():
        console.print("[green]✓ Блок Langflow найден в Caddyfile[/green]")
        
        # Проверяем синтаксис
        if "reverse_proxy langflow:7860" in content:
            console.print("[green]✓ reverse_proxy настроен правильно[/green]")
        else:
            console.print("[yellow]⚠ reverse_proxy может быть настроен неправильно[/yellow]")
        
        # Проверяем домен
        if "langflow.ai-agents-seed.ru" in content or "{LANGFLOW_DOMAIN}" in content:
            console.print("[green]✓ Домен Langflow найден[/green]")
        else:
            console.print("[yellow]⚠ Домен Langflow может быть не настроен[/yellow]")
        
        return True
    else:
        console.print("[red]❌ Блок Langflow не найден в Caddyfile![/red]")
        return False


def check_docker_compose():
    """Проверяет конфигурацию docker-compose.yml"""
    console.print("\n[cyan]🐳 Проверка docker-compose.yml...[/cyan]")
    
    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        console.print("[red]❌ docker-compose.yml не найден![/red]")
        return False
    
    content = compose_file.read_text(encoding='utf-8')
    
    # Проверяем наличие сервиса langflow
    if "langflow:" in content:
        console.print("[green]✓ Сервис langflow найден в docker-compose.yml[/green]")
        
        # Проверяем важные переменные
        checks = {
            "LANGFLOW_HOST=0.0.0.0": "LANGFLOW_HOST",
            "LANGFLOW_PORT=7860": "LANGFLOW_PORT",
            "LANGFLOW_CONFIG_DIR": "LANGFLOW_CONFIG_DIR",
            "langflow_data:/app/data": "Volume langflow_data",
            "networks:\n      - proxy": "Network proxy"
        }
        
        for check, name in checks.items():
            if check in content:
                console.print(f"  [green]✓[/green] {name} настроен")
            else:
                console.print(f"  [yellow]⚠[/yellow] {name} может быть не настроен")
        
        return True
    else:
        console.print("[red]❌ Сервис langflow не найден в docker-compose.yml![/red]")
        return False


def view_langflow_logs():
    """Показывает логи Langflow"""
    console.print("\n[cyan]📋 Логи Langflow (последние 50 строк):[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail=50", "langflow"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            console.print(f"[red]❌ Ошибка при получении логов: {result.stderr}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")


def view_caddy_logs():
    """Показывает логи Caddy"""
    console.print("\n[cyan]📋 Логи Caddy (последние 50 строк):[/cyan]")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail=50", "caddy"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            console.print(f"[red]❌ Ошибка при получении логов: {result.stderr}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")


def regenerate_config():
    """Перегенерирует конфигурацию"""
    console.print("\n[cyan]🔄 Перегенерация конфигурации...[/cyan]")
    
    try:
        env_config = dotenv_values(".env")
        if not env_config:
            console.print("[red]❌ Файл .env не найден![/red]")
            return False
        
        # Преобразуем .env в конфиг
        config = {
            'n8n_enabled': env_config.get('N8N_ENABLED', '').lower() == 'true',
            'langflow_enabled': env_config.get('LANGFLOW_ENABLED', '').lower() == 'true',
            'ollama_enabled': env_config.get('OLLAMA_ENABLED', '').lower() == 'true',
            'routing_mode': env_config.get('ROUTING_MODE', ''),
            'langflow_domain': env_config.get('LANGFLOW_DOMAIN', ''),
            'langflow_path': env_config.get('LANGFLOW_PATH', '/langflow'),
            'langflow_port': int(env_config.get('LANGFLOW_PORT', '7860')) if env_config.get('LANGFLOW_PORT') else 7860,
            'langflow_memory_limit': env_config.get('LANGFLOW_MEMORY_LIMIT', '4g'),
            'langflow_cpu_limit': float(env_config.get('LANGFLOW_CPU_LIMIT', '0.5')) if env_config.get('LANGFLOW_CPU_LIMIT') else 0.5,
            'n8n_domain': env_config.get('N8N_DOMAIN', ''),
            'supabase_domain': env_config.get('SUPABASE_DOMAIN', ''),
            'ollama_domain': env_config.get('OLLAMA_DOMAIN', ''),
            'base_domain': env_config.get('BASE_DOMAIN', ''),
            'letsencrypt_email': env_config.get('LETSENCRYPT_EMAIL', ''),
            'supabase_admin_login': env_config.get('SUPABASE_ADMIN_LOGIN', 'admin'),
            'supabase_admin_password_hash': env_config.get('SUPABASE_ADMIN_PASSWORD_HASH', ''),
            'postgres_password': env_config.get('POSTGRES_PASSWORD', ''),
        }
        
        hardware = detect_hardware()
        
        # Генерируем docker-compose.yml
        generate_docker_compose(config, hardware)
        console.print("[green]✓ docker-compose.yml перегенерирован[/green]")
        
        # Генерируем Caddyfile
        generate_caddyfile(config)
        console.print("[green]✓ Caddyfile перегенерирован[/green]")
        
        return True
    except Exception as e:
        console.print(f"[red]❌ Ошибка при перегенерации: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


def restart_services():
    """Перезапускает сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    if Confirm.ask("Перезапустить Langflow и Caddy?", default=True):
        try:
            # Перезапускаем Langflow
            console.print("Перезапуск Langflow...")
            result = subprocess.run(
                ["docker", "compose", "restart", "langflow"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                console.print("[green]✓ Langflow перезапущен[/green]")
            else:
                console.print(f"[yellow]⚠ Ошибка при перезапуске Langflow: {result.stderr}[/yellow]")
            
            # Перезапускаем Caddy
            console.print("Перезапуск Caddy...")
            result = subprocess.run(
                ["docker", "compose", "restart", "caddy"],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                console.print("[green]✓ Caddy перезапущен[/green]")
            else:
                console.print(f"[yellow]⚠ Ошибка при перезапуске Caddy: {result.stderr}[/yellow]")
            
            return True
        except Exception as e:
            console.print(f"[red]❌ Ошибка при перезапуске: {e}[/red]")
            return False
    
    return False


def recreate_langflow():
    """Пересоздает контейнер Langflow"""
    console.print("\n[cyan]🔄 Пересоздание контейнера Langflow...[/cyan]")
    
    if Confirm.ask("Пересоздать контейнер Langflow? (данные сохранятся)", default=False):
        try:
            # Останавливаем и удаляем контейнер
            console.print("Остановка контейнера...")
            subprocess.run(
                ["docker", "compose", "stop", "langflow"],
                capture_output=True,
                timeout=30
            )
            
            subprocess.run(
                ["docker", "compose", "rm", "-f", "langflow"],
                capture_output=True,
                timeout=30
            )
            
            # Запускаем заново
            console.print("Запуск нового контейнера...")
            if docker_compose_up(detach=True, service_name='langflow'):
                console.print("[green]✓ Контейнер Langflow пересоздан[/green]")
                return True
            else:
                console.print("[red]❌ Ошибка при запуске контейнера[/red]")
                return False
        except Exception as e:
            console.print(f"[red]❌ Ошибка: {e}[/red]")
            return False
    
    return False


def main():
    """Главная функция"""
    console.print(Panel("[bold blue]🔧 Диагностика и исправление Langflow[/bold blue]", expand=False))
    
    # Проверки
    status_ok = check_langflow_status()
    health_ok = check_langflow_health() if status_ok else False
    caddyfile_ok = check_caddyfile()
    compose_ok = check_docker_compose()
    
    # Сводка
    console.print("\n[cyan]📊 Сводка проверок:[/cyan]")
    console.print(f"  Статус контейнера: {'✓' if status_ok else '❌'}")
    console.print(f"  Health check: {'✓' if health_ok else '❌'}")
    console.print(f"  Caddyfile: {'✓' if caddyfile_ok else '❌'}")
    console.print(f"  docker-compose.yml: {'✓' if compose_ok else '❌'}")
    
    # Меню действий
    if not (status_ok and health_ok and caddyfile_ok and compose_ok):
        console.print("\n[yellow]⚠ Обнаружены проблемы![/yellow]")
        console.print("\n[cyan]Доступные действия:[/cyan]")
        console.print("1. Просмотреть логи Langflow")
        console.print("2. Просмотреть логи Caddy")
        console.print("3. Перегенерировать конфигурацию (docker-compose.yml и Caddyfile)")
        console.print("4. Перезапустить сервисы (Langflow и Caddy)")
        console.print("5. Пересоздать контейнер Langflow (с сохранением данных)")
        console.print("0. Выход")
        
        choice = Prompt.ask("Выберите действие", choices=["0", "1", "2", "3", "4", "5"])
        
        if choice == "1":
            view_langflow_logs()
        elif choice == "2":
            view_caddy_logs()
        elif choice == "3":
            if regenerate_config():
                if Confirm.ask("\nПерезапустить сервисы после перегенерации?", default=True):
                    restart_services()
        elif choice == "4":
            restart_services()
        elif choice == "5":
            recreate_langflow()
    else:
        console.print("\n[green]✓ Все проверки пройдены успешно![/green]")
        if Confirm.ask("\nПросмотреть логи Langflow?", default=False):
            view_langflow_logs()


if __name__ == "__main__":
    main()

