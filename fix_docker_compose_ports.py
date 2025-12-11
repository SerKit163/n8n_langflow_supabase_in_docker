#!/usr/bin/env python3
"""
Скрипт для исправления секций ports в docker-compose.yml
"""
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv
import os

console = Console()


def fix_docker_compose():
    """Исправляет docker-compose.yml, добавляя правильные секции ports"""
    compose_path = Path("docker-compose.yml")
    
    if not compose_path.exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        return False
    
    content = compose_path.read_text(encoding='utf-8')
    original_content = content
    
    # Загружаем .env
    load_dotenv()
    
    # Список сервисов для обработки
    services = [
        ("n8n", os.getenv("N8N_PORT", "5678"), "5678"),
        ("langflow", os.getenv("LANGFLOW_PORT", "7860"), "7860"),
    ]
    
    for service_name, external_port, internal_port in services:
        # Ищем блок сервиса - от начала сервиса до следующей секции
        # Паттерн: находим весь блок сервиса до следующей секции (deploy, volumes, networks, restart)
        pattern = rf'(\s+{service_name}:[^\n]*\n)((?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)(deploy:|volumes:|networks:|restart:)'
        
        def replace_service(match):
            service_header = match.group(1)  # "  n8n:\n"
            service_body = match.group(2)  # Все что между заголовком и следующей секцией
            indent = match.group(3)  # Отступ (обычно 4 пробела)
            next_section = match.group(4)  # "deploy:" или другая секция
            
            # Проверяем, есть ли уже незакомментированная секция ports
            if re.search(rf'^{indent}ports:\s*$', service_body, re.MULTILINE):
                # Порты уже есть, пропускаем
                return match.group(0)
            
            # Удаляем все закомментированные секции ports
            # Удаляем комментарии о портах
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
            ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{external_port}:{internal_port}"\n'
            
            return f'{service_header}{service_body}{ports_section}{indent}{next_section}'
        
        new_content = re.sub(pattern, replace_service, content, flags=re.MULTILINE)
        
        if new_content != content:
            content = new_content
            console.print(f"[green]✓ Порт {external_port} добавлен для {service_name}[/green]")
        else:
            console.print(f"[yellow]⚠ Не удалось добавить порт для {service_name}[/yellow]")
    
    if content != original_content:
        # Сохраняем резервную копию
        backup_path = compose_path.with_suffix('.yml.backup')
        if compose_path.exists():
            backup_path.write_text(original_content, encoding='utf-8')
            console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        # Сохраняем исправленный файл
        compose_path.write_text(content, encoding='utf-8')
        console.print("[green]✓ docker-compose.yml исправлен[/green]")
        return True
    else:
        console.print("[yellow]⚠ Изменений не требуется[/yellow]")
        return False


def validate_yaml():
    """Проверяет синтаксис YAML"""
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
            return True
        else:
            console.print("[red]❌ Ошибка в docker-compose.yml:[/red]")
            console.print(result.stderr)
            return False
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось проверить синтаксис: {e}[/yellow]")
        return None


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔧 Исправление docker-compose.yml[/bold cyan]",
        border_style="cyan"
    ))
    
    # Исправляем файл
    if fix_docker_compose():
        # Проверяем синтаксис
        console.print("\n[cyan]🔍 Проверка синтаксиса...[/cyan]")
        is_valid = validate_yaml()
        
        if is_valid:
            console.print("\n[bold green]✅ Готово![/bold green]")
            console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
            console.print("1. Перезапустите сервисы: docker-compose up -d")
            console.print("2. Сервисы будут доступны:")
            console.print("   - Через Caddy (HTTPS): https://домен")
            console.print("   - Напрямую (HTTP): http://localhost:ПОРТ")
        elif is_valid is False:
            console.print("\n[red]❌ Ошибка синтаксиса![/red]")
            console.print("[yellow]💡 Восстановите из резервной копии:[/yellow]")
            console.print("   cp docker-compose.yml.backup docker-compose.yml")
    else:
        console.print("\n[yellow]⚠ Файл не был изменен[/yellow]")


if __name__ == "__main__":
    main()

