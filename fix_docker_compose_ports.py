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
        # Проверяем, есть ли уже незакомментированная секция ports
        ports_pattern = rf'^\s+{service_name}:[^\n]*\n(?:[^\n]*\n)*?\s+ports:\s*$'
        if re.search(ports_pattern, content, re.MULTILINE):
            console.print(f"[cyan]ℹ Секция ports уже существует для {service_name}, пропускаем[/cyan]")
            continue
        
        # Проверяем, существует ли сервис в файле
        service_exists = re.search(rf'^\s+{service_name}:', content, re.MULTILINE)
        if not service_exists:
            console.print(f"[yellow]⚠ Сервис {service_name} не найден в docker-compose.yml[/yellow]")
            continue
        
        # Ищем место для вставки: после environment (для n8n) или после user (для langflow), перед deploy
        # Паттерн 1: после environment, перед deploy
        pattern1 = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+deploy:)[^\n]*\n)*?\s+environment:[^\n]*\n(?:(?!\s+deploy:)[^\n]*\n)*?)(\s+)(deploy:)'
        
        def replace_after_env(match):
            before_deploy = match.group(1)
            indent = match.group(2)
            deploy_section = match.group(3)
            
            # Удаляем закомментированные ports если есть
            before_deploy = re.sub(
                rf'{indent}#.*[пп]орт.*\n{indent}#\s+ports:\n{indent}#\s+- "[^"]+":\d+\n?',
                '',
                before_deploy,
                flags=re.MULTILINE | re.IGNORECASE
            )
            before_deploy = re.sub(
                rf'{indent}# ВАЖНО:.*\n{indent}#\s+ports:\n{indent}#\s+- "[^"]+":\d+\n?',
                '',
                before_deploy,
                flags=re.MULTILINE | re.IGNORECASE
            )
            
            # Добавляем секцию ports перед deploy
            ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{external_port}:{internal_port}"\n'
            
            return f'{before_deploy}{ports_section}{indent}{deploy_section}'
        
        new_content = re.sub(pattern1, replace_after_env, content, flags=re.MULTILINE)
        
        if new_content != content:
            content = new_content
            console.print(f"[green]✓ Порт {external_port} добавлен для {service_name}[/green]")
            continue
        
        # Паттерн 2: для langflow - после user, перед environment
        pattern2 = rf'(\s+{service_name}:[^\n]*\n\s+user:[^\n]*\n)(\s+)(# ВАЖНО:.*\n\s+#\s+ports:\n\s+#\s+- "[^"]+":\d+\n\s+)(environment:)'
        
        def replace_after_user(match):
            before_env = match.group(1)
            indent = match.group(2)
            commented_ports = match.group(3)
            env_section = match.group(4)
            
            # Заменяем закомментированные ports на активные
            ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{external_port}:{internal_port}"\n'
            
            return f'{before_env}{ports_section}{indent}{env_section}'
        
        new_content = re.sub(pattern2, replace_after_user, content, flags=re.MULTILINE)
        
        if new_content != content:
            content = new_content
            console.print(f"[green]✓ Порт {external_port} добавлен для {service_name}[/green]")
            continue
        
        # Паттерн 3: универсальный - перед любой следующей секцией (deploy, volumes, networks, restart)
        pattern3 = rf'(\s+{service_name}:[^\n]*\n)((?:(?!\s+(?:deploy|volumes|networks|restart|healthcheck|entrypoint):)[^\n]*\n)*?)(\s+)(deploy:|volumes:|networks:|restart:)'
        
        def replace_before_section(match):
            service_header = match.group(1)
            service_body = match.group(2)
            indent = match.group(3)
            next_section = match.group(4)
            
            # Удаляем закомментированные ports
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
            
            # Добавляем секцию ports
            ports_section = f'{indent}# Прямой доступ через порт (fallback при проблемах с SSL)\n{indent}ports:\n{indent}  - "{external_port}:{internal_port}"\n'
            
            return f'{service_header}{service_body}{ports_section}{indent}{next_section}'
        
        new_content = re.sub(pattern3, replace_before_section, content, flags=re.MULTILINE)
        
        if new_content != content:
            content = new_content
            console.print(f"[green]✓ Порт {external_port} добавлен для {service_name}[/green]")
        else:
            console.print(f"[yellow]⚠ Не удалось добавить порт для {service_name}[/yellow]")
            console.print(f"[cyan]💡 Попробуйте добавить вручную в docker-compose.yml:[/cyan]")
            console.print(f"   ports:")
            console.print(f'     - "{external_port}:{internal_port}"')
    
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

