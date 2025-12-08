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
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Запуск сервисов...", total=None)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            progress.update(task, completed=True)
        
        if result.returncode != 0:
            console.print(f"[red]Ошибка при запуске:[/red]\n{result.stderr}")
            return False
        
        return True
    except subprocess.TimeoutExpired:
        console.print("[red]Таймаут при запуске сервисов[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
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

