"""
Модуль управления Docker
"""
import subprocess
import sys
import re
from typing import Optional, Dict, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, TaskID

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
            
            # Определяем образы из docker-compose.yml
            images_to_track = {}
            try:
                if file:
                    compose_file = file
                else:
                    compose_file = "docker-compose.yml"
                
                with open(compose_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Ищем образы
                    if 'n8nio/n8n' in content or 'n8n' in content.lower():
                        images_to_track['n8n'] = {'status': 'waiting', 'task_id': None}
                    if 'langflowai/langflow' in content or 'langflow' in content.lower():
                        images_to_track['langflow'] = {'status': 'waiting', 'task_id': None}
                    if 'supabase' in content.lower():
                        images_to_track['supabase'] = {'status': 'waiting', 'task_id': None}
                    if 'ollama' in content.lower():
                        images_to_track['ollama'] = {'status': 'waiting', 'task_id': None}
            except Exception:
                # Если не удалось прочитать файл, используем стандартный набор
                images_to_track = {
                    'n8n': {'status': 'waiting', 'task_id': None},
                    'langflow': {'status': 'waiting', 'task_id': None},
                    'supabase': {'status': 'waiting', 'task_id': None}
                }
            
            pull_output = []
            current_image_name = None
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=False
            ) as progress:
                # Создаем задачи для каждого образа
                for img_name in images_to_track.keys():
                    task_id = progress.add_task(
                        f"[dim]{img_name.capitalize()}: ожидание...[/dim]",
                        total=None
                    )
                    images_to_track[img_name]['task_id'] = task_id
                
                try:
                    for line in pull_process.stdout:
                        line = line.rstrip()
                        if not line:
                            continue
                        
                        pull_output.append(line)
                        line_lower = line.lower()
                        
                        # Определяем, какой образ загружается - улучшенный парсинг
                        detected_image = None
                        
                        # Паттерн 1: "Pulling n8n ..." или "Pulling langflow ..." (имя сервиса)
                        service_match = re.search(r'pulling\s+([a-z-]+)', line_lower)
                        if service_match:
                            service_name = service_match.group(1)
                            # Проверяем соответствие с отслеживаемыми образами
                            for img_name in images_to_track.keys():
                                if service_name == img_name or service_name.replace('-', '') == img_name.replace('-', ''):
                                    detected_image = img_name
                                    break
                        
                        # Паттерн 2: полное имя образа в строке (n8nio/n8n, langflowai/langflow и т.д.)
                        if not detected_image:
                            if 'n8nio/n8n' in line_lower or 'n8nio/n8n:' in line:
                                detected_image = 'n8n'
                            elif 'langflowai/langflow' in line_lower or 'langflowai/langflow:' in line:
                                detected_image = 'langflow'
                            elif 'supabase/postgres' in line_lower or 'supabase/postgres:' in line:
                                detected_image = 'supabase'
                            elif 'supabase/studio' in line_lower or 'supabase/studio:' in line:
                                detected_image = 'supabase'
                            elif 'ollama/ollama' in line_lower or 'ollama/ollama:' in line:
                                detected_image = 'ollama'
                        
                        # Паттерн 3: по ключевым словам в контексте загрузки
                        if not detected_image:
                            if ('n8n' in line_lower and ('pulling' in line_lower or 'image' in line_lower)) and 'n8nio' not in line_lower:
                                # Проверяем, что это не ложное срабатывание
                                if 'supabase' not in line_lower:
                                    detected_image = 'n8n'
                            elif ('langflow' in line_lower and ('pulling' in line_lower or 'image' in line_lower)) and 'langflowai' not in line_lower:
                                detected_image = 'langflow'
                            elif ('supabase' in line_lower and ('pulling' in line_lower or 'image' in line_lower)):
                                detected_image = 'supabase'
                            elif ('ollama' in line_lower and ('pulling' in line_lower or 'image' in line_lower)):
                                detected_image = 'ollama'
                        
                        # Обновляем текущий образ, если обнаружен
                        if detected_image and detected_image in images_to_track:
                            if current_image_name != detected_image:
                                current_image_name = detected_image
                                task_id = images_to_track[detected_image]['task_id']
                                images_to_track[detected_image]['status'] = 'pulling'
                                progress.update(
                                    task_id,
                                    description=f"[cyan]{detected_image.capitalize()}: загрузка...[/cyan]"
                                )
                        
                        # Обновляем статус текущего образа
                        if current_image_name and current_image_name in images_to_track:
                            task_id = images_to_track[current_image_name]['task_id']
                            
                            # Определяем этап загрузки
                            if 'downloading' in line_lower or 'pulling' in line_lower:
                                progress.update(
                                    task_id,
                                    description=f"[cyan]{current_image_name.capitalize()}: скачивание...[/cyan]"
                                )
                            elif 'extracting' in line_lower:
                                progress.update(
                                    task_id,
                                    description=f"[yellow]{current_image_name.capitalize()}: распаковка...[/yellow]"
                                )
                            elif 'verifying' in line_lower or 'verifying checksum' in line_lower:
                                progress.update(
                                    task_id,
                                    description=f"[yellow]{current_image_name.capitalize()}: проверка...[/yellow]"
                                )
                            elif 'pull complete' in line_lower or 'already exists' in line_lower or 'up to date' in line_lower:
                                progress.update(
                                    task_id,
                                    description=f"[green]✓ {current_image_name.capitalize()}: загружен[/green]"
                                )
                                images_to_track[current_image_name]['status'] = 'complete'
                                current_image_name = None
                            elif 'error' in line_lower or 'failed' in line_lower:
                                progress.update(
                                    task_id,
                                    description=f"[red]❌ {current_image_name.capitalize()}: ошибка[/red]"
                                )
                                images_to_track[current_image_name]['status'] = 'error'
                    
                    pull_return_code = pull_process.wait(timeout=600)
                    
                    # Обновляем все задачи на завершенные
                    if pull_return_code == 0:
                        for img_name, info in images_to_track.items():
                            if info['status'] != 'complete':
                                progress.update(
                                    info['task_id'],
                                    description=f"[green]✓ {img_name.capitalize()}: готов[/green]"
                                )
                except subprocess.TimeoutExpired:
                    pull_process.kill()
                    for img_name, info in images_to_track.items():
                        if info['status'] != 'complete':
                            progress.update(
                                info['task_id'],
                                description=f"[red]❌ {img_name.capitalize()}: таймаут[/red]"
                            )
                    console.print("\n[red]❌ Таймаут при загрузке образов (более 10 минут)[/red]")
                    return False
            
            if pull_return_code != 0:
                console.print(f"\n[red]❌ Ошибка при загрузке образов (код: {pull_return_code})[/red]")
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
            
            # Запускаем up с динамическим прогрессом
            up_process = subprocess.Popen(
                up_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            up_output = []
            current_container = None
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=False
            ) as progress:
                task = progress.add_task(
                    "[cyan]Запуск контейнеров...[/cyan]",
                    total=None
                )
                
                try:
                    for line in up_process.stdout:
                        line = line.rstrip()
                        if not line:
                            continue
                        
                        up_output.append(line)
                        line_lower = line.lower()
                        
                        # Определяем текущий контейнер
                        if 'creating' in line_lower:
                            match = re.search(r'creating[^\s]*\s+([^\s]+)', line_lower)
                            if match:
                                current_container = match.group(1)
                                progress.update(task, description=f"[cyan]Создание {current_container}...[/cyan]")
                        elif 'starting' in line_lower:
                            if current_container:
                                progress.update(task, description=f"[cyan]Запуск {current_container}...[/cyan]")
                        elif 'started' in line_lower:
                            if current_container:
                                progress.update(task, description=f"[green]✓ {current_container} запущен[/green]")
                                current_container = None
                        elif 'error' in line_lower or 'failed' in line_lower:
                            progress.update(task, description=f"[red]❌ Ошибка: {line[:50]}[/red]")
                    
                    up_return_code = up_process.wait(timeout=120)
                    
                    if up_return_code == 0:
                        progress.update(task, description="[green]✓ Все контейнеры запущены[/green]")
                except subprocess.TimeoutExpired:
                    up_process.kill()
                    progress.update(task, description="[red]❌ Таймаут при запуске[/red]")
                    console.print("\n[red]❌ Таймаут при запуске контейнеров[/red]")
                    return False
            
            if up_return_code != 0:
                console.print(f"\n[red]❌ Ошибка при запуске контейнеров (код: {up_return_code})[/red]")
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

