#!/usr/bin/env python3
"""
Скрипт для автоматической настройки firewall (ufw)
Основано на подходе из проекта LISA
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def check_ufw_installed() -> bool:
    """Проверяет установлен ли ufw"""
    try:
        result = subprocess.run(
            ['which', 'ufw'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def run_command(cmd: list, description: str) -> bool:
    """Выполняет команду и выводит результат"""
    console.print(f"   🔧 Выполняю: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            if result.stdout:
                console.print(f"   [dim]{result.stdout.strip()}[/dim]")
            return True
        else:
            if result.stderr:
                console.print(f"   [yellow]⚠ {result.stderr.strip()}[/yellow]")
            return False
    except Exception as e:
        console.print(f"   [red]❌ Ошибка: {e}[/red]")
        return False


def setup_firewall() -> bool:
    """Настраивает firewall через ufw"""
    console.print("\n[cyan]🔒 Настройка firewall...[/cyan]")
    
    # Проверяем установлен ли ufw
    if not check_ufw_installed():
        console.print("[yellow]⚠ ufw не установлен[/yellow]")
        console.print("[cyan]💡 Установите ufw:[/cyan]")
        console.print("   [dim]sudo apt-get update && sudo apt-get install -y ufw[/dim]")
        return False
    
    # Проверяем права sudo
    try:
        result = subprocess.run(
            ['sudo', '-n', 'true'],
            capture_output=True,
            timeout=2
        )
        has_sudo = result.returncode == 0
    except Exception:
        has_sudo = False
    
    if not has_sudo:
        console.print("[yellow]⚠ Требуются права sudo для настройки firewall[/yellow]")
        console.print("[cyan]💡 Запустите скрипт с sudo или введите пароль при запросе[/cyan]")
    
    console.print("   Добавление правил firewall...")
    
    # Открываем порты
    ports = [
        ('22/tcp', 'SSH'),
        ('80/tcp', 'HTTP'),
        ('443/tcp', 'HTTPS')
    ]
    
    all_success = True
    for port, name in ports:
        success = run_command(
            ['sudo', 'ufw', 'allow', port],
            f"Открытие порта {port} ({name})"
        )
        if success:
            console.print(f"   ✅ {name} порт {port} разрешен")
        else:
            console.print(f"   ⚠ Не удалось открыть порт {port}")
            all_success = False
    
    # Включаем firewall
    console.print("\n   Включение firewall...")
    success = run_command(
        ['sudo', 'ufw', '--force', 'enable'],
        "Включение ufw"
    )
    
    if success:
        # Показываем статус
        console.print("\n   [cyan]Статус firewall:[/cyan]")
        result = subprocess.run(
            ['sudo', 'ufw', 'status'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            console.print(f"   [dim]{result.stdout.strip()}[/dim]")
        
        console.print("\n   [green]✅ Firewall настроен (порты 80, 443, 22 открыты)[/green]")
        return True
    else:
        console.print("\n   [yellow]⚠ Не удалось включить firewall[/yellow]")
        return False


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔥 Настройка Firewall (ufw)[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Откроет порты 22 (SSH), 80 (HTTP), 443 (HTTPS)")
    console.print("2. Включит firewall (ufw)")
    console.print("3. Покажет текущий статус firewall")
    
    console.print("\n[cyan]💡 Основано на подходе из проекта LISA[/cyan]")
    
    if not Confirm.ask("\n[cyan]Продолжить настройку firewall?[/cyan]", default=True):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    if setup_firewall():
        console.print("\n[bold green]✅ Настройка firewall завершена![/bold green]")
        console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
        console.print("1. Проверьте статус: sudo ufw status")
        console.print("2. Если нужно добавить другие порты: sudo ufw allow ПОРТ/ПРОТОКОЛ")
        console.print("3. Для просмотра логов: sudo ufw status verbose")
    else:
        console.print("\n[yellow]⚠ Настройка firewall не завершена[/yellow]")
        console.print("[cyan]💡 Проверьте права доступа и установку ufw[/cyan]")


if __name__ == "__main__":
    main()

