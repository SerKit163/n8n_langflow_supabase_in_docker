#!/usr/bin/env python3
"""
Скрипт для добавления N8N к существующей установке
"""
import sys
import os
from pathlib import Path
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from installer.hardware_detector import detect_hardware
from installer.config_adaptor import adapt_config_for_hardware
from installer.config_generator import generate_docker_compose, generate_caddyfile, generate_env_file
from installer.utils import ensure_dir
from installer.validator import validate_domain, validate_path
from installer.docker_manager import docker_compose_up
import subprocess

console = Console()


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🔧 Добавление N8N к существующей установке

Этот скрипт добавит N8N к вашей текущей установке.
N8N - это инструмент для автоматизации рабочих процессов и интеграций.

⚠️  ВНИМАНИЕ:
  • N8N требует минимум 1GB RAM (рекомендуется 2-4GB)
  • Убедитесь, что у вас достаточно ресурсов
    """
    console.print(Panel(welcome_text, title="Добавление N8N", border_style="cyan"))


def check_existing_config():
    """Проверяет существующую конфигурацию"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[red]❌ Файл .env не найден![/red]")
        console.print("[yellow]Запустите сначала python3 setup.py для первоначальной установки[/yellow]")
        sys.exit(1)
    
    config = dotenv_values(env_path)
    
    # Проверяем, не включен ли уже N8N
    if config.get('N8N_ENABLED', '').lower() == 'true':
        console.print("[yellow]⚠️  N8N уже включен в конфигурации![/yellow]")
        if not Confirm.ask("Переконфигурировать N8N?", default=False):
            sys.exit(0)
    
    return config


def configure_n8n(hardware, existing_config):
    """Настраивает N8N"""
    console.print("\n[cyan]⚙️ Настройка N8N[/cyan]")
    
    # Получаем рекомендуемые настройки
    recommended_config = adapt_config_for_hardware(hardware)
    
    # Режим маршрутизации
    routing_mode = existing_config.get('ROUTING_MODE', '')
    
    n8n_config = {
        'n8n_enabled': True,
        'n8n_port': 5678,
        'n8n_memory_limit': f"{recommended_config['memory_limits']['n8n']:.1f}g",
        'n8n_cpu_limit': recommended_config['cpu_limits']['n8n'],
    }
    
    # Настройка домена/пути в зависимости от режима маршрутизации
    if routing_mode == 'subdomain':
        console.print("\n[cyan]🌐 Настройка домена для N8N:[/cyan]")
        
        # Извлекаем базовый домен из существующих доменов
        base_domain = None
        existing_domains = [
            existing_config.get('SUPABASE_DOMAIN', ''),
            existing_config.get('LANGFLOW_DOMAIN', ''),
            existing_config.get('OLLAMA_DOMAIN', '')
        ]
        for domain in existing_domains:
            if domain:
                # Извлекаем базовый домен (убираем поддомен)
                parts = domain.split('.')
                if len(parts) >= 2:
                    base_domain = '.'.join(parts[1:])  # Берем все после первой части
                    break
        
        # Предлагаем автоматический или ручной режим
        use_auto = Confirm.ask(
            "Автоматически сформировать поддомен для N8N?",
            default=True
        )
        
        if use_auto and base_domain:
            # АВТОМАТИЧЕСКИЙ РЕЖИМ
            auto_domain = f"n8n.{base_domain}"
            console.print(f"\n[green]✓ Предложенный домен: {auto_domain}[/green]")
            if Confirm.ask(f"Использовать домен {auto_domain}?", default=True):
                n8n_config['n8n_domain'] = auto_domain
            else:
                # Ручной ввод
                while True:
                    n8n_domain = Prompt.ask(
                        "Домен для N8N (например, n8n.example.com) или '-' для пропуска",
                        default=existing_config.get('N8N_DOMAIN', auto_domain)
                    )
                    if n8n_domain == '-':
                        console.print("[yellow]⚠️  Домен не указан, N8N будет доступен только по IP:порт[/yellow]")
                        break
                    is_valid, error = validate_domain(n8n_domain)
                    if is_valid:
                        n8n_config['n8n_domain'] = n8n_domain
                        break
                    else:
                        console.print(f"[red]❌ {error}[/red]")
        else:
            # РУЧНОЙ РЕЖИМ
            while True:
                n8n_domain = Prompt.ask(
                    "Домен для N8N (например, n8n.example.com) или '-' для пропуска",
                    default=existing_config.get('N8N_DOMAIN', '')
                )
                if n8n_domain == '-':
                    console.print("[yellow]⚠️  Домен не указан, N8N будет доступен только по IP:порт[/yellow]")
                    break
                is_valid, error = validate_domain(n8n_domain)
                if is_valid:
                    n8n_config['n8n_domain'] = n8n_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    elif routing_mode == 'path':
        console.print("\n[cyan]🌐 Настройка пути для N8N:[/cyan]")
        base_domain = existing_config.get('BASE_DOMAIN', '')
        
        if base_domain:
            # Предлагаем автоматический или ручной режим
            use_auto = Confirm.ask(
                "Автоматически использовать путь /n8n?",
                default=True
            )
            
            if use_auto:
                # АВТОМАТИЧЕСКИЙ РЕЖИМ
                auto_path = '/n8n'
                console.print(f"\n[green]✓ Предложенный путь: {base_domain}{auto_path}[/green]")
                if Confirm.ask(f"Использовать путь {auto_path}?", default=True):
                    n8n_config['n8n_path'] = auto_path
                    n8n_config['base_domain'] = base_domain
                else:
                    # Ручной ввод
                    while True:
                        n8n_path = Prompt.ask(
                            "Путь для N8N (например, /n8n)",
                            default=existing_config.get('N8N_PATH', '/n8n')
                        )
                        is_valid, error = validate_path(n8n_path)
                        if is_valid:
                            n8n_config['n8n_path'] = n8n_path
                            n8n_config['base_domain'] = base_domain
                            break
                        else:
                            console.print(f"[red]❌ {error}[/red]")
            else:
                # РУЧНОЙ РЕЖИМ
                while True:
                    n8n_path = Prompt.ask(
                        "Путь для N8N (например, /n8n)",
                        default=existing_config.get('N8N_PATH', '/n8n')
                    )
                    is_valid, error = validate_path(n8n_path)
                    if is_valid:
                        n8n_config['n8n_path'] = n8n_path
                        n8n_config['base_domain'] = base_domain
                        break
                    else:
                        console.print(f"[red]❌ {error}[/red]")
        else:
            console.print("[yellow]⚠️  BASE_DOMAIN не найден в конфигурации[/yellow]")
            console.print("[yellow]💡 Укажите базовый домен для режима путей[/yellow]")
            while True:
                base_domain = Prompt.ask("Базовый домен (например, example.com) или '-' для пропуска", default="-")
                if base_domain == '-':
                    break
                is_valid, error = validate_domain(base_domain)
                if is_valid:
                    n8n_config['base_domain'] = base_domain
                    # Предлагаем путь
                    use_auto = Confirm.ask("Автоматически использовать путь /n8n?", default=True)
                    if use_auto:
                        n8n_config['n8n_path'] = '/n8n'
                    else:
                        while True:
                            n8n_path = Prompt.ask("Путь для N8N", default="/n8n")
                            is_valid, error = validate_path(n8n_path)
                            if is_valid:
                                n8n_config['n8n_path'] = n8n_path
                                break
                            else:
                                console.print(f"[red]❌ {error}[/red]")
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    else:
        console.print("\n[cyan]🔌 Настройка порта для N8N:[/cyan]")
        n8n_port = IntPrompt.ask(
            "Порт для N8N",
            default=int(existing_config.get('N8N_PORT', '5678'))
        )
        n8n_config['n8n_port'] = n8n_port
    
    # Настройка ресурсов
    console.print("\n[cyan]💾 Настройка ресурсов:[/cyan]")
    use_recommended = Confirm.ask(
        f"Использовать рекомендуемые настройки? (Память: {n8n_config['n8n_memory_limit']}, CPU: {n8n_config['n8n_cpu_limit']})",
        default=True
    )
    
    if not use_recommended:
        n8n_config['n8n_memory_limit'] = Prompt.ask(
            "Лимит памяти (например, 2g)",
            default=n8n_config['n8n_memory_limit']
        )
        n8n_config['n8n_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(n8n_config['n8n_cpu_limit'])
        ))
    
    # Настройка протокола и webhook URL
    console.print("\n[cyan]🔗 Настройка протокола:[/cyan]")
    if routing_mode == 'subdomain' or routing_mode == 'path':
        n8n_protocol = 'https'
        if n8n_config.get('n8n_domain'):
            webhook_url = f"https://{n8n_config['n8n_domain']}/"
        elif n8n_config.get('base_domain'):
            webhook_url = f"https://{n8n_config['base_domain']}{n8n_config.get('n8n_path', '/n8n')}/"
        else:
            webhook_url = ''
    else:
        n8n_protocol = 'http'
        webhook_url = f"http://localhost:{n8n_config['n8n_port']}/"
    
    n8n_config['n8n_protocol'] = n8n_protocol
    n8n_config['webhook_url'] = webhook_url
    
    return n8n_config


def update_config_files(existing_config, n8n_config):
    """Обновляет конфигурационные файлы"""
    console.print("\n[cyan]📝 Обновление конфигурации...[/cyan]")
    
    # Обновляем .env файл
    env_path = Path(".env")
    
    # Добавляем/обновляем переменные N8N
    set_key(env_path, 'N8N_ENABLED', 'true')
    set_key(env_path, 'N8N_PORT', str(n8n_config.get('n8n_port', 5678)))
    set_key(env_path, 'N8N_MEMORY_LIMIT', n8n_config.get('n8n_memory_limit', '2g'))
    set_key(env_path, 'N8N_CPU_LIMIT', str(n8n_config.get('n8n_cpu_limit', 0.5)))
    set_key(env_path, 'N8N_PROTOCOL', n8n_config.get('n8n_protocol', 'https'))
    set_key(env_path, 'WEBHOOK_URL', n8n_config.get('webhook_url', ''))
    
    if n8n_config.get('n8n_domain'):
        set_key(env_path, 'N8N_DOMAIN', n8n_config['n8n_domain'])
    if n8n_config.get('n8n_path'):
        set_key(env_path, 'N8N_PATH', n8n_config['n8n_path'])
    
    console.print("[green]✓ .env файл обновлен[/green]")
    
    # Обновляем существующую конфигурацию для генерации docker-compose
    full_config = dict(existing_config)
    full_config.update({
        'n8n_enabled': True,
        'n8n_port': n8n_config.get('n8n_port', 5678),
        'n8n_memory_limit': n8n_config.get('n8n_memory_limit', '2g'),
        'n8n_cpu_limit': n8n_config.get('n8n_cpu_limit', 0.5),
        'n8n_domain': n8n_config.get('n8n_domain', ''),
        'n8n_path': n8n_config.get('n8n_path', '/n8n'),
        'n8n_protocol': n8n_config.get('n8n_protocol', 'https'),
        'webhook_url': n8n_config.get('webhook_url', ''),
    })
    
    # Обновляем routing_mode если его нет
    if 'routing_mode' not in full_config:
        full_config['routing_mode'] = existing_config.get('ROUTING_MODE', '')
    
    # Обновляем другие необходимые переменные
    for key in ['langflow_domain', 'supabase_domain', 'ollama_domain', 'base_domain',
                'letsencrypt_email', 'ssl_enabled', 'langflow_port',
                'supabase_port', 'langflow_path', 'supabase_path', 'ollama_path']:
        if key.upper() in existing_config:
            full_config[key] = existing_config[key.upper()]
    
    # Добавляем флаги для других сервисов
    full_config['langflow_enabled'] = existing_config.get('LANGFLOW_ENABLED', 'true').strip().lower() != 'false'
    full_config['ollama_enabled'] = existing_config.get('OLLAMA_ENABLED', '').strip().lower() == 'true'
    
    # Добавляем остальные необходимые переменные
    for key in ['postgres_password', 'supabase_admin_login', 'supabase_admin_password',
                'supabase_admin_password_hash', 'jwt_secret', 'anon_key', 'service_role_key',
                'supabase_kb_port', 'langflow_memory_limit', 'langflow_cpu_limit',
                'supabase_memory_limit', 'supabase_cpu_limit', 'ollama_memory_limit',
                'ollama_cpu_limit', 'ollama_port']:
        if key.upper() in existing_config:
            full_config[key] = existing_config[key.upper()]
    
    # Генерируем docker-compose.yml
    hardware = detect_hardware()
    generate_docker_compose(full_config, hardware)
    console.print("[green]✓ docker-compose.yml обновлен[/green]")
    
    # Генерируем Caddyfile если используется режим поддоменов или путей
    if existing_config.get('ROUTING_MODE') in ('subdomain', 'path'):
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile обновлен[/green]")
    
    # Перегенерируем .env с обновленными настройками
    generate_env_file(full_config)
    console.print("[green]✓ .env перегенерирован[/green]")
    
    return full_config


def start_n8n():
    """Запускает N8N контейнер"""
    console.print("\n[cyan]🚀 Запуск N8N...[/cyan]")
    
    if Confirm.ask("Запустить N8N сейчас?", default=True):
        # Используем docker_compose_up для показа прогресса загрузки образов
        if docker_compose_up(detach=True):
            console.print("[green]✓ N8N запущен![/green]")
            
            # Показываем информацию о доступе
            console.print("\n[cyan]📋 Информация для доступа:[/cyan]")
            config = dotenv_values(".env")
            routing_mode = config.get('ROUTING_MODE', '')
            
            if routing_mode == 'subdomain':
                domain = config.get('N8N_DOMAIN', '')
                if domain:
                    protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                    console.print(f"  [green]✓[/green] N8N: {protocol}://{domain}")
            elif routing_mode == 'path':
                base_domain = config.get('BASE_DOMAIN', '')
                n8n_path = config.get('N8N_PATH', '/n8n')
                if base_domain:
                    protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                    console.print(f"  [green]✓[/green] N8N: {protocol}://{base_domain}{n8n_path}")
            else:
                port = config.get('N8N_PORT', '5678')
                console.print(f"  [green]✓[/green] N8N: http://localhost:{port}")
            
            console.print("\n[yellow]💡 При первом запуске N8N создаст учетную запись администратора[/yellow]")
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Ошибка при запуске N8N:[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            console.print("\n[yellow]Попробуйте запустить вручную:[/yellow]")
            console.print("[dim]docker-compose up -d n8n[/dim]")


def main():
    """Главная функция"""
    show_welcome()
    
    # Проверяем существующую конфигурацию
    existing_config = check_existing_config()
    
    # Определяем железо
    console.print("\n[cyan]🔍 Определение конфигурации железа...[/cyan]")
    hardware = detect_hardware()
    console.print(f"[green]✓ RAM: {hardware['ram']['total_gb']:.1f} GB[/green]")
    console.print(f"[green]✓ CPU: {hardware['cpu']['cores']} ядер[/green]")
    
    # Настраиваем N8N
    n8n_config = configure_n8n(hardware, existing_config)
    
    # Обновляем конфигурационные файлы
    full_config = update_config_files(existing_config, n8n_config)
    
    # Запускаем N8N
    start_n8n()
    
    console.print("\n[green]🎉 N8N успешно добавлен![/green]")


if __name__ == "__main__":
    main()

