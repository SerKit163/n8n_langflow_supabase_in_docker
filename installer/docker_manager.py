"""
Модуль управления Docker
"""
import subprocess
import sys
from typing import Optional, Dict, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def check_docker() -> bool:
    """Проверяет установлен ли Docker"""
    try:
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_docker_compose() -> bool:
    """Проверяет установлен ли Docker Compose"""
    try:
        # Пробуем docker compose (v2)
        result = subprocess.run(
            ['docker', 'compose', 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
        
        # Пробуем docker-compose (v1)
        result = subprocess.run(
            ['docker-compose', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_docker_version() -> Optional[str]:
    """Получает версию Docker"""
    try:
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_docker_compose_version() -> Optional[str]:
    """Получает версию Docker Compose"""
    try:
        # Пробуем docker compose (v2)
        result = subprocess.run(
            ['docker', 'compose', 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Пробуем docker-compose (v1)
        result = subprocess.run(
            ['docker-compose', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def is_docker_running() -> bool:
    """Проверяет запущен ли Docker daemon"""
    try:
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def docker_compose_up(detach: bool = True, file: Optional[str] = None) -> bool:
    """
    Запускает docker compose up
    
    Args:
        detach: Запустить в фоновом режиме
        file: Путь к docker-compose.yml файлу
    """
    cmd = get_docker_compose_command()
    
    if file:
        cmd.extend(['-f', file])
    
    cmd.append('up')
    
    if detach:
        cmd.append('-d')
    
    try:
        console.print("[cyan]Запуск Docker Compose...[/cyan]")
        console.print(f"[dim]Команда: {' '.join(cmd)}[/dim]\n")
        
        # Запускаем команду
        # Для detach режима используем capture_output для быстрого завершения
        # Для не-detach показываем вывод напрямую
        if detach:
            # В detach режиме команда должна завершиться быстро
            # Показываем прогресс через спиннер, но не блокируем вывод
            console.print("[dim]Загрузка образов и запуск контейнеров...[/dim]")
            console.print("[dim]Это может занять несколько минут при первой установке[/dim]\n")
            
            # Запускаем команду с выводом в реальном времени
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Показываем важные строки вывода
            important_keywords = ['pulling', 'creating', 'starting', 'started', 'error', 'failed', 'warning']
            output_buffer = []
            
            try:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        output_buffer.append(line)
                        # Показываем только важные строки
                        if any(keyword in line.lower() for keyword in important_keywords):
                            console.print(f"[dim]{line}[/dim]")
                
                # Ждем завершения процесса
                return_code = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                process.kill()
                console.print("[red]❌ Таймаут при запуске сервисов (более 10 минут)[/red]")
                return False
            
            if return_code != 0:
                console.print(f"[red]❌ Ошибка при запуске сервисов (код: {return_code})[/red]")
                # Показываем последние строки вывода
                if output_buffer:
                    console.print(f"[yellow]Последние строки вывода:[/yellow]")
                    for line in output_buffer[-10:]:
                        console.print(f"[dim]{line}[/dim]")
                console.print(f"\n[yellow]💡 Попробуйте запустить вручную:[/yellow]")
                console.print(f"[dim]{' '.join(cmd)}[/dim]")
                return False
            
            console.print("[green]✓ Сервисы запущены[/green]")
            
            # Даем время контейнерам запуститься
            import time
            time.sleep(2)
            
            # Проверяем статус
            status_cmd = get_docker_compose_command()
            if file:
                status_cmd.extend(['-f', file])
            status_cmd.extend(['ps'])
            
            try:
                status_result = subprocess.run(
                    status_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if status_result.returncode == 0 and status_result.stdout.strip():
                    console.print("\n[cyan]Статус контейнеров:[/cyan]")
                    console.print(status_result.stdout)
            except Exception:
                pass  # Игнорируем ошибки проверки статуса
        else:
            # Для не-detach режима показываем вывод напрямую
            result = subprocess.run(
                cmd,
                timeout=600
            )
            return result.returncode == 0
        
        return True
    except subprocess.TimeoutExpired:
        console.print("[red]❌ Таймаут при запуске сервисов (более 10 минут)[/red]")
        console.print("[yellow]💡 Возможно, образы загружаются слишком долго[/yellow]")
        console.print("[yellow]💡 Попробуйте запустить вручную: docker-compose up -d[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


def docker_compose_down(file: Optional[str] = None) -> bool:
    """Останавливает сервисы"""
    cmd = get_docker_compose_command()
    
    if file:
        cmd.extend(['-f', file])
    
    cmd.append('down')
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        return False


def docker_compose_pull(file: Optional[str] = None) -> bool:
    """Обновляет образы"""
    cmd = get_docker_compose_command()
    
    if file:
        cmd.extend(['-f', file])
    
    cmd.append('pull')
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Обновление образов...", total=None)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            progress.update(task, completed=True)
        
        return result.returncode == 0
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        return False


def get_docker_compose_command() -> List[str]:
    """Возвращает команду для docker compose"""
    # Пробуем docker compose (v2)
    try:
        result = subprocess.run(
            ['docker', 'compose', 'version'],
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            return ['docker', 'compose']
    except Exception:
        pass
    
    # Используем docker-compose (v1)
    return ['docker-compose']


def check_service_health(service_name: str, timeout: int = 30) -> bool:
    """Проверяет здоровье сервиса"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', f'name={service_name}', '--format', '{{.Status}}'],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            return 'Up' in status or 'healthy' in status.lower()
        
        return False
    except Exception:
        return False


def get_running_services() -> List[str]:
    """Возвращает список запущенных сервисов"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
        
        return []
    except Exception:
        return []

