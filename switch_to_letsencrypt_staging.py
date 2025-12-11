#!/usr/bin/env python3
"""
Скрипт для переключения Caddy на Let's Encrypt Staging
Staging среда имеет более высокие лимиты для тестирования
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


def switch_to_staging():
    """Переключает Caddyfile на использование Let's Encrypt Staging"""
    caddyfile_path = get_project_root() / "Caddyfile"
    caddyfile_template_path = get_project_root() / "Caddyfile.template"
    
    target_file = caddyfile_template_path if caddyfile_template_path.exists() else caddyfile_path
    
    if not target_file.exists():
        console.print("[red]❌ Caddyfile не найден![/red]")
        return False
    
    content = target_file.read_text(encoding='utf-8')
    original_content = content
    
    console.print("[cyan]🔄 Переключение на Let's Encrypt Staging...[/cyan]")
    
    # Заменяем acme_ca на staging
    global_block_pattern = r'(\{\s*\n)(\s*email\s+\{[^}]+\}\s*\n?)(.*?)(\})'
    
    def add_staging(match):
        header = match.group(1)
        email_line = match.group(2)
        rest = match.group(3)
        footer = match.group(4)
        
        # Удаляем все старые acme_ca
        rest = re.sub(r'\s+acme_ca\s+[^\n]+\n?', '', rest)
        rest = re.sub(r'\s+# .*SSL.*?\n', '', rest, flags=re.MULTILINE)
        
        # Добавляем Let's Encrypt Staging
        staging_config = '    # Let\'s Encrypt Staging - более высокие лимиты для тестирования\n'
        staging_config += '    acme_ca https://acme-staging-v02.api.letsencrypt.org/directory\n'
        
        rest = staging_config + rest
        return f"{header}{email_line}{rest}{footer}"
    
    content = re.sub(global_block_pattern, add_staging, content, flags=re.DOTALL)
    
    if content != original_content:
        backup_path = target_file.with_suffix(target_file.suffix + '.backup')
        backup_path.write_text(original_content, encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        target_file.write_text(content, encoding='utf-8')
        console.print(f"[green]✓ {target_file.name} обновлен на Let's Encrypt Staging[/green]")
        return True
    else:
        console.print("[yellow]⚠ Изменений не требуется[/yellow]")
        return False


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Переключение на Let's Encrypt Staging[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Let's Encrypt Staging:[/yellow]")
    console.print("  ✓ Более высокие лимиты для тестирования")
    console.print("  ✓ Сертификаты не доверяются браузерами (для теста)")
    console.print("  ✓ Полезно для отладки конфигурации")
    
    console.print("\n[cyan]⚠ ВАЖНО:[/cyan]")
    console.print("  • Staging сертификаты НЕ доверяются браузерами")
    console.print("  • Используйте только для тестирования")
    console.print("  • Для продакшена используйте Buypass Go SSL или Let's Encrypt Production")
    
    if not Confirm.ask("\n[cyan]Переключить на Staging?[/cyan]", default=False):
        return
    
    if switch_to_staging():
        console.print("\n[bold green]✅ Переключение завершено![/bold green]")
        console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
        console.print("1. python3 regenerate_caddyfile.py")
        console.print("2. docker-compose restart caddy")
        console.print("3. docker-compose logs -f caddy")


if __name__ == "__main__":
    main()

