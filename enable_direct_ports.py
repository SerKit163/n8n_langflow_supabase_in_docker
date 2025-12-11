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
    
    # Ищем блок сервиса - от начала сервиса до следующей секции (deploy, volumes, networks)
    # Паттерн: находим весь блок сервиса до следующей секции
    pattern = rf'(\s+{service_name}:[^\n]*\n)((?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)(deploy:|volumes:|networks:|restart:)'
    
    def replace_func(match):
        service_header = match.group(1)  # "  n8n:\n"
        service_body = match.group(2)  # Все что между заголовком и следующей секцией
        indent = match.group(3)  # Отступ (обычно 4 пробела)
        next_section = match.group(4)  # "deploy:" или другая секция
        
        # Проверяем, есть ли уже незакомментированная секция ports
        if re.search(rf'^{indent}ports:', service_body, re.MULTILINE):
            # Порты уже есть, пропускаем
            return match.group(0)
        
        # Удаляем все закомментированные секции ports
        service_body = re.sub(
            rf'{indent}#.*[пп]орт.*\n{indent}#\s+ports:\n{indent}#\s+- "[^"]+":\d+\n?',
            '',
            service_body,
            flags=re.MULTILINE | re.IGNORECASE
        )
        service_body = re.sub(
            rf'{indent}# ВАЖНО:.*\n{indent}#\s+ports:\n{indent}#\s+- "[^"]+":\d+\n?',
            '',
            service_body,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Добавляем секцию ports перед следующей секцией
        ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{port}:{internal_port}"\n'
        
        return f'{service_header}{service_body}{ports_section}{indent}{next_section}'
    
    new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
    
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

