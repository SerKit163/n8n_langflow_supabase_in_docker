#!/usr/bin/env python3
"""
Скрипт для добавления Langflow к существующей установке
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
import subprocess

console = Console()


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🤖 Добавление Langflow к существующей установке

Этот скрипт добавит Langflow к вашей текущей установке.
Langflow - это визуальный конструктор для создания AI агентов.

⚠️  ВНИМАНИЕ:
  • Langflow требует много памяти (минимум 3GB, рекомендуется 4-8GB)
  • Для работы с AI агентами рекомендуется минимум 8GB RAM
  • При создании сложных агентов память может увеличиться до 4-6GB
    """
    console.print(Panel(welcome_text, title="Добавление Langflow", border_style="cyan"))


def check_existing_config():
    """Проверяет существующую конфигурацию"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[red]❌ Файл .env не найден![/red]")
        console.print("[yellow]Запустите сначала python3 setup.py для первоначальной установки[/yellow]")
        sys.exit(1)
    
    config = dotenv_values(env_path)
    
    # Проверяем, не включен ли уже Langflow
    if config.get('LANGFLOW_ENABLED', '').lower() == 'true':
        console.print("[yellow]⚠️  Langflow уже включен в конфигурации![/yellow]")
        if not Confirm.ask("Переконфигурировать Langflow?", default=False):
            sys.exit(0)
    
    return config


def configure_langflow(hardware, existing_config):
    """Настраивает Langflow"""
    console.print("\n[cyan]⚙️ Настройка Langflow[/cyan]")
    
    # Получаем рекомендуемые настройки
    recommended_config = adapt_config_for_hardware(hardware)
    
    # Проверяем память
    total_ram = hardware['ram']['total_gb']
    langflow_memory = recommended_config['memory_limits']['langflow']
    
    if total_ram < 8:
        console.print(f"[yellow]⚠️  Мало RAM ({total_ram:.1f} GB) - Langflow может работать медленно[/yellow]")
        console.print("[yellow]💡 Рекомендуется минимум 8GB RAM для комфортной работы[/yellow]")
    
    if langflow_memory < 3:
        console.print(f"[yellow]⚠️  Лимит памяти для Langflow ({langflow_memory:.1f}GB) меньше рекомендуемого минимума (3GB)[/yellow]")
        console.print("[yellow]💡 Langflow требует много памяти для работы с ИИ агентами![/yellow]")
        console.print(f"[yellow]   Текущий лимит: {langflow_memory:.1f}GB из {total_ram:.1f}GB доступных.[/yellow]")
        console.print("[yellow]   При создании сложных агентов память может увеличиться до 4-6GB.[/yellow]")
        if not Confirm.ask("\nПродолжить с текущими настройками?", default=True):
            sys.exit(0)
    
    # Режим маршрутизации
    routing_mode = existing_config.get('ROUTING_MODE', '')
    
    langflow_config = {
        'langflow_enabled': True,
        'langflow_port': 7860,
        'langflow_memory_limit': f"{langflow_memory:.1f}g",
        'langflow_cpu_limit': recommended_config['cpu_limits']['langflow'],
    }
    
    # Настройка домена/пути в зависимости от режима маршрутизации
    if routing_mode == 'subdomain':
        console.print("\n[cyan]🌐 Настройка домена для Langflow:[/cyan]")
        langflow_domain = Prompt.ask(
            "Домен для Langflow (например, langflow.example.com)",
            default=existing_config.get('LANGFLOW_DOMAIN', '')
        )
        if langflow_domain:
            langflow_config['langflow_domain'] = langflow_domain
        else:
            console.print("[yellow]⚠️  Домен не указан, Langflow будет доступен только по IP:порт[/yellow]")
    elif routing_mode == 'path':
        console.print("\n[cyan]🌐 Настройка пути для Langflow:[/cyan]")
        base_domain = existing_config.get('BASE_DOMAIN', '')
        if base_domain:
            langflow_path = Prompt.ask(
                "Путь для Langflow",
                default=existing_config.get('LANGFLOW_PATH', '/langflow')
            )
            langflow_config['langflow_path'] = langflow_path
            langflow_config['base_domain'] = base_domain
        else:
            console.print("[yellow]⚠️  BASE_DOMAIN не найден в конфигурации[/yellow]")
    else:
        console.print("\n[cyan]🔌 Настройка порта для Langflow:[/cyan]")
        langflow_port = IntPrompt.ask(
            "Порт для Langflow",
            default=int(existing_config.get('LANGFLOW_PORT', '7860'))
        )
        langflow_config['langflow_port'] = langflow_port
    
    # Настройка ресурсов
    console.print("\n[cyan]💾 Настройка ресурсов:[/cyan]")
    use_recommended = Confirm.ask(
        f"Использовать рекомендуемые настройки? (Память: {langflow_config['langflow_memory_limit']}, CPU: {langflow_config['langflow_cpu_limit']})",
        default=True
    )
    
    if not use_recommended:
        langflow_config['langflow_memory_limit'] = Prompt.ask(
            "Лимит памяти (например, 4g)",
            default=langflow_config['langflow_memory_limit']
        )
        langflow_config['langflow_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(langflow_config['langflow_cpu_limit'])
        ))
    
    return langflow_config


def update_config_files(existing_config, langflow_config):
    """Обновляет конфигурационные файлы"""
    console.print("\n[cyan]📝 Обновление конфигурации...[/cyan]")
    
    # Обновляем .env файл
    env_path = Path(".env")
    
    # Добавляем/обновляем переменные Langflow
    set_key(env_path, 'LANGFLOW_ENABLED', 'true')
    set_key(env_path, 'LANGFLOW_PORT', str(langflow_config.get('langflow_port', 7860)))
    set_key(env_path, 'LANGFLOW_MEMORY_LIMIT', langflow_config.get('langflow_memory_limit', '4g'))
    set_key(env_path, 'LANGFLOW_CPU_LIMIT', str(langflow_config.get('langflow_cpu_limit', 0.5)))
    
    if langflow_config.get('langflow_domain'):
        set_key(env_path, 'LANGFLOW_DOMAIN', langflow_config['langflow_domain'])
    if langflow_config.get('langflow_path'):
        set_key(env_path, 'LANGFLOW_PATH', langflow_config['langflow_path'])
    
    console.print("[green]✓ .env файл обновлен[/green]")
    
    # Обновляем существующую конфигурацию для генерации docker-compose
    full_config = dict(existing_config)
    full_config.update({
        'langflow_enabled': True,
        'langflow_port': langflow_config.get('langflow_port', 7860),
        'langflow_memory_limit': langflow_config.get('langflow_memory_limit', '4g'),
        'langflow_cpu_limit': langflow_config.get('langflow_cpu_limit', 0.5),
        'langflow_domain': langflow_config.get('langflow_domain', ''),
        'langflow_path': langflow_config.get('langflow_path', '/langflow'),
    })
    
    # Обновляем routing_mode если его нет
    if 'routing_mode' not in full_config:
        full_config['routing_mode'] = existing_config.get('ROUTING_MODE', '')
    
    # Обновляем другие необходимые переменные
    for key in ['n8n_domain', 'supabase_domain', 'ollama_domain', 'base_domain',
                'letsencrypt_email', 'ssl_enabled', 'n8n_port',
                'supabase_port', 'n8n_path', 'supabase_path', 'ollama_path']:
        if key.upper() in existing_config:
            full_config[key] = existing_config[key.upper()]
    
    # Добавляем флаги для других сервисов
    full_config['n8n_enabled'] = existing_config.get('N8N_ENABLED', 'true').strip().lower() != 'false'
    full_config['ollama_enabled'] = existing_config.get('OLLAMA_ENABLED', '').strip().lower() == 'true'
    
    # Добавляем остальные необходимые переменные
    for key in ['postgres_password', 'supabase_admin_login', 'supabase_admin_password',
                'supabase_admin_password_hash', 'jwt_secret', 'anon_key', 'service_role_key',
                'supabase_kb_port', 'n8n_memory_limit', 'n8n_cpu_limit',
                'supabase_memory_limit', 'supabase_cpu_limit', 'ollama_memory_limit',
                'ollama_cpu_limit', 'ollama_port', 'n8n_protocol', 'webhook_url']:
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


def start_langflow():
    """Запускает Langflow контейнер"""
    console.print("\n[cyan]🚀 Запуск Langflow...[/cyan]")
    
    if Confirm.ask("Запустить Langflow сейчас?", default=True):
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "langflow"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print("[green]✓ Langflow запущен![/green]")
            
            # Показываем информацию о доступе
            console.print("\n[cyan]📋 Информация для доступа:[/cyan]")
            config = dotenv_values(".env")
            routing_mode = config.get('ROUTING_MODE', '')
            
            if routing_mode == 'subdomain':
                domain = config.get('LANGFLOW_DOMAIN', '')
                if domain:
                    protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                    console.print(f"  [green]✓[/green] Langflow: {protocol}://{domain}")
            elif routing_mode == 'path':
                base_domain = config.get('BASE_DOMAIN', '')
                langflow_path = config.get('LANGFLOW_PATH', '/langflow')
                if base_domain:
                    protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                    console.print(f"  [green]✓[/green] Langflow: {protocol}://{base_domain}{langflow_path}")
            else:
                port = config.get('LANGFLOW_PORT', '7860')
                console.print(f"  [green]✓[/green] Langflow: http://localhost:{port}")
            
            console.print("\n[yellow]💡 При первом запуске Langflow может занять несколько минут для инициализации[/yellow]")
            console.print("[yellow]💡 Проверьте логи если страница не загружается: docker-compose logs langflow[/yellow]")
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Ошибка при запуске Langflow:[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            console.print("\n[yellow]Попробуйте запустить вручную:[/yellow]")
            console.print("[dim]docker-compose up -d langflow[/dim]")


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
    
    # Настраиваем Langflow
    langflow_config = configure_langflow(hardware, existing_config)
    
    # Обновляем конфигурационные файлы
    full_config = update_config_files(existing_config, langflow_config)
    
    # Запускаем Langflow
    start_langflow()
    
    console.print("\n[green]🎉 Langflow успешно добавлен![/green]")


if __name__ == "__main__":
    main()

