#!/usr/bin/env python3
"""
Интерактивный установщик n8n + Langflow + Supabase stack
"""
import sys
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from installer.hardware_detector import detect_hardware
from installer.config_adaptor import adapt_config_for_hardware, get_resource_summary
from installer.resource_checker import display_resource_check
from installer.validator import (
    validate_domain, validate_port, validate_email, validate_path,
    validate_memory, validate_cpu, validate_api_key
)
from installer.docker_manager import (
    check_docker, check_docker_compose, is_docker_running,
    get_docker_version, get_docker_compose_version, docker_compose_up
)
from installer.config_generator import generate_env_file, generate_docker_compose, generate_caddyfile
# nginx-proxy автоматически настраивает маршрутизацию, ручная генерация конфигов не нужна
# from installer.nginx_config import generate_nginx_configs
from installer.utils import generate_secret_key, generate_password, ensure_dir

console = Console()


def install_dependencies():
    """Автоматическая установка Python зависимостей"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        console.print("[yellow]⚠ requirements.txt не найден[/yellow]")
        return False
    
    console.print("\n[cyan]📦 Установка Python зависимостей...[/cyan]")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Зависимости установлены[/green]")
            return True
        else:
            console.print(f"[yellow]⚠ Предупреждение при установке зависимостей:[/yellow]")
            console.print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠ Таймаут при установке зависимостей[/yellow]")
        return False
    except Exception as e:
        console.print(f"[yellow]⚠ Ошибка при установке зависимостей: {e}[/yellow]")
        return False


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🚀 Установщик n8n + Langflow + Supabase Stack

Этот скрипт поможет вам установить и настроить:
  • n8n - автоматизация рабочих процессов
  • Langflow - создание AI агентов
  • Supabase - база данных и бэкенд
  • Ollama - локальные LLM модели (опционально)

Следуйте инструкциям для настройки вашей системы.
"""
    console.print(Panel(welcome_text, title="[bold cyan]Добро пожаловать![/bold cyan]", border_style="cyan"))


def check_system_requirements():
    """Проверяет системные требования"""
    console.print("\n[cyan]🔍 Проверка системных требований...[/cyan]")
    
    # Проверка Docker
    if not check_docker():
        console.print("[red]❌ Docker не установлен![/red]")
        console.print("   Установите Docker: https://docs.docker.com/get-docker/")
        return False
    
    docker_version = get_docker_version()
    console.print(f"[green]✓ Docker установлен[/green] {docker_version}")
    
    # Проверка Docker Compose
    if not check_docker_compose():
        console.print("[red]❌ Docker Compose не установлен![/red]")
        console.print("   Установите Docker Compose: https://docs.docker.com/compose/install/")
        return False
    
    compose_version = get_docker_compose_version()
    console.print(f"[green]✓ Docker Compose установлен[/green] {compose_version}")
    
    # Проверка что Docker запущен
    if not is_docker_running():
        console.print("[red]❌ Docker daemon не запущен![/red]")
        console.print("   Запустите Docker и попробуйте снова")
        return False
    
    console.print("[green]✓ Docker daemon запущен[/green]")
    
    return True


def show_hardware_info(hardware):
    """Показывает информацию о железе"""
    table = Table(title="📊 Информация о системе")
    table.add_column("Компонент", style="cyan")
    table.add_column("Значение", style="green")
    
    # CPU
    cpu_info = f"{hardware['cpu']['cores']} ядер"
    if hardware['cpu']['threads'] > hardware['cpu']['cores']:
        cpu_info += f" ({hardware['cpu']['threads']} потоков)"
    table.add_row("CPU", cpu_info)
    
    # RAM
    ram_info = f"{hardware['ram']['total_gb']:.1f} GB"
    ram_info += f" (доступно: {hardware['ram']['available_gb']:.1f} GB)"
    table.add_row("RAM", ram_info)
    
    # GPU
    if hardware['gpu']['available']:
        gpu_info = f"{hardware['gpu']['vendor']} {hardware['gpu']['model']}"
        if hardware['gpu']['memory_gb'] > 0:
            gpu_info += f" ({hardware['gpu']['memory_gb']:.1f} GB)"
        if hardware['gpu']['cuda_available']:
            gpu_info += " [green]✓ CUDA[/green]"
    else:
        gpu_info = "[yellow]Не обнаружена[/yellow]"
    table.add_row("GPU", gpu_info)
    
    # Диск
    disk_info = f"{hardware['disk']['free_gb']:.1f} GB свободно"
    table.add_row("Диск", disk_info)
    
    # Тип системы
    system_type = "🖥️ Локальный ПК" if hardware['system_type'] == 'local' else "☁️ VPS"
    table.add_row("Тип системы", system_type)
    
    console.print(table)


def select_routing_mode() -> str:
    """Выбор режима маршрутизации"""
    console.print("\n[cyan]🌐 Выбор режима маршрутизации[/cyan]")
    
    options = {
        '1': 'subdomain',
        '2': 'path',
        '3': 'none'
    }
    
    console.print("""
  1) Поддомены (n8n.yourdomain.com, langflow.yourdomain.com)
  2) Пути (yourdomain.com/n8n, yourdomain.com/langflow)
  3) Без доменов (только порты, для разработки)
""")
    
    choice = Prompt.ask("Ваш выбор", choices=['1', '2', '3'], default='3')
    return options[choice]


def configure_domains(routing_mode: str, ollama_available: bool = False) -> dict:
    """Настройка доменов"""
    domains_config = {}
    
    if routing_mode == 'subdomain':
        console.print("\n[bold cyan]📝 КОНФИГУРАЦИЯ СИСТЕМЫ:[/bold cyan]")
        console.print("\n[cyan]🌐 Домены[/cyan]")
        console.print("[yellow]💡[/yellow] Домены опциональны. Если не указаны, доступ будет по IP адресу сервера\n")
        
        # Выбор режима ввода
        use_auto = Confirm.ask(
            "Автоматически сформировать поддомены из базового домена?",
            default=True
        )
        
        if use_auto:
            # АВТОМАТИЧЕСКИЙ РЕЖИМ
            console.print("\n[yellow]💡[/yellow] Введите базовый домен, система автоматически сформирует поддомены")
            console.print("[yellow]💡[/yellow] Или введите '-' для пропуска (система будет работать по IP/localhost)\n")
            
            while True:
                base_domain = Prompt.ask("Базовый домен (пример: site.ru) или '-'", default="-")
                if base_domain == '-':
                    break
                
                # Валидация базового домена
                is_valid, error = validate_domain(base_domain)
                if not is_valid:
                    console.print(f"[red]❌ {error}[/red]")
                    continue
                
                # Автоматически формируем поддомены для основных сервисов
                generated_domains = {
                    'n8n_domain': f"n8n.{base_domain}",
                    'langflow_domain': f"langflow.{base_domain}",
                    'supabase_domain': f"supabase.{base_domain}"
                }
                
                # Показываем сформированные поддомены
                console.print("\n[green]✓ Сформированные поддомены:[/green]")
                console.print(f"  N8N: [cyan]{generated_domains['n8n_domain']}[/cyan]")
                console.print(f"  Langflow: [cyan]{generated_domains['langflow_domain']}[/cyan]")
                console.print(f"  Supabase: [cyan]{generated_domains['supabase_domain']}[/cyan]")
                
                # Подтверждение основных доменов
                if Confirm.ask("\nИспользовать эти поддомены?", default=True):
                    domains_config.update(generated_domains)
                    
                    # Спрашиваем про Ollama отдельно, если доступен
                    if ollama_available:
                        console.print("\n[cyan]🌐 Опциональные домены:[/cyan]")
                        ollama_domain = Prompt.ask(
                            f"Домен Ollama (пример: ollama.{base_domain}) или '-' для пропуска",
                            default=f"ollama.{base_domain}"
                        )
                        if ollama_domain != '-':
                            is_valid, error = validate_domain(ollama_domain)
                            if is_valid:
                                domains_config['ollama_domain'] = ollama_domain
                            else:
                                console.print(f"[red]❌ {error}[/red]")
                                console.print("[yellow]Домен Ollama пропущен[/yellow]")
                    
                    break
                else:
                    console.print("[yellow]Введите другой базовый домен или '-' для пропуска[/yellow]\n")
        else:
            # РУЧНОЙ РЕЖИМ (как было раньше)
            console.print("\n[yellow]💡[/yellow] Домены (введите '-' для пропуска, система будет работать по IP/localhost):\n")
            
            while True:
                n8n_domain = Prompt.ask("Домен N8N (пример: n8n.site.ru) или '-'", default="-")
                if n8n_domain == '-':
                    break
                is_valid, error = validate_domain(n8n_domain)
                if is_valid:
                    domains_config['n8n_domain'] = n8n_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
            
            while True:
                langflow_domain = Prompt.ask("Домен Langflow (пример: langflow.site.ru) или '-'", default="-")
                if langflow_domain == '-':
                    break
                is_valid, error = validate_domain(langflow_domain)
                if is_valid:
                    domains_config['langflow_domain'] = langflow_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
            
            while True:
                supabase_domain = Prompt.ask("Домен Supabase (пример: supabase.site.ru) или '-'", default="-")
                if supabase_domain == '-':
                    break
                is_valid, error = validate_domain(supabase_domain)
                if is_valid:
                    domains_config['supabase_domain'] = supabase_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
            
            # Опциональные домены
            if ollama_available:
                console.print("\n[cyan]🌐 Опциональные домены (введите '-' для пропуска):[/cyan]")
                ollama_domain = Prompt.ask("Домен Ollama (пример: ollama.site.ru) или '-'", default="-")
                if ollama_domain != '-':
                    is_valid, error = validate_domain(ollama_domain)
                    if is_valid:
                        domains_config['ollama_domain'] = ollama_domain
        
        # SSL
        if any(domains_config.values()):
            console.print("\n[yellow]🔒 Email для SSL сертификатов:[/yellow]")
            console.print("[yellow]⚠ ВАЖНО: Используйте настоящий email адрес![/yellow]")
            console.print("[yellow]⚠ Let's Encrypt не принимает фейковые email (например, test@test.test)[/yellow]\n")
            
            while True:
                email = Prompt.ask("Email для Let's Encrypt")
                is_valid, error = validate_email(email)
                if is_valid:
                    domains_config['letsencrypt_email'] = email
                    domains_config['ssl_enabled'] = True
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    
    elif routing_mode == 'path':
        console.print("\n[bold cyan]📝 КОНФИГУРАЦИЯ СИСТЕМЫ:[/bold cyan]")
        console.print("\n[cyan]🌐 Домены[/cyan]")
        console.print("[yellow]💡[/yellow] Домены опциональны. Если не указаны, доступ будет по IP адресу сервера\n")
        
        # Выбор режима ввода
        use_auto = Confirm.ask(
            "Автоматически сформировать пути из базового домена?",
            default=True
        )
        
        if use_auto:
            # АВТОМАТИЧЕСКИЙ РЕЖИМ
            console.print("\n[yellow]💡[/yellow] Введите базовый домен, система автоматически сформирует пути")
            console.print("[yellow]💡[/yellow] Или введите '-' для пропуска (система будет работать по IP/localhost)\n")
            
            while True:
                base_domain = Prompt.ask("Базовый домен (пример: site.ru) или '-'", default="-")
                if base_domain == '-':
                    break
                
                # Валидация базового домена
                is_valid, error = validate_domain(base_domain)
                if not is_valid:
                    console.print(f"[red]❌ {error}[/red]")
                    continue
                
                # Автоматически формируем пути для основных сервисов
                generated_paths = {
                    'base_domain': base_domain,
                    'n8n_path': '/n8n',
                    'langflow_path': '/langflow',
                    'supabase_path': '/supabase'
                }
                
                # Показываем сформированные пути
                console.print("\n[green]✓ Сформированные пути:[/green]")
                console.print(f"  Базовый домен: [cyan]{base_domain}[/cyan]")
                console.print(f"  N8N: [cyan]{base_domain}{generated_paths['n8n_path']}[/cyan]")
                console.print(f"  Langflow: [cyan]{base_domain}{generated_paths['langflow_path']}[/cyan]")
                console.print(f"  Supabase: [cyan]{base_domain}{generated_paths['supabase_path']}[/cyan]")
                
                # Подтверждение основных путей
                if Confirm.ask("\nИспользовать эти пути?", default=True):
                    domains_config.update(generated_paths)
                    
                    # Спрашиваем про Ollama отдельно, если доступен
                    if ollama_available:
                        console.print("\n[cyan]🌐 Опциональные пути:[/cyan]")
                        ollama_path = Prompt.ask(
                            f"Путь для Ollama (пример: /ollama) или '-' для пропуска",
                            default="/ollama"
                        )
                        if ollama_path != '-':
                            domains_config['ollama_path'] = ollama_path
                    
                    break
                else:
                    console.print("[yellow]Введите другой базовый домен или '-' для пропуска[/yellow]\n")
        else:
            # РУЧНОЙ РЕЖИМ (как было раньше)
            console.print("\n[yellow]💡[/yellow] Домены (введите '-' для пропуска, система будет работать по IP/localhost):\n")
            
            while True:
                base_domain = Prompt.ask("Базовый домен (пример: site.ru) или '-'", default="-")
                if base_domain == '-':
                    break
                is_valid, error = validate_domain(base_domain)
                if is_valid:
                    domains_config['base_domain'] = base_domain
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
            
            if base_domain != '-':
                domains_config['n8n_path'] = Prompt.ask("Путь для N8N", default="/n8n")
                domains_config['langflow_path'] = Prompt.ask("Путь для Langflow", default="/langflow")
                domains_config['supabase_path'] = Prompt.ask("Путь для Supabase", default="/supabase")
                
                if ollama_available:
                    domains_config['ollama_path'] = Prompt.ask("Путь для Ollama", default="/ollama")
        
        # SSL
        if any(domains_config.values()):
            console.print("\n[yellow]🔒 Email для SSL сертификатов:[/yellow]")
            console.print("[yellow]⚠ ВАЖНО: Используйте настоящий email адрес![/yellow]\n")
            
            while True:
                email = Prompt.ask("Email для Let's Encrypt")
                is_valid, error = validate_email(email)
                if is_valid:
                    domains_config['letsencrypt_email'] = email
                    domains_config['ssl_enabled'] = True
                    break
                else:
                    console.print(f"[red]❌ {error}[/red]")
    
    return domains_config


def configure_services(recommended_config: dict, hardware: dict) -> dict:
    """Настройка сервисов"""
    console.print("\n[cyan]⚙️ Настройка сервисов[/cyan]")
    
    services_config = {}
    
    # Использовать рекомендуемые настройки?
    use_recommended = Confirm.ask(
        "Использовать рекомендуемые настройки на основе вашего железа?",
        default=True
    )
    
    if use_recommended:
        services_config = {
            'n8n_memory_limit': f"{recommended_config['memory_limits']['n8n']:.1f}g",
            'n8n_cpu_limit': recommended_config['cpu_limits']['n8n'],
            'langflow_memory_limit': f"{recommended_config['memory_limits']['langflow']:.1f}g",
            'langflow_cpu_limit': recommended_config['cpu_limits']['langflow'],
            'supabase_memory_limit': f"{recommended_config['memory_limits']['supabase']:.1f}g",
            'supabase_cpu_limit': recommended_config['cpu_limits']['supabase'],
        }
    else:
        # Ручная настройка
        console.print("\n[yellow]N8N:[/yellow]")
        services_config['n8n_memory_limit'] = Prompt.ask(
            "Лимит памяти (например, 2g)",
            default=f"{recommended_config['memory_limits']['n8n']:.1f}g"
        )
        services_config['n8n_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(recommended_config['cpu_limits']['n8n'])
        ))
        
        console.print("\n[yellow]Langflow:[/yellow]")
        services_config['langflow_memory_limit'] = Prompt.ask(
            "Лимит памяти",
            default=f"{recommended_config['memory_limits']['langflow']:.1f}g"
        )
        services_config['langflow_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(recommended_config['cpu_limits']['langflow'])
        ))
        
        console.print("\n[yellow]Supabase:[/yellow]")
        services_config['supabase_memory_limit'] = Prompt.ask(
            "Лимит памяти",
            default=f"{recommended_config['memory_limits']['supabase']:.1f}g"
        )
        services_config['supabase_cpu_limit'] = float(Prompt.ask(
            "Лимит CPU",
            default=str(recommended_config['cpu_limits']['supabase'])
        ))
    
    # Порты
    console.print("\n[cyan]🔌 Настройка портов:[/cyan]")
    console.print("[yellow]💡[/yellow] Нажмите Enter для продолжения с портом по умолчанию или введите свой порт\n")
    
    services_config['n8n_port'] = IntPrompt.ask("Порт для N8N (5678)", default=5678)
    services_config['langflow_port'] = IntPrompt.ask("Порт для Langflow (7860)", default=7860)
    
    # Настройка автологина Langflow
    console.print("\n[yellow]Настройка автологина Langflow:[/yellow]")
    services_config['langflow_auto_login'] = Confirm.ask(
        "Включить автологин в Langflow?",
        default=True
    )
    if services_config['langflow_auto_login']:
        services_config['langflow_username'] = Prompt.ask(
            "Имя пользователя для Langflow",
            default="admin"
        )
        services_config['langflow_password'] = Prompt.ask(
            "Пароль для Langflow (оставьте пустым для автогенерации)",
            default="",
            password=True
        )
        if not services_config['langflow_password']:
            from installer.utils import generate_password
            services_config['langflow_password'] = generate_password()
            console.print(f"[green]✓ Пароль сгенерирован: {services_config['langflow_password']}[/green]")
    else:
        services_config['langflow_username'] = 'admin'
        services_config['langflow_password'] = ''
    services_config['supabase_port'] = IntPrompt.ask("Порт для Supabase (8000)", default=8000)
    
    # Ollama
    if recommended_config.get('ollama_recommended', False):
        ollama_enabled = Confirm.ask(
            "Включить Ollama? (требуется GPU или много RAM)",
            default=True
        )
    else:
        ollama_enabled = Confirm.ask(
            "Включить Ollama? [yellow](не рекомендуется без GPU)[/yellow]",
            default=False
        )
    
    services_config['ollama_enabled'] = ollama_enabled
    
    if ollama_enabled:
        services_config['ollama_port'] = IntPrompt.ask("Порт для Ollama (11434)", default=11434)
        services_config['ollama_memory_limit'] = f"{recommended_config['memory_limits']['ollama']:.1f}g"
        services_config['ollama_cpu_limit'] = recommended_config['cpu_limits']['ollama']
        services_config['ollama_image'] = recommended_config['ollama_image']
    
    return services_config


def configure_supabase() -> dict:
    """Настройка Supabase: пароль, ключи"""
    console.print("\n[yellow]🗄️ Настройка Supabase:[/yellow]")
    
    # Пароль для Supabase
    console.print("\n[cyan]Пароль для Supabase:[/cyan]")
    console.print("[yellow]💡[/yellow] Пароль для подключения к базе данных PostgreSQL\n")
    
    generate_password_auto = Confirm.ask(
        "Сгенерировать пароль автоматически?",
        default=True
    )
    
    if generate_password_auto:
        postgres_password = generate_password()
        console.print(f"[green]✓ Пароль сгенерирован: {postgres_password}[/green]")
        console.print("[yellow]⚠ Сохраните этот пароль! Он понадобится для подключения к базе данных[/yellow]")
    else:
        while True:
            postgres_password = Prompt.ask(
                "Введите пароль для Supabase (минимум 8 символов)",
                password=True
            )
            if len(postgres_password) >= 8:
                break
            else:
                console.print("[red]❌ Пароль должен быть минимум 8 символов[/red]")
    
    # Логин для админки (фиксированный)
    supabase_admin_login = "admin"
    console.print(f"\n[cyan]Логин для админки Supabase: {supabase_admin_login}[/cyan]")
    console.print("[yellow]💡[/yellow] Логин 'admin' будет использоваться для входа в админ-панель Supabase\n")
    
    # Ключи Supabase
    console.print("[yellow]🔑 Ключи Supabase:[/yellow]")
    console.print("[yellow]💡[/yellow] Генерация: https://supabase.com/docs/guides/self-hosting/docker#generate-api-keys")
    console.print("[cyan]Ссылка открыта в браузере или скопируйте её[/cyan]\n")
    
    # Пытаемся открыть ссылку
    import webbrowser
    try:
        webbrowser.open("https://supabase.com/docs/guides/self-hosting/docker#generate-api-keys")
    except Exception:
        pass
    
    # Запрашиваем ключи у пользователя
    console.print("[yellow]⚠ Введите ключи Supabase из документации:[/yellow]\n")
    
    while True:
        jwt_secret = Prompt.ask("JWT_SECRET (минимум 32 символов)", default="")
        if len(jwt_secret) >= 32:
            break
        else:
            console.print("[red]❌ JWT_SECRET должен быть минимум 32 символа[/red]")
    
    while True:
        anon_key = Prompt.ask("ANON_KEY", default="")
        if anon_key:
            break
        else:
            console.print("[red]❌ ANON_KEY обязателен для работы Supabase[/red]")
    
    while True:
        service_role_key = Prompt.ask("SERVICE_ROLE_KEY", default="")
        if service_role_key:
            break
        else:
            console.print("[red]❌ SERVICE_ROLE_KEY обязателен для работы Supabase[/red]")
    
    return {
        'postgres_password': postgres_password,
        'supabase_admin_login': supabase_admin_login,
        'jwt_secret': jwt_secret,
        'anon_key': anon_key,
        'service_role_key': service_role_key
    }


def main():
    """Главная функция установщика"""
    try:
        # 0. Установка зависимостей
        install_dependencies()
        
        # 1. Приветствие
        show_welcome()
        
        # 2. Проверка системных требований
        if not check_system_requirements():
            console.print("\n[red]Установка прервана из-за ошибок[/red]")
            sys.exit(1)
        
        # 3. Определение железа
        console.print("\n[cyan]🔍 Анализ системы...[/cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Определение характеристик...", total=None)
            hardware = detect_hardware()
            progress.update(task, completed=True)
        
        show_hardware_info(hardware)
        
        # 4. Адаптация под железо
        recommended_config = adapt_config_for_hardware(hardware)
        
        # Показываем рекомендации
        if recommended_config.get('warnings'):
            console.print("\n[yellow]⚠ Предупреждения:[/yellow]")
            for warning in recommended_config['warnings']:
                console.print(Panel(warning, border_style="yellow"))
        
        if recommended_config.get('errors'):
            console.print("\n[red]❌ Ошибки:[/red]")
            for error in recommended_config['errors']:
                console.print(Panel(error, border_style="red"))
            
            if not Confirm.ask("Продолжить установку несмотря на ошибки?", default=False):
                sys.exit(1)
        
        # Показываем рекомендуемые настройки
        summary = get_resource_summary(recommended_config)
        console.print(f"\n[cyan]💡 Рекомендуемые настройки:[/cyan]")
        console.print(f"  CPU: {summary['total_cpu_cores']:.1f} ядер")
        console.print(f"  RAM: {summary['total_memory_gb']:.1f} GB")
        console.print(f"  Сервисов: {summary['services_count']}")
        
        if recommended_config.get('use_gpu'):
            console.print("[green]✓ GPU обнаружена - можно использовать Ollama[/green]")
        
        # 5. Проверка ресурсов
        if not display_resource_check(hardware, recommended_config):
            if not Confirm.ask("\nПродолжить установку?", default=False):
                sys.exit(1)
        
        # 6. Выбор режима маршрутизации
        routing_mode = select_routing_mode()
        
        # 7. Настройка доменов
        domains_config = {}
        if routing_mode != 'none':
            # Проверяем, доступен ли Ollama (на основе железа)
            ollama_available = recommended_config.get('ollama_recommended', False) or recommended_config.get('use_gpu', False)
            domains_config = configure_domains(routing_mode, ollama_available=ollama_available)
        
        # 8. Настройка сервисов
        services_config = configure_services(recommended_config, hardware)
        
        # 9. Настройка Supabase (пароль, ключи)
        supabase_config = configure_supabase()
        services_config.update(supabase_config)
        
        # 10. Объединяем конфигурацию
        full_config = {
            'routing_mode': routing_mode,
            **domains_config,
            **services_config,
            **recommended_config
        }
        
        # 11. Генерация конфигов
        console.print("\n[cyan]📝 Генерация конфигурационных файлов...[/cyan]")
        
        # Создаем структуру папок
        ensure_dir("volumes/n8n_data")
        ensure_dir("volumes/langflow_data")
        ensure_dir("volumes/supabase_data")
        if full_config.get('ollama_enabled'):
            ensure_dir("volumes/ollama_data")
        
        # Генерируем .env
        generate_env_file(full_config)
        console.print("[green]✓ .env файл создан[/green]")
        
        # Генерируем docker-compose.yml
        generate_docker_compose(full_config, hardware)
        console.print("[green]✓ docker-compose.yml создан[/green]")
        
        # Генерация Caddyfile
        generate_caddyfile(full_config)
        console.print("[green]✓ Caddyfile создан[/green]")
        
        # nginx-proxy автоматически настраивает маршрутизацию через переменные VIRTUAL_HOST
        if routing_mode == 'subdomain':
            console.print("[green]✓ nginx-proxy настроен для автоматической маршрутизации[/green]")
        
        # 12. Запуск сервисов
        console.print("\n[cyan]🚀 Готово к запуску![/cyan]")
        if Confirm.ask("Запустить сервисы сейчас?", default=True):
            console.print("\n[cyan]Запуск сервисов...[/cyan]")
            console.print("[yellow]💡 Это может занять несколько минут при первой загрузке образов[/yellow]\n")
            
            # Указываем путь к docker-compose.yml
            compose_file = Path.cwd() / "docker-compose.yml"
            if docker_compose_up(file=str(compose_file)):
                console.print("\n[green]✓ Сервисы запущены![/green]")
                
                # Показываем информацию для доступа
                console.print("\n[cyan]📋 Информация для доступа:[/cyan]")
                if routing_mode == 'subdomain':
                    if full_config.get('n8n_domain'):
                        console.print(f"  N8N: http{'s' if full_config.get('ssl_enabled') else ''}://{full_config['n8n_domain']}")
                    if full_config.get('langflow_domain'):
                        console.print(f"  Langflow: http{'s' if full_config.get('ssl_enabled') else ''}://{full_config['langflow_domain']}")
                elif routing_mode == 'path':
                    if full_config.get('base_domain'):
                        console.print(f"  N8N: http{'s' if full_config.get('ssl_enabled') else ''}://{full_config['base_domain']}{full_config.get('n8n_path', '/n8n')}")
                else:
                    console.print(f"  N8N: http://localhost:{full_config.get('n8n_port', 5678)}")
                    console.print(f"  Langflow: http://localhost:{full_config.get('langflow_port', 7860)}")
                    console.print(f"  Supabase: http://localhost:{full_config.get('supabase_port', 8000)}")
                
                console.print("\n[yellow]💡 Если сервисы не запустились, проверьте логи:[/yellow]")
                console.print("[dim]docker-compose logs[/dim]")
            else:
                console.print("\n[red]❌ Ошибка при запуске сервисов[/red]")
                console.print("\n[yellow]💡 Диагностика проблемы:[/yellow]")
                console.print("  1. Проверьте логи: [dim]docker-compose logs[/dim]")
                console.print("  2. Проверьте статус: [dim]docker-compose ps[/dim]")
                console.print("  3. Попробуйте запустить вручную: [dim]docker-compose up -d[/dim]")
                console.print("  4. Проверьте .env файл на наличие всех переменных")
        
        console.print("\n[green]✓ Установка завершена![/green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Установка прервана пользователем[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Ошибка: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

