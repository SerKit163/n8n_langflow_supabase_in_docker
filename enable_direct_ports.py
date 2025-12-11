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
    # Создаем резервную копию
    backup_path = compose_path.with_suffix('.yml.backup')
    if compose_path.exists():
        backup_path.write_text(compose_path.read_text(encoding='utf-8'), encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
    
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
    
    # Определяем внутренний порт (обычно такой же как внешний для этих сервисов)
    internal_port = default_port
    
    # Проверяем, есть ли уже незакомментированная секция ports
    if re.search(rf'^\s+{service_name}:[^\n]*\n(?:[^\n]*\n)*?\s+ports:\s*$', content, re.MULTILINE):
        console.print(f"[cyan]ℹ Секция ports уже существует для {service_name}, пропускаем[/cyan]")
        return content
    
    # Паттерн 1: стандартный формат с комментарием "ВАЖНО: Не открываем порт..."
    pattern1 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy\.\n(\s+)# ports:\n(\s+)#\s+- "[^"]+":(\d+)'
    
    def replace_commented_ports1(match):
        before_comment = match.group(1)
        indent = match.group(2)
        indent2 = match.group(3)
        indent3 = match.group(4)
        internal_port_found = match.group(5)
        
        # Используем найденный внутренний порт или дефолтный
        internal = internal_port_found if internal_port_found else internal_port
        
        ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent2}ports:\n{indent3}  - "{port}:{internal}"\n'
        
        return f'{before_comment}{ports_section}'
    
    new_content = re.sub(pattern1, replace_commented_ports1, content, flags=re.MULTILINE)
    
    if new_content != content:
        console.print(f"[green]✓ Порт {port} включен для {service_name}[/green]")
        return new_content
    
    # Паттерн 2: любой закомментированный блок ports
    pattern2 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)#.*[пп]орт.*\n(\s+)#\s+ports:\n(\s+)#\s+- "[^"]+":(\d+)'
    
    def replace_commented_ports2(match):
        before_comment = match.group(1)
        indent = match.group(2)
        indent2 = match.group(3)
        indent3 = match.group(4)
        internal_port_found = match.group(5)
        
        internal = internal_port_found if internal_port_found else internal_port
        
        ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent2}ports:\n{indent3}  - "{port}:{internal}"\n'
        
        return f'{before_comment}{ports_section}'
    
    new_content = re.sub(pattern2, replace_commented_ports2, content, flags=re.MULTILINE)
    
    if new_content != content:
        console.print(f"[green]✓ Порт {port} включен для {service_name}[/green]")
        return new_content
    
    # Паттерн 3: вставляем перед deploy (если закомментированных портов нет)
    pattern3 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+deploy:)[^\n]*\n)*?)(\s+)(deploy:)'
    
    def insert_before_deploy(match):
        before_deploy = match.group(1)
        indent = match.group(2)
        deploy_section = match.group(3)
        
        ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{port}:{internal_port}"\n'
        
        return f'{before_deploy}{ports_section}{indent}{deploy_section}'
    
    new_content = re.sub(pattern3, insert_before_deploy, content, flags=re.MULTILINE)
    
    if new_content != content:
        console.print(f"[green]✓ Порт {port} включен для {service_name}[/green]")
        return new_content
    else:
        console.print(f"[yellow]⚠ Не удалось автоматически включить порт для {service_name}[/yellow]")
        return content


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
    
    # Проверяем синтаксис YAML
    console.print("\n[cyan]🔍 Проверка синтаксиса docker-compose.yml...[/cyan]")
    import subprocess
    try:
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            console.print("[green]✓ Синтаксис docker-compose.yml корректен[/green]")
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
        else:
            console.print("[red]❌ Ошибка синтаксиса в docker-compose.yml![/red]")
            console.print(result.stderr)
            console.print("\n[yellow]💡 Восстановите из резервной копии:[/yellow]")
            console.print("   cp docker-compose.yml.backup docker-compose.yml")
            console.print("\n[cyan]Или используйте скрипт исправления:[/cyan]")
            console.print("   python3 fix_docker_compose_ports.py")
    except FileNotFoundError:
        console.print("[yellow]⚠ docker-compose не найден, пропускаем проверку синтаксиса[/yellow]")
        console.print("\n[bold green]✅ Изменения сохранены![/bold green]")
        console.print("[cyan]💡 Проверьте синтаксис вручную: docker-compose config[/cyan]")
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось проверить синтаксис: {e}[/yellow]")
        console.print("\n[bold green]✅ Изменения сохранены![/bold green]")
        console.print("[cyan]💡 Проверьте синтаксис вручную: docker-compose config[/cyan]")


if __name__ == "__main__":
    main()

