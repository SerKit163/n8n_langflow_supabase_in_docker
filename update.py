#!/usr/bin/env python3
"""
Скрипт обновления системы и сервисов
"""
import sys
import subprocess
import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))

from installer.version_checker import get_current_versions, check_updates
from installer.docker_manager import (
    docker_compose_down, docker_compose_pull, docker_compose_up,
    get_docker_compose_command
)
from installer.utils import ensure_dir

console = Console()


def show_welcome():
    """Приветственное сообщение"""
    welcome_text = """
🔄 Обновление n8n + Langflow + Supabase Stack

Этот скрипт поможет обновить ваши сервисы до последних версий.
"""
    console.print(Panel(welcome_text, title="Обновление системы", border_style="cyan"))


def create_backup():
    """Создает бэкап volumes"""
    console.print("\n[cyan]💾 Создание бэкапа...[/cyan]")
    
    backup_dir = ensure_dir("backups")
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"backup_{timestamp}"
    backup_path = backup_dir / backup_name
    
    try:
        # Создаем архив volumes
        cmd = ['tar', '-czf', str(backup_path) + '.tar.gz', 'volumes/']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            console.print(f"[green]✓ Бэкап создан: {backup_path}.tar.gz[/green]")
            return True
        else:
            console.print(f"[yellow]⚠ Не удалось создать бэкап: {result.stderr}[/yellow]")
            return False
    except Exception as e:
        console.print(f"[yellow]⚠ Ошибка при создании бэкапа: {e}[/yellow]")
        return False


def show_updates_table(updates: dict):
    """Показывает таблицу доступных обновлений"""
    if not updates:
        console.print("[green]✓ Все сервисы актуальны![/green]")
        return
    
    table = Table(title="📦 Доступные обновления")
    table.add_column("Сервис", style="cyan")
    table.add_column("Текущая версия", style="yellow")
    table.add_column("Последняя версия", style="green")
    table.add_column("Обновление", style="magenta")
    
    for service, info in updates.items():
        if info['has_update']:
            table.add_row(
                service.upper(),
                info['current'],
                info['latest'],
                "✓ Доступно"
            )
        else:
            table.add_row(
                service.upper(),
                info['current'],
                info['latest'],
                "— Актуально"
            )
    
    console.print(table)


def select_updates(updates: dict) -> dict:
    """Позволяет выбрать какие сервисы обновлять"""
    available_updates = {k: v for k, v in updates.items() if v['has_update']}
    
    if not available_updates:
        return {}
    
    selected = {}
    
    console.print("\n[cyan]Выберите сервисы для обновления:[/cyan]")
    for service, info in available_updates.items():
        if Confirm.ask(f"Обновить {service.upper()} ({info['current']} → {info['latest']})?", default=True):
            selected[service] = info
    
    return selected


def update_docker_compose(selected_updates: dict):
    """Обновляет версии в docker-compose.yml"""
    compose_file = Path("docker-compose.yml")
    
    if not compose_file.exists():
        console.print("[yellow]⚠ docker-compose.yml не найден[/yellow]")
        return False
    
    try:
        content = compose_file.read_text(encoding='utf-8')
        
        # Обновляем версии образов
        for service, info in selected_updates.items():
            image_name = info['image']
            old_version = info['current']
            new_version = info['latest']
            
            # Заменяем версию в образе
            old_image = f"{image_name}:{old_version}"
            new_image = f"{image_name}:{new_version}"
            content = content.replace(old_image, new_image)
            
            # Также заменяем если версия указана отдельно
            content = content.replace(f"{service}:{old_version}", f"{service}:{new_version}")
        
        compose_file.write_text(content, encoding='utf-8')
        console.print("[green]✓ docker-compose.yml обновлен[/green]")
        return True
    except Exception as e:
        console.print(f"[red]❌ Ошибка при обновлении docker-compose.yml: {e}[/red]")
        return False


def update_services(selected_updates: dict):
    """Обновляет выбранные сервисы"""
    if not selected_updates:
        console.print("[yellow]Нет сервисов для обновления[/yellow]")
        return
    
    console.print("\n[cyan]🔄 Обновление сервисов...[/cyan]")
    
    # 1. Останавливаем сервисы
    console.print("Остановка сервисов...")
    if not docker_compose_down():
        console.print("[yellow]⚠ Не удалось остановить сервисы[/yellow]")
        if not Confirm.ask("Продолжить?", default=False):
            return
    
    # 2. Обновляем docker-compose.yml
    if not update_docker_compose(selected_updates):
        console.print("[red]❌ Не удалось обновить конфигурацию[/red]")
        return
    
    # 3. Обновляем образы
    console.print("Обновление Docker образов...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Загрузка образов...", total=None)
        if docker_compose_pull():
            progress.update(task, completed=True)
            console.print("[green]✓ Образы обновлены[/green]")
        else:
            console.print("[red]❌ Ошибка при обновлении образов[/red]")
            return
    
    # 4. Запускаем сервисы
    console.print("Запуск обновленных сервисов...")
    if docker_compose_up():
        console.print("[green]✓ Сервисы обновлены и запущены![/green]")
    else:
        console.print("[red]❌ Ошибка при запуске сервисов[/red]")


def main():
    """Главная функция"""
    try:
        show_welcome()
        
        # Проверяем текущие версии
        console.print("\n[cyan]🔍 Проверка текущих версий...[/cyan]")
        current_versions = get_current_versions()
        
        if not current_versions:
            console.print("[yellow]⚠ Не удалось определить текущие версии[/yellow]")
            console.print("   Убедитесь что docker-compose.yml существует")
            sys.exit(1)
        
        console.print(f"[green]✓ Найдено сервисов: {len(current_versions)}[/green]")
        
        # Проверяем доступные обновления
        console.print("\n[cyan]🔍 Поиск обновлений...[/cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Проверка версий...", total=None)
            updates = check_updates(current_versions)
            progress.update(task, completed=True)
        
        # Показываем таблицу обновлений
        show_updates_table(updates)
        
        # Если нет обновлений
        available_updates = {k: v for k, v in updates.items() if v['has_update']}
        if not available_updates:
            console.print("\n[green]✓ Все сервисы актуальны![/green]")
            sys.exit(0)
        
        # Выбираем что обновлять
        selected = select_updates(updates)
        
        if not selected:
            console.print("\n[yellow]Обновление отменено[/yellow]")
            sys.exit(0)
        
        # Создаем бэкап
        if Confirm.ask("\nСоздать бэкап перед обновлением?", default=True):
            create_backup()
        
        # Подтверждение
        console.print(f"\n[cyan]Будет обновлено сервисов: {len(selected)}[/cyan]")
        if not Confirm.ask("Продолжить обновление?", default=True):
            console.print("[yellow]Обновление отменено[/yellow]")
            sys.exit(0)
        
        # Обновляем
        update_services(selected)
        
        console.print("\n[green]✓ Обновление завершено![/green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Обновление прервано пользователем[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Ошибка: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

