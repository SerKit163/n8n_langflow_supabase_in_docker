#!/usr/bin/env python3
"""
Скрипт для восстановления правильных версий Docker образов
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
import subprocess
import re

console = Console()

# Правильные версии образов
CORRECT_VERSIONS = {
    'n8n': 'n8nio/n8n:latest',
    'langflow': 'langflowai/langflow:latest',
    'supabase-db': 'ghcr.io/supabase/postgres:15.1.0.119',
    'supabase-auth': 'ghcr.io/supabase/gotrue:v2.162.0',
    'supabase-rest': 'ghcr.io/supabase/postgrest:v12.2.0',
    'supabase-studio': 'ghcr.io/supabase/studio:20240513-d025e0f',
    'caddy': 'caddy:latest'
}


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🔧 Восстановление версий Docker образов

Этот скрипт восстановит правильные версии образов в docker-compose.yml
после неправильного обновления.

⚠️  ВНИМАНИЕ:
  • Скрипт остановит и перезапустит сервисы
  • Все данные сохранятся в volumes
    """
    console.print(Panel(welcome_text, title="Восстановление версий", border_style="yellow"))


def restore_docker_compose():
    """Восстанавливает правильные версии в docker-compose.yml"""
    compose_file = Path("docker-compose.yml")
    
    if not compose_file.exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        return False
    
    try:
        content = compose_file.read_text(encoding='utf-8')
        original_content = content
        
        # Восстанавливаем версии для каждого сервиса
        for service_name, correct_image in CORRECT_VERSIONS.items():
            # Ищем строку с image для этого сервиса
            # Паттерн: service_name: ... image: неправильная_версия
            pattern = rf'({service_name}:[^\n]*\n(?:(?:[^\n]*\n)*?))(\s+image:\s*)([^\n]+)'
            
            def replace_image(match):
                service_block = match.group(1)
                image_prefix = match.group(2)
                old_image = match.group(3).strip()
                
                # Заменяем на правильную версию
                return service_block + image_prefix + correct_image
            
            content = re.sub(pattern, replace_image, content, flags=re.MULTILINE)
            
            # Также заменяем все вхождения неправильного образа
            # Ищем все упоминания образа для этого сервиса
            image_name = correct_image.split(':')[0]
            old_patterns = [
                rf'{image_name}:0\.1\.2',
                rf'{image_name}:base-0\.0\.21',
                rf'{image_name}:0\.0\.8',
                rf'{image_name}:v\d+\.\d+\.\d+',
            ]
            
            for old_pattern in old_patterns:
                content = re.sub(old_pattern, correct_image, content)
        
        # Проверяем, были ли изменения
        if content == original_content:
            console.print("[yellow]⚠️  Изменений не требуется - версии уже правильные[/yellow]")
            return True
        
        # Сохраняем изменения
        compose_file.write_text(content, encoding='utf-8')
        console.print("[green]✓ docker-compose.yml восстановлен[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка при восстановлении: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


def restore_versions_simple():
    """Простое восстановление - заменяет известные неправильные версии"""
    compose_file = Path("docker-compose.yml")
    
    if not compose_file.exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        return False
    
    try:
        content = compose_file.read_text(encoding='utf-8')
        original_content = content
        
        # Заменяем известные неправильные версии
        replacements = {
            'n8nio/n8n:0.1.2': 'n8nio/n8n:latest',
            'langflowai/langflow:base-0.0.21': 'langflowai/langflow:latest',
            'ghcr.io/supabase/postgres:0.0.8': 'ghcr.io/supabase/postgres:15.1.0.119',
            'ghcr.io/supabase/postgrest:0.0.8': 'ghcr.io/supabase/postgrest:v12.2.0',
            'ghcr.io/supabase/gotrue:0.0.8': 'ghcr.io/supabase/gotrue:v2.162.0',
            'ghcr.io/supabase/studio:0.0.8': 'ghcr.io/supabase/studio:20240513-d025e0f',
        }
        
        for wrong_version, correct_version in replacements.items():
            if wrong_version in content:
                content = content.replace(wrong_version, correct_version)
                console.print(f"[green]✓ Исправлено: {wrong_version} → {correct_version}[/green]")
        
        if content == original_content:
            console.print("[yellow]⚠️  Неправильных версий не найдено[/yellow]")
            return True
        
        compose_file.write_text(content, encoding='utf-8')
        console.print("[green]✓ docker-compose.yml восстановлен[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Ошибка при восстановлении: {e}[/red]")
        return False


def restart_services():
    """Перезапускает сервисы"""
    console.print("\n[cyan]🔄 Перезапуск сервисов...[/cyan]")
    
    try:
        # Останавливаем сервисы
        console.print("[yellow]⏳ Остановка сервисов...[/yellow]")
        subprocess.run(
            ["docker-compose", "down"],
            check=True,
            capture_output=True,
            timeout=60
        )
        
        # Запускаем заново
        console.print("[yellow]⏳ Запуск сервисов...[/yellow]")
        subprocess.run(
            ["docker-compose", "up", "-d"],
            check=True,
            capture_output=True,
            timeout=120
        )
        
        console.print("[green]✓ Сервисы перезапущены[/green]")
        return True
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при перезапуске: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        return False


def main():
    """Главная функция"""
    show_welcome()
    
    if not Confirm.ask("\n[cyan]Восстановить версии образов?[/cyan]", default=True):
        console.print("[yellow]Операция отменена[/yellow]")
        return
    
    # Восстанавливаем версии
    if restore_versions_simple():
        # Перезапускаем сервисы
        if Confirm.ask("\n[cyan]Перезапустить сервисы?[/cyan]", default=True):
            if restart_services():
                console.print("\n[green]✅ Версии восстановлены и сервисы перезапущены![/green]")
                console.print("[yellow]💡 Проверьте статус: docker-compose ps[/yellow]")
            else:
                console.print("\n[yellow]⚠️  Версии восстановлены, но перезапуск не удался[/yellow]")
                console.print("[yellow]💡 Попробуйте вручную: docker-compose up -d[/yellow]")
        else:
            console.print("\n[green]✅ Версии восстановлены![/green]")
            console.print("[yellow]💡 Запустите сервисы: docker-compose up -d[/yellow]")
    else:
        console.print("\n[red]❌ Не удалось восстановить версии[/red]")
        console.print("[yellow]💡 Проверьте docker-compose.yml вручную[/yellow]")


if __name__ == "__main__":
    main()

