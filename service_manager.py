#!/usr/bin/env python3
"""
Скрипт для управления отдельными сервисами
Позволяет безопасно перезапускать, восстанавливать и проверять состояние сервисов
"""
import subprocess
import sys
import os
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

console = Console()

# Список доступных сервисов
SERVICES = {
    'n8n': {
        'name': 'n8n',
        'container': 'n8n',
        'description': 'N8N - автоматизация workflow',
        'volume': 'n8n_data',
        'health_endpoint': 'http://localhost:5678/healthz'
    },
    'langflow': {
        'name': 'langflow',
        'container': 'langflow',
        'description': 'Langflow - визуальный конструктор AI агентов',
        'volume': 'langflow_data',
        'health_endpoint': 'http://localhost:7860/health'
    },
    'supabase': {
        'name': 'supabase',
        'container': 'supabase-db',
        'description': 'Supabase - база данных PostgreSQL',
        'volume': 'supabase_data',
        'health_endpoint': None  # Проверяется через pg_isready
    },
    'supabase-studio': {
        'name': 'supabase-studio',
        'container': 'supabase-studio',
        'description': 'Supabase Studio - админ панель',
        'volume': None,
        'health_endpoint': 'http://localhost:3000'
    },
    'supabase-auth': {
        'name': 'supabase-auth',
        'container': 'supabase-auth',
        'description': 'Supabase Auth - сервис аутентификации',
        'volume': None,
        'health_endpoint': None
    },
    'supabase-rest': {
        'name': 'supabase-rest',
        'container': 'supabase-rest',
        'description': 'Supabase REST API',
        'volume': None,
        'health_endpoint': None
    },
    'ollama': {
        'name': 'ollama',
        'container': 'ollama',
        'description': 'Ollama - локальный LLM сервер',
        'volume': 'ollama_data',
        'health_endpoint': 'http://localhost:11434/api/tags'
    },
    'caddy': {
        'name': 'caddy',
        'container': 'caddy',
        'description': 'Caddy - reverse proxy и SSL',
        'volume': 'caddy_data',
        'health_endpoint': None
    }
}


def run_command(cmd: List[str], check: bool = True) -> tuple[int, str, str]:
    """Выполняет команду и возвращает код возврата, stdout и stderr"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def check_docker_compose() -> bool:
    """Проверяет наличие docker-compose.yml"""
    if not os.path.exists('docker-compose.yml'):
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        console.print("   Убедитесь, что вы находитесь в корневой директории проекта.")
        return False
    return True


def get_service_status(service_name: str) -> Dict:
    """Получает статус сервиса"""
    service_info = SERVICES.get(service_name)
    if not service_info:
        return {'exists': False}
    
    container_name = service_info['container']
    
    # Проверяем существует ли контейнер
    code, stdout, _ = run_command(
        ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}\t{{.Status}}\t{{.State}}'],
        check=False
    )
    
    if not stdout.strip():
        return {'exists': False, 'running': False}
    
    # Парсим статус
    parts = stdout.strip().split('\t')
    if len(parts) >= 3:
        status = parts[1]
        state = parts[2]
        running = state == 'running'
        
        # Проверяем здоровье
        health = 'unknown'
        if running:
            code_health, stdout_health, _ = run_command(
                ['docker', 'inspect', '--format', '{{.State.Health.Status}}', container_name],
                check=False
            )
            if code_health == 0 and stdout_health.strip():
                health = stdout_health.strip()
        
        return {
            'exists': True,
            'running': running,
            'status': status,
            'state': state,
            'health': health
        }
    
    return {'exists': False, 'running': False}


def show_all_services_status():
    """Показывает статус всех сервисов"""
    if not check_docker_compose():
        return
    
    table = Table(title="Статус сервисов", box=box.ROUNDED)
    table.add_column("Сервис", style="cyan", no_wrap=True)
    table.add_column("Контейнер", style="blue")
    table.add_column("Статус", justify="center")
    table.add_column("Здоровье", justify="center")
    table.add_column("Описание", style="dim")
    
    for service_key, service_info in SERVICES.items():
        status = get_service_status(service_key)
        
        if not status.get('exists'):
            status_text = "[dim]Не установлен[/dim]"
            health_text = "[dim]-[/dim]"
        else:
            if status.get('running'):
                status_text = "[green]● Запущен[/green]"
            else:
                status_text = "[red]● Остановлен[/red]"
            
            health = status.get('health', 'unknown')
            if health == 'healthy':
                health_text = "[green]✓ Здоров[/green]"
            elif health == 'unhealthy':
                health_text = "[red]✗ Не здоров[/red]"
            elif health == 'starting':
                health_text = "[yellow]⟳ Запускается[/yellow]"
            else:
                health_text = "[dim]-[/dim]"
        
        table.add_row(
            service_key,
            service_info['container'],
            status_text,
            health_text,
            service_info['description']
        )
    
    console.print()
    console.print(table)


def restart_service(service_name: str, force_recreate: bool = False):
    """Перезапускает сервис"""
    if not check_docker_compose():
        return False
    
    service_info = SERVICES.get(service_name)
    if not service_info:
        console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        return False
    
    container_name = service_info['container']
    
    console.print(f"\n[yellow]🔄 {'Пересоздание' if force_recreate else 'Перезапуск'} сервиса {service_name}...[/yellow]")
    
    if force_recreate:
        # Останавливаем и удаляем контейнер (данные сохраняются в volume)
        console.print(f"[dim]Останавливаем контейнер {container_name}...[/dim]")
        run_command(['docker-compose', 'stop', service_name], check=False)
        run_command(['docker-compose', 'rm', '-f', service_name], check=False)
        
        # Пересоздаем контейнер
        console.print(f"[dim]Пересоздаем контейнер {container_name}...[/dim]")
        code, stdout, stderr = run_command(['docker-compose', 'up', '-d', '--no-deps', service_name], check=False)
    else:
        # Просто перезапускаем
        code, stdout, stderr = run_command(['docker-compose', 'restart', service_name], check=False)
    
    if code == 0:
        console.print(f"[green]✓ Сервис {service_name} успешно {'пересоздан' if force_recreate else 'перезапущен'}![/green]")
        
        # Показываем логи
        if Confirm.ask(f"\nПоказать логи сервиса {service_name}?", default=True):
            show_service_logs(service_name, tail=50)
        
        return True
    else:
        console.print(f"[red]❌ Ошибка при {'пересоздании' if force_recreate else 'перезапуске'} сервиса![/red]")
        if stderr:
            console.print(f"[red]{stderr}[/red]")
        return False


def show_service_logs(service_name: str, tail: int = 100, follow: bool = False):
    """Показывает логи сервиса"""
    if not check_docker_compose():
        return
    
    service_info = SERVICES.get(service_name)
    if not service_info:
        console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        return
    
    container_name = service_info['container']
    
    cmd = ['docker-compose', 'logs']
    if tail:
        cmd.extend(['--tail', str(tail)])
    if follow:
        cmd.append('-f')
    cmd.append(service_name)
    
    console.print(f"\n[cyan]📋 Логи сервиса {service_name}:[/cyan]")
    console.print(Panel("", border_style="cyan"))
    
    # Запускаем команду без перехвата вывода для live просмотра
    if follow:
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            console.print("\n[yellow]Просмотр логов прерван[/yellow]")
    else:
        code, stdout, stderr = run_command(cmd, check=False)
        if stdout:
            console.print(stdout)
        if stderr:
            console.print(f"[red]{stderr}[/red]")


def check_service_health(service_name: str) -> bool:
    """Проверяет здоровье сервиса"""
    service_info = SERVICES.get(service_name)
    if not service_info:
        return False
    
    status = get_service_status(service_name)
    if not status.get('running'):
        console.print(f"[red]❌ Сервис {service_name} не запущен![/red]")
        return False
    
    health = status.get('health', 'unknown')
    if health == 'healthy':
        console.print(f"[green]✓ Сервис {service_name} здоров![/green]")
        return True
    elif health == 'unhealthy':
        console.print(f"[red]❌ Сервис {service_name} не здоров![/red]")
        return False
    else:
        console.print(f"[yellow]⚠ Статус здоровья сервиса {service_name} неизвестен[/yellow]")
        return False


def fix_service(service_name: str):
    """Восстанавливает проблемный сервис"""
    if not check_docker_compose():
        return False
    
    service_info = SERVICES.get(service_name)
    if not service_info:
        console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        return False
    
    console.print(f"\n[yellow]🔧 Восстановление сервиса {service_name}...[/yellow]")
    
    # Показываем текущий статус
    status = get_service_status(service_name)
    console.print(f"\n[cyan]Текущий статус:[/cyan]")
    if status.get('running'):
        console.print(f"  Состояние: [green]Запущен[/green]")
    else:
        console.print(f"  Состояние: [red]Остановлен[/red]")
    
    if status.get('health'):
        health = status['health']
        if health == 'healthy':
            console.print(f"  Здоровье: [green]Здоров[/green]")
        elif health == 'unhealthy':
            console.print(f"  Здоровье: [red]Не здоров[/red]")
        else:
            console.print(f"  Здоровье: [yellow]{health}[/yellow]")
    
    # Показываем последние логи
    console.print(f"\n[cyan]Последние ошибки из логов:[/cyan]")
    code, stdout, stderr = run_command(
        ['docker-compose', 'logs', '--tail', '30', service_name],
        check=False
    )
    if stdout:
        # Показываем только строки с ошибками
        error_lines = [line for line in stdout.split('\n') if 'error' in line.lower() or 'fatal' in line.lower() or 'exception' in line.lower()]
        if error_lines:
            for line in error_lines[-10:]:  # Последние 10 ошибок
                console.print(f"  [red]{line}[/red]")
        else:
            console.print("  [dim]Ошибок в последних логах не найдено[/dim]")
    
    # Предлагаем варианты восстановления
    console.print(f"\n[cyan]Варианты восстановления:[/cyan]")
    console.print("  1. Перезапустить сервис (быстро)")
    console.print("  2. Пересоздать контейнер (сохраняя данные)")
    console.print("  3. Показать полные логи")
    console.print("  4. Отмена")
    
    choice = Prompt.ask("\nВыберите действие", choices=["1", "2", "3", "4"], default="1")
    
    if choice == "1":
        return restart_service(service_name, force_recreate=False)
    elif choice == "2":
        if Confirm.ask("\n⚠ Пересоздание контейнера остановит сервис на несколько секунд. Продолжить?", default=True):
            return restart_service(service_name, force_recreate=True)
        return False
    elif choice == "3":
        show_service_logs(service_name, tail=200, follow=False)
        if Confirm.ask("\nПопробовать восстановить сервис?", default=True):
            return fix_service(service_name)  # Рекурсивно вызываем снова
        return False
    else:
        console.print("[yellow]Отменено[/yellow]")
        return False


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]Менеджер сервисов[/bold cyan]\n\n"
        "Управление отдельными сервисами Docker Compose\n"
        "Все данные сохраняются в Docker volumes",
        border_style="cyan"
    ))
    
    if not check_docker_compose():
        sys.exit(1)
    
    while True:
        console.print("\n[bold]Доступные действия:[/bold]")
        console.print("  1. Показать статус всех сервисов")
        console.print("  2. Перезапустить сервис")
        console.print("  3. Пересоздать сервис (с сохранением данных)")
        console.print("  4. Показать логи сервиса")
        console.print("  5. Проверить здоровье сервиса")
        console.print("  6. Восстановить проблемный сервис")
        console.print("  7. Выход")
        
        choice = Prompt.ask("\nВыберите действие", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
        
        if choice == "1":
            show_all_services_status()
        
        elif choice == "2":
            show_all_services_status()
            service_name = Prompt.ask("\nВведите имя сервиса для перезапуска")
            if service_name in SERVICES:
                restart_service(service_name, force_recreate=False)
            else:
                console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        
        elif choice == "3":
            show_all_services_status()
            service_name = Prompt.ask("\nВведите имя сервиса для пересоздания")
            if service_name in SERVICES:
                if Confirm.ask(f"\n⚠ Пересоздание контейнера {service_name} остановит сервис на несколько секунд. Продолжить?", default=True):
                    restart_service(service_name, force_recreate=True)
            else:
                console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        
        elif choice == "4":
            show_all_services_status()
            service_name = Prompt.ask("\nВведите имя сервиса для просмотра логов")
            if service_name in SERVICES:
                tail = Prompt.ask("Количество последних строк", default="100")
                try:
                    tail = int(tail)
                except ValueError:
                    tail = 100
                follow = Confirm.ask("Следить за логами в реальном времени?", default=False)
                show_service_logs(service_name, tail=tail, follow=follow)
            else:
                console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        
        elif choice == "5":
            show_all_services_status()
            service_name = Prompt.ask("\nВведите имя сервиса для проверки здоровья")
            if service_name in SERVICES:
                check_service_health(service_name)
            else:
                console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        
        elif choice == "6":
            show_all_services_status()
            service_name = Prompt.ask("\nВведите имя проблемного сервиса")
            if service_name in SERVICES:
                fix_service(service_name)
            else:
                console.print(f"[red]❌ Сервис '{service_name}' не найден![/red]")
        
        elif choice == "7":
            console.print("[green]До свидания![/green]")
            break
        
        if choice != "7":
            if not Confirm.ask("\nПродолжить работу с менеджером?", default=True):
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Прервано пользователем[/yellow]")
        sys.exit(0)

