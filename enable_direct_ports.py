#!/usr/bin/env python3
"""
Скрипт для включения прямого доступа через порты (fallback при проблемах с SSL)
"""
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv
import os

console = Console()


def read_docker_compose():
    """Читает docker-compose.yml"""
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        return None
    return compose_path.read_text(encoding='utf-8')


def write_docker_compose(content):
    """Записывает docker-compose.yml"""
    compose_path = Path("docker-compose.yml")
    compose_path.write_text(content, encoding='utf-8')
    console.print("[green]✓ docker-compose.yml обновлен[/green]")


def enable_ports_for_service(content, service_name, port_env_var, default_port):
    """Включает порты для сервиса"""
    # Загружаем .env для получения портов
    load_dotenv()
    port = os.getenv(port_env_var, default_port)
    
    if not port:
        port = default_port
        console.print(f"[yellow]⚠ Порт для {service_name} не найден в .env, используем {default_port}[/yellow]")
    
    # Ищем блок сервиса с закомментированными портами
    # Паттерн для поиска: сервис -> комментарий о портах -> закомментированные ports
    pattern = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy\.\n(\s+)# ports:\n(\s+)#\s+- "[^"]+":(\d+)'
    
    def replace_func(match):
        indent = match.group(2)
        internal_port = match.group(5) if match.group(5) else default_port
        return f'{match.group(1)}{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{port}:{internal_port}"'
    
    new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
    
    if new_content != content:
        console.print(f"[green]✓ Порт {port} включен для {service_name}[/green]")
        return new_content
    else:
        # Попробуем найти уже существующий блок ports (закомментированный)
        pattern2 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)#.*[пп]орт.*\n(\s+)#\s+ports:\n(\s+)#\s+- "[^"]+":(\d+)'
        new_content = re.sub(pattern2, replace_func, content, flags=re.MULTILINE)
        
        if new_content == content:
            # Если не нашли, добавляем секцию ports после environment
            pattern3 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+deploy:)[^\n]*\n)*?)(\s+deploy:)'
            def add_ports_func(match):
                indent = match.group(2)
                return f'{match.group(1)}{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{port}:{default_port}"\n{match.group(2)}deploy:'
            new_content = re.sub(pattern3, add_ports_func, content, flags=re.MULTILINE)
        
        if new_content != content:
            console.print(f"[green]✓ Порт {port} включен для {service_name}[/green]")
        else:
            console.print(f"[yellow]⚠ Не удалось автоматически включить порт для {service_name}[/yellow]")
            console.print(f"[cyan]💡 Вручную раскомментируйте секцию ports в docker-compose.yml для {service_name}[/cyan]")
        
        return new_content


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔌 Включение прямого доступа через порты[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Включит прямой доступ к сервисам через порты (localhost:ПОРТ)")
    console.print("2. Это позволит использовать сервисы даже при проблемах с SSL")
    console.print("3. Сервисы будут доступны как через Caddy (HTTPS), так и напрямую (HTTP)")
    
    console.print("\n[cyan]💡 Доступные сервисы:[/cyan]")
    console.print("  - N8N: обычно порт 5678")
    console.print("  - Langflow: обычно порт 7860")
    console.print("  - Supabase DB: обычно порт 8000")
    
    if not console.input("\n[cyan]Продолжить? (y/n): [/cyan]").lower().startswith('y'):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # Читаем docker-compose.yml
    content = read_docker_compose()
    if not content:
        return
    
    # Включаем порты для каждого сервиса
    services = [
        ("n8n", "N8N_PORT", "5678"),
        ("langflow", "LANGFLOW_PORT", "7860"),
    ]
    
    for service_name, port_env, default_port in services:
        content = enable_ports_for_service(content, service_name, port_env, default_port)
    
    # Сохраняем изменения
    write_docker_compose(content)
    
    console.print("\n[bold green]✅ Готово![/bold green]")
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    console.print("1. Перезапустите сервисы: docker-compose up -d")
    console.print("2. Сервисы будут доступны:")
    console.print("   - Через Caddy (HTTPS): https://домен")
    console.print("   - Напрямую (HTTP): http://localhost:ПОРТ")
    console.print("\n[yellow]⚠ Внимание:[/yellow]")
    console.print("- Прямой доступ через порты работает только по HTTP (без SSL)")
    console.print("- Для продакшена рекомендуется использовать только Caddy (HTTPS)")
    console.print("- Прямой доступ можно отключить, закомментировав секции ports в docker-compose.yml")


if __name__ == "__main__":
    main()

