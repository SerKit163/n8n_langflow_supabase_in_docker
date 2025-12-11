#!/usr/bin/env python3
"""
Скрипт для переключения с режима доменов на режим портов (без SSL)
Полезно когда нужно работать сразу, без ожидания SSL сертификатов
"""
import re
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
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
    
    # Проверяем, есть ли уже незакомментированная секция ports
    if re.search(rf'^\s+{service_name}:[^\n]*\n(?:[^\n]*\n)*?\s+ports:\s*$', content, re.MULTILINE):
        console.print(f"[cyan]ℹ Порт уже включен для {service_name}, пропускаем[/cyan]")
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
        internal = internal_port_found if internal_port_found else default_port
        
        ports_section = f'{indent}# Прямой доступ через порт (режим без доменов)\n{indent2}ports:\n{indent3}  - "{port}:{internal}"\n'
        
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
        
        internal = internal_port_found if internal_port_found else default_port
        
        ports_section = f'{indent}# Прямой доступ через порт (режим без доменов)\n{indent2}ports:\n{indent3}  - "{port}:{internal}"\n'
        
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
        
        ports_section = f'{indent}# Прямой доступ через порт (режим без доменов)\n{indent}ports:\n{indent}  - "{port}:{default_port}"\n'
        
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
        "[bold cyan]🔌 Переключение на режим портов (без SSL)[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Включит прямой доступ к сервисам через порты (HTTP)")
    console.print("2. Отключит использование доменов и SSL")
    console.print("3. Позволит работать сразу, без ожидания SSL сертификатов")
    
    console.print("\n[cyan]💡 Доступ к сервисам:[/cyan]")
    console.print("  - N8N: http://localhost:5678 или http://IP_СЕРВЕРА:5678")
    console.print("  - Langflow: http://localhost:7860 или http://IP_СЕРВЕРА:7860")
    console.print("  - Supabase Studio: http://localhost:3000 или http://IP_СЕРВЕРА:3000")
    
    console.print("\n[yellow]⚠ Внимание:[/yellow]")
    console.print("  • Доступ только по HTTP (без SSL)")
    console.print("  • Для продакшена рекомендуется использовать домены с SSL")
    console.print("  • Позже можно переключиться обратно: python3 switch_to_domains.py")
    
    if not Confirm.ask("\n[cyan]Продолжить? (y/n): [/cyan]", default=True):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # Загружаем текущую конфигурацию
    load_dotenv()
    
    # Проверяем какие сервисы включены
    n8n_enabled = os.getenv('N8N_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    langflow_enabled = os.getenv('LANGFLOW_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    
    # Обновляем .env
    console.print("\n[cyan]Шаг 1: Обновление .env[/cyan]")
    env_path = Path(".env")
    if env_path.exists():
        env_content = env_path.read_text(encoding='utf-8')
        
        # Обновляем routing_mode
        env_content = re.sub(
            r'^ROUTING_MODE=.*$',
            "ROUTING_MODE=none",
            env_content,
            flags=re.MULTILINE
        )
        
        # Отключаем SSL
        env_content = re.sub(
            r'^SSL_ENABLED=.*$',
            "SSL_ENABLED=false",
            env_content,
            flags=re.MULTILINE
        )
        
        env_path.write_text(env_content, encoding='utf-8')
        console.print("[green]✓ .env обновлен[/green]")
    else:
        console.print("[yellow]⚠ Файл .env не найден[/yellow]")
    
    # Включаем порты в docker-compose.yml
    console.print("\n[cyan]Шаг 2: Включение прямых портов[/cyan]")
    content = read_docker_compose()
    if content:
        if n8n_enabled:
            content = enable_ports_for_service(content, 'n8n', 'N8N_PORT', '5678')
        if langflow_enabled:
            content = enable_ports_for_service(content, 'langflow', 'LANGFLOW_PORT', '7860')
        content = enable_ports_for_service(content, 'supabase-studio', 'SUPABASE_KB_PORT', '3000')
        write_docker_compose(content)
    
    # Проверяем синтаксис YAML
    console.print("\n[cyan]Шаг 3: Проверка синтаксиса docker-compose.yml...[/cyan]")
    try:
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            console.print("[green]✓ Синтаксис docker-compose.yml корректен[/green]")
        else:
            console.print("[red]❌ Ошибка синтаксиса в docker-compose.yml![/red]")
            console.print(result.stderr)
            console.print("\n[yellow]💡 Восстановите из резервной копии:[/yellow]")
            console.print("   cp docker-compose.yml.backup docker-compose.yml")
            return
    except FileNotFoundError:
        console.print("[yellow]⚠ docker-compose не найден, пропускаем проверку синтаксиса[/yellow]")
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось проверить синтаксис: {e}[/yellow]")
    
    # Перезапускаем сервисы
    console.print("\n[cyan]Шаг 4: Перезапуск сервисов[/cyan]")
    if Confirm.ask("Перезапустить сервисы? (y/n)", default=True):
        try:
            subprocess.run(
                ["docker-compose", "up", "-d"],
                check=True,
                timeout=60
            )
            console.print("[green]✓ Сервисы перезапущены[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Не удалось перезапустить сервисы: {e}[/yellow]")
            console.print("[cyan]💡 Запустите вручную: docker-compose up -d[/cyan]")
    
    console.print("\n[bold green]✅ Готово![/bold green]")
    console.print("\n[cyan]💡 Сервисы доступны:[/cyan]")
    if n8n_enabled:
        console.print(f"  • N8N: http://localhost:5678")
    if langflow_enabled:
        console.print(f"  • Langflow: http://localhost:7860")
    console.print(f"  • Supabase Studio: http://localhost:3000")
    console.print("\n[yellow]⚠ Внимание:[/yellow]")
    console.print("- Доступ только по HTTP (без SSL)")
    console.print("- Для продакшена рекомендуется использовать домены с SSL")
    console.print("- Переключитесь обратно: python3 switch_to_domains.py")


if __name__ == "__main__":
    main()

