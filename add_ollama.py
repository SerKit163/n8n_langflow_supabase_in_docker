#!/usr/bin/env python3
"""
Скрипт для добавления Ollama к существующей установке
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
🤖 Добавление Ollama к существующей установке

Этот скрипт добавит Ollama к вашей текущей установке n8n, Langflow и Supabase.
Ollama - это локальный сервер для запуска больших языковых моделей.

⚠️  ВНИМАНИЕ:
  • Ollama требует много памяти (минимум 2GB, рекомендуется 4-8GB)
  • Для GPU версии нужна NVIDIA GPU с CUDA
  • Без GPU Ollama будет работать медленно на CPU
    """
    console.print(Panel(welcome_text, title="Добавление Ollama", border_style="cyan"))


def check_existing_config():
    """Проверяет существующую конфигурацию"""
    env_path = Path(".env")
    if not env_path.exists():
        console.print("[red]❌ Файл .env не найден![/red]")
        console.print("[yellow]Запустите сначала python3 setup.py для первоначальной установки[/yellow]")
        sys.exit(1)
    
    config = dotenv_values(env_path)
    
    # Проверяем, не включен ли уже Ollama
    if config.get('OLLAMA_ENABLED', '').lower() == 'true':
        console.print("[yellow]⚠️  Ollama уже включен в конфигурации![/yellow]")
        if not Confirm.ask("Переконфигурировать Ollama?", default=False):
            sys.exit(0)
    
    return config


def configure_ollama(hardware, existing_config):
    """Настраивает Ollama"""
    console.print("\n[cyan]⚙️ Настройка Ollama[/cyan]")
    
    # Определяем, есть ли GPU
    has_gpu = hardware['gpu']['available'] and hardware['gpu'].get('cuda_available', False)
    
    if has_gpu:
        console.print("[green]✓ Обнаружена NVIDIA GPU с CUDA[/green]")
        ollama_image = "ollama/ollama:latest-gpu"
        console.print("[yellow]💡 Будет использована GPU версия Ollama[/yellow]")
    else:
        console.print("[yellow]⚠️  GPU не обнаружена или CUDA недоступна[/yellow]")
        console.print("[yellow]💡 Будет использована CPU версия (работает медленнее)[/yellow]")
        if not Confirm.ask("Продолжить с CPU версией?", default=True):
            sys.exit(0)
        ollama_image = "ollama/ollama:latest"
    
    # Получаем рекомендуемые настройки
    # Временно включаем ollama для правильного расчета ресурсов
    hardware_temp = hardware.copy()
    hardware_temp['gpu'] = hardware['gpu'].copy()
    hardware_temp['gpu']['available'] = has_gpu  # Устанавливаем доступность GPU
    recommended_config = adapt_config_for_hardware(hardware_temp)
    
    # Если память для Ollama равна 0, устанавливаем минимум
    if recommended_config['memory_limits']['ollama'] == 0:
        total_ram = hardware['ram']['total_gb']
        # Для CPU версии используем 30% от RAM, минимум 2GB, максимум 4GB
        recommended_config['memory_limits']['ollama'] = max(2.0, min(total_ram * 0.3, 4.0))
        recommended_config['cpu_limits']['ollama'] = min(0.5, hardware['cpu']['cores'] * 0.3)
    
    # Режим маршрутизации
    routing_mode = existing_config.get('ROUTING_MODE', '')
    
    ollama_config = {
        'ollama_enabled': True,
        'ollama_image': ollama_image,
        'ollama_port': 11434,
        'ollama_memory_limit': f"{recommended_config['memory_limits']['ollama']:.1f}g",
        'ollama_cpu_limit': recommended_config['cpu_limits']['ollama'],
    }
    
    # Настройка домена/пути в зависимости от режима маршрутизации
    if routing_mode == 'subdomain':
        console.print("\n[cyan]🌐 Настройка домена для Ollama:[/cyan]")
        
        # Извлекаем базовый домен из существующих доменов
        base_domain = None
        existing_domains = [
            existing_config.get('SUPABASE_DOMAIN', ''),
            existing_config.get('N8N_DOMAIN', ''),
            existing_config.get('LANGFLOW_DOMAIN', '')
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
            "Автоматически сформировать поддомен для Ollama?",
            default=True
        )
        
        if use_auto and base_domain:
            # АВТОМАТИЧЕСКИЙ РЕЖИМ
            auto_domain = f"ollama.{base_domain}"
            console.print(f"\n[green]✓ Предложенный домен: {auto_domain}[/green]")
            if Confirm.ask(f"Использовать домен {auto_domain}?", default=True):
                ollama_config['ollama_domain'] = auto_domain
            else:
                # Ручной ввод
                while True:
                    ollama_domain = Prompt.ask(
                        "Домен для Ollama (например, ollama.example.com) или '-' для пропуска",
                        default=existing_config.get('OLLAMA_DOMAIN', auto_domain)
                    )
                    if ollama_domain == '-':
                        console.print("[yellow]⚠️  Домен не указан, Ollama будет доступен только по IP:порт[/yellow]")
                        break
                    is_valid, error = validate_domain(ollama_domain)
                    if is_valid:
                        ollama_config['ollama_domain'] = ollama_domain
                        break
                    else:
                        console.print(f"[red]❌ {error}[/red]")
        else:
            # РУЧНОЙ РЕЖИМ
            while True:
                ollama_domain = Prompt.ask(
                    "Домен для Ollama (например, ollama.example.com) или '-' для пропуска",
                    default=existing_config.get('OLLAMA_DOMAIN', '')
                )
                if ollama_domain == '-':
                    console.print("[yellow]⚠️  Домен не указан, Ollama будет доступен только по IP:порт[/yellow]")
                    break
                is_valid, error = validate_domain(ollama_domain)
                if is_valid:
                    ollama_config['ollama_domain'] = ollama_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    elif routing_mode == 'path':
        console.print("\n[cyan]🌐 Настройка пути для Ollama:[/cyan]")
        base_domain = existing_config.get('BASE_DOMAIN', '')
        
        if base_domain:
            # Предлагаем автоматический или ручной режим
            use_auto = Confirm.ask(
                "Автоматически использовать путь /ollama?",
                default=True
            )
            
            if use_auto:
                # АВТОМАТИЧЕСКИЙ РЕЖИМ
                auto_path = '/ollama'
                console.print(f"\n[green]✓ Предложенный путь: {base_domain}{auto_path}[/green]")
                if Confirm.ask(f"Использовать путь {auto_path}?", default=True):
                    ollama_config['ollama_path'] = auto_path
                    ollama_config['base_domain'] = base_domain
                else:
                    # Ручной ввод
                    while True:
                        ollama_path = Prompt.ask(
                            "Путь для Ollama (например, /ollama)",
                            default=existing_config.get('OLLAMA_PATH', '/ollama')
                        )
                        is_valid, error = validate_path(ollama_path)
                        if is_valid:
                            ollama_config['ollama_path'] = ollama_path
                            ollama_config['base_domain'] = base_domain
                            break
                        else:
                            console.print(f"[red]❌ {error}[/red]")
            else:
                # РУЧНОЙ РЕЖИМ
                while True:
                    ollama_path = Prompt.ask(
                        "Путь для Ollama (например, /ollama)",
                        default=existing_config.get('OLLAMA_PATH', '/ollama')
                    )
                    is_valid, error = validate_path(ollama_path)
                    if is_valid:
                        ollama_config['ollama_path'] = ollama_path
                        ollama_config['base_domain'] = base_domain
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
                    ollama_config['base_domain'] = base_domain
                    # Предлагаем путь
                    use_auto = Confirm.ask("Автоматически использовать путь /ollama?", default=True)
                    if use_auto:
                        ollama_config['ollama_path'] = '/ollama'
                    else:
                        while True:
                            ollama_path = Prompt.ask("Путь для Ollama", default="/ollama")
                            is_valid, error = validate_path(ollama_path)
                            if is_valid:
                                ollama_config['ollama_path'] = ollama_path
                                break
                            else:
                                console.print(f"[red]❌ {error}[/red]")
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    else:
        console.print("\n[cyan]🔌 Настройка порта для Ollama:[/cyan]")
        ollama_port = IntPrompt.ask(
            "Порт для Ollama",
            default=11434
        )
        ollama_config['ollama_port'] = ollama_port
    
    # Настройка ресурсов
    console.print("\n[cyan]💾 Настройка ресурсов:[/cyan]")
    use_recommended = Confirm.ask(
        f"Использовать рекомендуемые настройки? (Память: {ollama_config['ollama_memory_limit']}, CPU: {ollama_config['ollama_cpu_limit']})",
        default=True
    )
    
    if not use_recommended:
        ollama_config['ollama_memory_limit'] = Prompt.ask(
            "Лимит памяти (например, 4g)",
            default=ollama_config['ollama_memory_limit']
        )
        ollama_config['ollama_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(ollama_config['ollama_cpu_limit'])
        ))
    
    return ollama_config


def update_config_files(existing_config, ollama_config):
    """Обновляет конфигурационные файлы"""
    console.print("\n[cyan]📝 Обновление конфигурации...[/cyan]")
    
    # Обновляем .env файл
    env_path = Path(".env")
    
    # Добавляем/обновляем переменные Ollama
    set_key(env_path, 'OLLAMA_ENABLED', 'true')
    set_key(env_path, 'OLLAMA_PORT', str(ollama_config.get('ollama_port', 11434)))
    set_key(env_path, 'OLLAMA_MEMORY_LIMIT', ollama_config.get('ollama_memory_limit', '4g'))
    set_key(env_path, 'OLLAMA_CPU_LIMIT', str(ollama_config.get('ollama_cpu_limit', 1.0)))
    
    if ollama_config.get('ollama_domain'):
        set_key(env_path, 'OLLAMA_DOMAIN', ollama_config['ollama_domain'])
    if ollama_config.get('ollama_path'):
        set_key(env_path, 'OLLAMA_PATH', ollama_config['ollama_path'])
    
    console.print("[green]✓ .env файл обновлен[/green]")
    
    # Обновляем существующую конфигурацию для генерации docker-compose
    full_config = dict(existing_config)
    full_config.update({
        'ollama_enabled': True,
        'ollama_port': ollama_config.get('ollama_port', 11434),
        'ollama_memory_limit': ollama_config.get('ollama_memory_limit', '4g'),
        'ollama_cpu_limit': ollama_config.get('ollama_cpu_limit', 1.0),
        'ollama_domain': ollama_config.get('ollama_domain', ''),
        'ollama_path': ollama_config.get('ollama_path', '/ollama'),
        'ollama_image': ollama_config.get('ollama_image', 'ollama/ollama:latest'),
    })
    
    # Обновляем routing_mode если его нет
    if 'routing_mode' not in full_config:
        full_config['routing_mode'] = existing_config.get('ROUTING_MODE', '')
    
    # Обновляем другие необходимые переменные
    for key in ['n8n_domain', 'langflow_domain', 'supabase_domain', 'base_domain',
                'letsencrypt_email', 'ssl_enabled', 'n8n_port', 'langflow_port',
                'supabase_port', 'n8n_path', 'langflow_path', 'supabase_path']:
        if key.upper() in existing_config:
            full_config[key] = existing_config[key.upper()]
    
    # Генерируем docker-compose.yml
    hardware = detect_hardware()
    generate_docker_compose(full_config, hardware)
    console.print("[green]✓ docker-compose.yml обновлен[/green]")
    
    # Генерируем Caddyfile если используется режим поддоменов
    if existing_config.get('ROUTING_MODE') == 'subdomain':
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile обновлен[/green]")
    
    # Создаем директорию для данных Ollama
    ensure_dir("volumes/ollama_data")
    console.print("[green]✓ Директория для данных Ollama создана[/green]")
    
    return full_config


def start_ollama():
    """Запускает Ollama контейнер"""
    console.print("\n[cyan]🚀 Запуск Ollama...[/cyan]")
    
    if Confirm.ask("Запустить Ollama сейчас?", default=True):
        # Используем docker_compose_up для показа прогресса загрузки образов
        if docker_compose_up(detach=True):
            console.print("[green]✓ Ollama запущен![/green]")
            
            # Показываем информацию о доступе
            console.print("\n[cyan]📋 Информация для доступа:[/cyan]")
            try:
                config = dotenv_values(".env")
                routing_mode = config.get('ROUTING_MODE', '')
                
                if routing_mode == 'subdomain':
                    domain = config.get('OLLAMA_DOMAIN', '')
                    if domain:
                        protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                        console.print(f"  [green]✓[/green] Ollama: {protocol}://{domain}")
                elif routing_mode == 'path':
                    base_domain = config.get('BASE_DOMAIN', '')
                    ollama_path = config.get('OLLAMA_PATH', '/ollama')
                    if base_domain:
                        protocol = 'https' if config.get('SSL_ENABLED', 'true').lower() == 'true' else 'http'
                        console.print(f"  [green]✓[/green] Ollama: {protocol}://{base_domain}{ollama_path}")
                else:
                    port = config.get('OLLAMA_PORT', '11434')
                    console.print(f"  [green]✓[/green] Ollama: http://localhost:{port}")
                
                console.print("\n[yellow]💡 После запуска Ollama вы можете скачать модели командой:[/yellow]")
                console.print("[dim]docker exec -it ollama ollama pull llama2[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠️  Не удалось получить информацию о доступе: {e}[/yellow]")
        else:
            console.print("[red]❌ Ошибка при запуске Ollama[/red]")
            console.print("\n[yellow]💡 Попробуйте запустить вручную:[/yellow]")
            console.print("[dim]docker-compose up -d ollama[/dim]")


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
    if hardware['gpu']['available']:
        console.print(f"[green]✓ GPU: {hardware['gpu'].get('name', 'Обнаружена')}[/green]")
    
    # Настраиваем Ollama
    ollama_config = configure_ollama(hardware, existing_config)
    
    # Обновляем конфигурационные файлы
    full_config = update_config_files(existing_config, ollama_config)
    
    # Запускаем Ollama
    start_ollama()
    
    console.print("\n[green]🎉 Ollama успешно добавлен![/green]")


if __name__ == "__main__":
    main()

