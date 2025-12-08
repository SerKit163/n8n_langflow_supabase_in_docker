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
    
    try:
        if detach:
            # ЭТАП 1: Загрузка образов с детальным прогрессом
            console.print("[cyan]📥 Загрузка образов Docker...[/cyan]")
            console.print("[dim]Это может занять несколько минут при первой установке[/dim]\n")
            
            pull_cmd = get_docker_compose_command()
            if file:
                pull_cmd.extend(['-f', file])
            pull_cmd.append('pull')
            
            # Запускаем pull с выводом в реальном времени
            pull_process = subprocess.Popen(
                pull_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Показываем весь вывод pull с прогрессом
            pull_output = []
            try:
                for line in pull_process.stdout:
                    line = line.rstrip()
                    if line:
                        pull_output.append(line)
                        # Показываем все строки с прогрессом загрузки
                        if any(keyword in line.lower() for keyword in ['pulling', 'downloading', 'extracting', 'pull complete', 'already exists', 'error', 'failed', 'waiting', 'verifying']):
                            console.print(f"[dim]{line}[/dim]")
                        # Показываем прогресс слоев (проценты, размеры)
                        elif '%' in line or 'mb' in line.lower() or 'kb' in line.lower() or 'gb' in line.lower():
                            console.print(f"[dim]{line}[/dim]")
                        # Показываем статусы слоев
                        elif 'layer' in line.lower() or 'digest:' in line.lower() or 'status:' in line.lower():
                            console.print(f"[dim]{line}[/dim]")
                
                pull_return_code = pull_process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                pull_process.kill()
                console.print("[red]❌ Таймаут при загрузке образов (более 10 минут)[/red]")
                return False
            
            if pull_return_code != 0:
                console.print(f"[red]❌ Ошибка при загрузке образов (код: {pull_return_code})[/red]")
                if pull_output:
                    console.print(f"[yellow]Последние строки вывода:[/yellow]")
                    for line in pull_output[-10:]:
                        console.print(f"[dim]{line}[/dim]")
                return False
            
            console.print("[green]✓ Образы загружены[/green]\n")
            
            # ЭТАП 2: Запуск контейнеров
            console.print("[cyan]🚀 Запуск контейнеров...[/cyan]\n")
            
            up_cmd = get_docker_compose_command()
            if file:
                up_cmd.extend(['-f', file])
            up_cmd.extend(['up', '-d'])
            
            # Запускаем up с выводом
            up_process = subprocess.Popen(
                up_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            up_output = []
            try:
                for line in up_process.stdout:
                    line = line.rstrip()
                    if line:
                        up_output.append(line)
                        # Показываем важные строки запуска
                        if any(keyword in line.lower() for keyword in ['creating', 'starting', 'started', 'error', 'failed', 'warning', 'container']):
                            console.print(f"[dim]{line}[/dim]")
                
                up_return_code = up_process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                up_process.kill()
                console.print("[red]❌ Таймаут при запуске контейнеров[/red]")
                return False
            
            if up_return_code != 0:
                console.print(f"[red]❌ Ошибка при запуске контейнеров (код: {up_return_code})[/red]")
                if up_output:
                    console.print(f"[yellow]Последние строки вывода:[/yellow]")
                    for line in up_output[-10:]:
                        console.print(f"[dim]{line}[/dim]")
                console.print(f"\n[yellow]💡 Попробуйте запустить вручную:[/yellow]")
                console.print(f"[dim]{' '.join(up_cmd)}[/dim]")
                return False
            
            console.print("[green]✓ Контейнеры запущены[/green]")
            
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

