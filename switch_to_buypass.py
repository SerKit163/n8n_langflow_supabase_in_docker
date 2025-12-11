#!/usr/bin/env python3
"""
Скрипт для переключения Caddy на Buypass Go SSL
Buypass Go SSL - бесплатный CA без регистрации, работает из коробки
"""
import os
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def get_project_root() -> Path:
    """Возвращает корневую директорию проекта"""
    return Path(__file__).parent


def switch_caddyfile_to_buypass():
    """Переключает Caddyfile на использование Buypass Go SSL"""
    caddyfile_path = get_project_root() / "Caddyfile"
    caddyfile_template_path = get_project_root() / "Caddyfile.template"
    
    # Проверяем наличие файлов
    if not caddyfile_path.exists() and not caddyfile_template_path.exists():
        console.print("[red]❌ Caddyfile или Caddyfile.template не найдены![/red]")
        return False
    
    # Работаем с шаблоном (основной файл)
    target_file = caddyfile_template_path if caddyfile_template_path.exists() else caddyfile_path
    
    content = target_file.read_text(encoding='utf-8')
    original_content = content
    
    console.print("[cyan]🔄 Переключение на Buypass Go SSL...[/cyan]")
    
    # Заменяем или добавляем acme_ca для Buypass Go SSL
    global_block_pattern = r'(\{\s*\n)(\s*email\s+\{[^}]+\}\s*\n?)(.*?)(\})'
    
    def add_buypass(match):
        header = match.group(1)
        email_line = match.group(2)
        rest = match.group(3)
        footer = match.group(4)
        
        # Удаляем все старые acme_ca
        rest = re.sub(r'\s+acme_ca\s+[^\n]+\n?', '', rest)
        rest = re.sub(r'\s+# ZeroSSL.*?\n', '', rest, flags=re.MULTILINE)
        rest = re.sub(r'\s+# Переключено на.*?\n', '', rest, flags=re.MULTILINE)
        
        # Добавляем Buypass Go SSL
        buypass_config = '    # Buypass Go SSL - бесплатный CA без регистрации\n'
        buypass_config += '    acme_ca https://api.buypass.com/acme/directory\n'
        
        rest = buypass_config + rest
        return f"{header}{email_line}{rest}{footer}"
    
    content = re.sub(global_block_pattern, add_buypass, content, flags=re.DOTALL)
    
    if content != original_content:
        backup_path = target_file.with_suffix(target_file.suffix + '.backup')
        backup_path.write_text(original_content, encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        target_file.write_text(content, encoding='utf-8')
        console.print(f"[green]✓ {target_file.name} обновлен на Buypass Go SSL[/green]")
        return True
    else:
        console.print("[yellow]⚠ Изменений не требуется[/yellow]")
        return False


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Переключение на Buypass Go SSL[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Buypass Go SSL - бесплатный CA:[/yellow]")
    console.print("  ✓ БЕЗ регистрации - работает из коробки")
    console.print("  ✓ БЕЗ pre-registration callback")
    console.print("  ✓ Бесплатные SSL сертификаты")
    console.print("  ✓ Поддерживается Caddy автоматически")
    
    if not Confirm.ask("\n[cyan]Переключить Caddy на Buypass Go SSL?[/cyan]", default=True):
        return
    
    if switch_caddyfile_to_buypass():
        console.print("\n[bold green]✅ Переключение завершено![/bold green]")
        console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
        console.print("1. python3 regenerate_caddyfile.py")
        console.print("2. docker-compose restart caddy")
        console.print("3. docker-compose logs -f caddy")


if __name__ == "__main__":
    main()

