#!/usr/bin/env python3
"""
Комплексный скрипт диагностики и автоматического восстановления системы
"""
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import dotenv_values

console = Console()


class SystemDiagnostics:
    """Класс для диагностики и восстановления системы"""
    
    def __init__(self):
        self.console = Console()
        self.env_config = {}
        self.issues = []
        self.fixes_applied = []
        
    def load_config(self):
        """Загружает конфигурацию из .env"""
        env_path = Path(".env")
        if env_path.exists():
            self.env_config = dotenv_values(env_path)
        else:
            self.console.print("[red]❌ Файл .env не найден![/red]")
            return False
        return True
    
    def check_docker_compose(self) -> bool:
        """Проверяет наличие docker-compose.yml"""
        if not Path("docker-compose.yml").exists():
            self.console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
            return False
        return True
    
    def run_command(self, cmd: List[str], timeout: int = 30, capture: bool = True) -> Tuple[bool, str, str]:
        """Выполняет команду и возвращает результат"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Timeout expired"
        except Exception as e:
            return False, "", str(e)
    
    def check_service_status(self, service_name: str) -> Dict:
        """Проверяет статус сервиса"""
        success, stdout, stderr = self.run_command(
            ["docker-compose", "ps", service_name],
            timeout=10
        )
        
        status = {
            'name': service_name,
            'running': False,
            'healthy': False,
            'restarts': 0,
            'status': 'unknown',
            'error': None
        }
        
        if success and stdout:
            if 'Up' in stdout:
                status['running'] = True
                if 'healthy' in stdout:
                    status['healthy'] = True
                elif 'unhealthy' in stdout:
                    status['healthy'] = False
                # Подсчитываем перезапуски
                if 'Restarting' in stdout:
                    status['restarts'] = stdout.count('Restarting')
            elif 'Exit' in stdout:
                status['status'] = 'exited'
        
        return status
    
    def check_all_services(self) -> Dict[str, Dict]:
        """Проверяет статус всех сервисов"""
        self.console.print("\n[cyan]🔍 Проверка статуса сервисов...[/cyan]")
        
        services = ['n8n', 'langflow', 'supabase-db', 'supabase-auth', 
                   'supabase-rest', 'supabase-studio', 'caddy']
        
        statuses = {}
        for service in services:
            status = self.check_service_status(service)
            statuses[service] = status
            
            if status['running']:
                if status['healthy']:
                    self.console.print(f"  [green]✓[/green] {service}: работает")
                else:
                    self.console.print(f"  [yellow]⚠[/yellow] {service}: запущен, но нездоров")
                    self.issues.append(f"{service}: контейнер запущен, но нездоров")
            else:
                self.console.print(f"  [red]✗[/red] {service}: не запущен")
                self.issues.append(f"{service}: контейнер не запущен")
        
        return statuses
    
    def check_database_connection(self) -> bool:
        """Проверяет подключение к базе данных"""
        self.console.print("\n[cyan]🔍 Проверка подключения к базе данных...[/cyan]")
        
        postgres_password = self.env_config.get('POSTGRES_PASSWORD', '')
        if not postgres_password:
            self.console.print("[red]❌ POSTGRES_PASSWORD не найден в .env[/red]")
            self.issues.append("База данных: POSTGRES_PASSWORD не настроен")
            return False
        
        success, stdout, stderr = self.run_command(
            [
                "docker", "exec", "supabase-db",
                "psql", "-U", "postgres", "-d", "postgres", "-c", "SELECT 1;"
            ],
            timeout=10
        )
        
        if success:
            self.console.print("[green]✓ Подключение к базе данных работает[/green]")
            return True
        else:
            self.console.print("[red]❌ Не удалось подключиться к базе данных[/red]")
            self.issues.append("База данных: нет подключения")
            return False
    
    def check_auth_schema(self) -> bool:
        """Проверяет наличие схемы auth"""
        self.console.print("\n[cyan]🔍 Проверка схемы auth...[/cyan]")
        
        success, stdout, stderr = self.run_command(
            [
                "docker", "exec", "supabase-db",
                "psql", "-U", "postgres", "-d", "postgres", "-c",
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth');"
            ],
            timeout=10
        )
        
        if success and 't' in stdout.lower():
            self.console.print("[green]✓ Схема auth существует[/green]")
            return True
        else:
            self.console.print("[red]❌ Схема auth не найдена[/red]")
            self.issues.append("База данных: схема auth отсутствует")
            return False
    
    def check_factor_type(self) -> bool:
        """Проверяет наличие типа factor_type"""
        self.console.print("\n[cyan]🔍 Проверка типа factor_type...[/cyan]")
        
        success, stdout, stderr = self.run_command(
            [
                "docker", "exec", "supabase-db",
                "psql", "-U", "postgres", "-d", "postgres", "-c",
                "SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = 'factor_type' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'auth'));"
            ],
            timeout=10
        )
        
        if success and 't' in stdout.lower():
            self.console.print("[green]✓ Тип factor_type существует[/green]")
            return True
        else:
            self.console.print("[red]❌ Тип factor_type не найден[/red]")
            self.issues.append("База данных: тип factor_type отсутствует")
            return False
    
    def check_volumes(self) -> Dict[str, bool]:
        """Проверяет наличие необходимых volumes"""
        self.console.print("\n[cyan]🔍 Проверка volumes...[/cyan]")
        
        volumes = {
            'n8n_data': 'n8n',
            'langflow_data': 'langflow',
            'supabase_data': 'supabase',
            'caddy_data': 'caddy',
            'caddy_config': 'caddy'
        }
        
        success, stdout, stderr = self.run_command(
            ["docker", "volume", "ls", "-q"],
            timeout=10
        )
        
        existing_volumes = set(stdout.strip().split('\n')) if stdout.strip() else set()
        
        volume_status = {}
        for volume_key, service_name in volumes.items():
            # Ищем volume по имени проекта
            found = False
            for vol in existing_volumes:
                if volume_key.replace('_', '') in vol.lower() or service_name in vol.lower():
                    found = True
                    break
            
            if found:
                self.console.print(f"  [green]✓[/green] Volume для {service_name} найден")
                volume_status[volume_key] = True
            else:
                self.console.print(f"  [yellow]⚠[/yellow] Volume для {service_name} не найден")
                volume_status[volume_key] = False
        
        return volume_status
    
    def check_network(self) -> bool:
        """Проверяет наличие сети proxy"""
        self.console.print("\n[cyan]🔍 Проверка сети...[/cyan]")
        
        success, stdout, stderr = self.run_command(
            ["docker", "network", "ls", "-q", "-f", "name=proxy"],
            timeout=10
        )
        
        if success and stdout.strip():
            self.console.print("[green]✓ Сеть proxy существует[/green]")
            return True
        else:
            self.console.print("[yellow]⚠ Сеть proxy не найдена (будет создана автоматически)[/yellow]")
            return True  # Не критично, создастся автоматически
    
    def check_logs_for_errors(self, service_name: str, lines: int = 50) -> List[str]:
        """Проверяет логи сервиса на ошибки"""
        success, stdout, stderr = self.run_command(
            ["docker-compose", "logs", "--tail", str(lines), service_name],
            timeout=15
        )
        
        errors = []
        if stdout:
            error_keywords = ['error', 'fatal', 'failed', 'exception', 'panic', 'crash']
            for line in stdout.split('\n'):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in error_keywords):
                    errors.append(line.strip())
        
        return errors
    
    def diagnose_all(self) -> Dict:
        """Проводит полную диагностику системы"""
        self.console.print(Panel(
            "[bold cyan]🔍 ДИАГНОСТИКА СИСТЕМЫ[/bold cyan]",
            border_style="cyan"
        ))
        
        if not self.load_config():
            return {}
        
        if not self.check_docker_compose():
            return {}
        
        diagnosis = {
            'services': self.check_all_services(),
            'database_connection': self.check_database_connection(),
            'auth_schema': self.check_auth_schema(),
            'factor_type': self.check_factor_type(),
            'volumes': self.check_volumes(),
            'network': self.check_network(),
            'issues': self.issues.copy()
        }
        
        return diagnosis
    
    def fix_auth_schema(self) -> bool:
        """Исправляет схему auth"""
        self.console.print("\n[cyan]🔧 Исправление схемы auth...[/cyan]")
        
        init_sql = """
        -- Создаем схему auth если её нет
        CREATE SCHEMA IF NOT EXISTS auth;
        
        -- Создаем тип factor_type если его нет
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type 
                WHERE typname = 'factor_type' 
                AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'auth')
            ) THEN
                CREATE TYPE auth.factor_type AS ENUM ('totp', 'phone');
            END IF;
        END $$;
        """
        
        success, stdout, stderr = self.run_command(
            [
                "docker", "exec", "-i", "supabase-db",
                "psql", "-U", "postgres", "-d", "postgres"
            ],
            timeout=30,
            capture=False
        )
        
        # Используем subprocess.Popen для передачи SQL через stdin
        try:
            process = subprocess.Popen(
                [
                    "docker", "exec", "-i", "supabase-db",
                    "psql", "-U", "postgres", "-d", "postgres"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=init_sql, timeout=30)
            
            if process.returncode == 0:
                self.console.print("[green]✓ Схема auth исправлена[/green]")
                self.fixes_applied.append("Схема auth создана/исправлена")
                return True
            else:
                self.console.print(f"[yellow]⚠ Предупреждение: {stderr}[/yellow]")
                # Продолжаем даже если есть предупреждения
                self.fixes_applied.append("Попытка исправления схемы auth")
                return True
        except Exception as e:
            self.console.print(f"[yellow]⚠ Ошибка: {e}[/yellow]")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Перезапускает сервис"""
        self.console.print(f"\n[cyan]🔄 Перезапуск {service_name}...[/cyan]")
        
        success, stdout, stderr = self.run_command(
            ["docker-compose", "restart", service_name],
            timeout=60
        )
        
        if success:
            self.console.print(f"[green]✓ {service_name} перезапущен[/green]")
            self.fixes_applied.append(f"{service_name} перезапущен")
            time.sleep(5)  # Даем время на запуск
            return True
        else:
            self.console.print(f"[red]❌ Ошибка при перезапуске {service_name}[/red]")
            return False
    
    def recreate_service(self, service_name: str) -> bool:
        """Пересоздает контейнер сервиса"""
        self.console.print(f"\n[cyan]🔄 Пересоздание {service_name}...[/cyan]")
        
        # Останавливаем и удаляем
        self.run_command(["docker-compose", "stop", service_name], timeout=30)
        self.run_command(["docker-compose", "rm", "-f", service_name], timeout=30)
        
        # Запускаем заново
        success, stdout, stderr = self.run_command(
            ["docker-compose", "up", "-d", service_name],
            timeout=120
        )
        
        if success:
            self.console.print(f"[green]✓ {service_name} пересоздан[/green]")
            self.fixes_applied.append(f"{service_name} пересоздан")
            time.sleep(10)  # Даем время на запуск
            return True
        else:
            self.console.print(f"[red]❌ Ошибка при пересоздании {service_name}[/red]")
            return False
    
    def recreate_database(self) -> bool:
        """Пересоздает базу данных (удаляет все данные!)"""
        self.console.print("\n[red]⚠️  ВНИМАНИЕ: Это удалит все данные в базе данных![/red]")
        
        if not Confirm.ask("Продолжить?", default=False):
            return False
        
        # Останавливаем сервисы, зависящие от БД
        dependent_services = ['supabase-auth', 'supabase-rest', 'supabase-studio']
        for service in dependent_services:
            self.run_command(["docker-compose", "stop", service], timeout=30)
        
        # Останавливаем и удаляем БД
        self.run_command(["docker-compose", "stop", "supabase-db"], timeout=30)
        self.run_command(["docker-compose", "rm", "-f", "supabase-db"], timeout=30)
        
        # Ищем и удаляем volume
        success, stdout, stderr = self.run_command(
            ["docker", "volume", "ls", "-q"],
            timeout=10
        )
        
        if success and stdout:
            volumes = stdout.strip().split('\n')
            for volume in volumes:
                if 'supabase' in volume.lower() or 'postgres' in volume.lower():
                    self.run_command(["docker", "volume", "rm", volume], timeout=10)
        
        # Запускаем БД заново
        success, stdout, stderr = self.run_command(
            ["docker-compose", "up", "-d", "supabase-db"],
            timeout=120
        )
        
        if success:
            self.console.print("[green]✓ База данных пересоздана[/green]")
            self.console.print("[yellow]⏳ Ожидание инициализации (15 секунд)...[/yellow]")
            time.sleep(15)
            
            # Инициализируем схему auth
            self.fix_auth_schema()
            
            # Запускаем зависимые сервисы
            for service in dependent_services:
                self.run_command(["docker-compose", "up", "-d", service], timeout=60)
            
            self.fixes_applied.append("База данных пересоздана")
            return True
        else:
            self.console.print("[red]❌ Ошибка при пересоздании базы данных[/red]")
            return False
    
    def auto_fix(self, diagnosis: Dict) -> bool:
        """Автоматически исправляет найденные проблемы"""
        self.console.print(Panel(
            "[bold green]🔧 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ[/bold green]",
            border_style="green"
        ))
        
        fixed = False
        
        # Исправляем схему auth
        if not diagnosis.get('auth_schema', True) or not diagnosis.get('factor_type', True):
            if self.fix_auth_schema():
                fixed = True
                # Перезапускаем supabase-auth
                self.restart_service('supabase-auth')
        
        # Перезапускаем неработающие сервисы
        services_status = diagnosis.get('services', {})
        for service_name, status in services_status.items():
            if not status.get('running', False):
                if self.restart_service(service_name):
                    fixed = True
        
        # Перезапускаем нездоровые сервисы
        for service_name, status in services_status.items():
            if status.get('running', False) and not status.get('healthy', False):
                if service_name == 'supabase-auth' and not diagnosis.get('auth_schema', True):
                    # Для supabase-auth сначала исправляем схему
                    continue
                if self.restart_service(service_name):
                    fixed = True
        
        return fixed
    
    def show_summary(self, diagnosis: Dict):
        """Показывает сводку диагностики"""
        self.console.print("\n" + Panel(
            "[bold cyan]📊 СВОДКА ДИАГНОСТИКИ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Создаем таблицу статусов
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Сервис", style="cyan")
        table.add_column("Статус", justify="center")
        table.add_column("Здоровье", justify="center")
        
        services_status = diagnosis.get('services', {})
        for service_name, status in services_status.items():
            if status.get('running', False):
                status_text = "[green]✓ Работает[/green]"
            else:
                status_text = "[red]✗ Остановлен[/red]"
            
            if status.get('healthy', False):
                health_text = "[green]✓ Здоров[/green]"
            elif status.get('running', False):
                health_text = "[yellow]⚠ Нездоров[/yellow]"
            else:
                health_text = "[dim]-[/dim]"
            
            table.add_row(service_name, status_text, health_text)
        
        self.console.print(table)
        
        # Показываем проблемы
        issues = diagnosis.get('issues', [])
        if issues:
            self.console.print("\n[red]❌ Найденные проблемы:[/red]")
            for issue in issues:
                self.console.print(f"  • {issue}")
        else:
            self.console.print("\n[green]✓ Проблем не обнаружено![/green]")
        
        # Показываем примененные исправления
        if self.fixes_applied:
            self.console.print("\n[green]✅ Примененные исправления:[/green]")
            for fix in self.fixes_applied:
                self.console.print(f"  • {fix}")


def main():
    """Главная функция"""
    console.print(Panel(
        "[bold cyan]🔧 ДИАГНОСТИКА И ВОССТАНОВЛЕНИЕ СИСТЕМЫ[/bold cyan]\n\n"
        "Этот скрипт проведет диагностику всех компонентов системы\n"
        "и предложит варианты автоматического исправления проблем.",
        border_style="cyan"
    ))
    
    diagnostics = SystemDiagnostics()
    
    # Проверяем наличие необходимых файлов
    if not Path(".env").exists():
        console.print("[red]❌ Файл .env не найден![/red]")
        console.print("[yellow]Запустите сначала python3 setup.py[/yellow]")
        sys.exit(1)
    
    if not Path("docker-compose.yml").exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        console.print("[yellow]Запустите сначала python3 setup.py[/yellow]")
        sys.exit(1)
    
    # Проводим диагностику
    diagnosis = diagnostics.diagnose_all()
    
    # Показываем сводку
    diagnostics.show_summary(diagnosis)
    
    # Предлагаем исправления
    issues = diagnosis.get('issues', [])
    if issues:
        console.print("\n[cyan]💡 Доступные действия:[/cyan]")
        console.print("1. Автоматическое исправление (рекомендуется)")
        console.print("2. Ручное исправление конкретных проблем")
        console.print("3. Просмотр логов проблемных сервисов")
        console.print("4. Выход")
        
        choice = Prompt.ask("\nВыберите действие", choices=["1", "2", "3", "4"], default="1")
        
        if choice == "1":
            if Confirm.ask("\n[cyan]Применить автоматическое исправление?[/cyan]", default=True):
                diagnostics.auto_fix(diagnosis)
                # Повторная диагностика
                console.print("\n[cyan]🔍 Повторная диагностика после исправлений...[/cyan]")
                diagnosis = diagnostics.diagnose_all()
                diagnostics.show_summary(diagnosis)
        
        elif choice == "2":
            console.print("\n[cyan]Доступные ручные исправления:[/cyan]")
            
            if not diagnosis.get('auth_schema', True):
                if Confirm.ask("Исправить схему auth?", default=True):
                    diagnostics.fix_auth_schema()
                    diagnostics.restart_service('supabase-auth')
            
            services_status = diagnosis.get('services', {})
            for service_name, status in services_status.items():
                if not status.get('running', False):
                    if Confirm.ask(f"Перезапустить {service_name}?", default=True):
                        diagnostics.restart_service(service_name)
            
            if not diagnosis.get('database_connection', True):
                if Confirm.ask("Пересоздать базу данных? (удалит все данные!)", default=False):
                    diagnostics.recreate_database()
        
        elif choice == "3":
            services_status = diagnosis.get('services', {})
            problematic_services = [
                name for name, status in services_status.items()
                if not status.get('running', False) or not status.get('healthy', False)
            ]
            
            if problematic_services:
                console.print("\n[cyan]Проблемные сервисы:[/cyan]")
                for i, service in enumerate(problematic_services, 1):
                    console.print(f"{i}. {service}")
                
                service_choice = Prompt.ask(
                    "\nВыберите сервис для просмотра логов",
                    choices=[str(i) for i in range(1, len(problematic_services) + 1)],
                    default="1"
                )
                
                selected_service = problematic_services[int(service_choice) - 1]
                console.print(f"\n[cyan]Логи {selected_service}:[/cyan]")
                errors = diagnostics.check_logs_for_errors(selected_service, 100)
                if errors:
                    for error in errors[:20]:  # Показываем первые 20 ошибок
                        console.print(f"[red]{error}[/red]")
                else:
                    console.print("[yellow]Критических ошибок в логах не найдено[/yellow]")
    else:
        console.print("\n[green]✅ Все сервисы работают корректно![/green]")
    
    console.print("\n[yellow]💡 Для просмотра логов используйте:[/yellow]")
    console.print("[dim]docker-compose logs -f <имя_сервиса>[/dim]")


if __name__ == "__main__":
    main()

