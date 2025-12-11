#!/usr/bin/env python3
"""
Скрипт для переключения с режима портов на режим доменов (SSL)
"""
import re
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from dotenv import load_dotenv
import os

console = Console()


def validate_email(email: str) -> tuple[bool, str]:
    """Проверяет валидность email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not email:
        return False, "Email не может быть пустым"
    if not re.match(pattern, email):
        return False, "Неверный формат email"
    # Проверяем что это не тестовый email
    test_emails = ['test@test.test', 'test@test.com', 'example@example.com']
    if email.lower() in test_emails:
        return False, "Используйте настоящий email адрес (Let's Encrypt не принимает тестовые email)"
    return True, ""


def validate_domain(domain: str) -> tuple[bool, str]:
    """Проверяет валидность домена"""
    import re
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    if not domain:
        return False, "Домен не может быть пустым"
    if not re.match(pattern, domain):
        return False, "Неверный формат домена"
    return True, ""


def read_docker_compose():
    """Читает docker-compose.yml"""
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        return None
    return compose_path.read_text(encoding='utf-8')


def write_docker_compose(content):
    """Записывает docker-compose.yml"""
    compose_path = Path("docker-compose.yml")
    # Создаем резервную копию
    backup_path = compose_path.with_suffix('.yml.backup')
    if compose_path.exists():
        backup_path.write_text(compose_path.read_text(encoding='utf-8'), encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
    
    compose_path.write_text(content, encoding='utf-8')
    console.print("[green]✓ docker-compose.yml обновлен[/green]")


def disable_ports_for_service(content, service_name):
    """Отключает порты для сервиса (комментирует)"""
    # Паттерн для незакомментированных портов
    pattern = rf'(\s+{service_name}:[^\n]*\n(?:(?!\s+[a-z-]+:)[^\n]*\n)*?)(\s+)# Прямой доступ через порт.*?\n(\s+)ports:\n(\s+)\s+- "(\d+):(\d+)"'
    
    def comment_ports(match):
        before_ports = match.group(1)
        indent = match.group(2)
        indent2 = match.group(3)
        indent3 = match.group(4)
        external_port = match.group(5)
        internal_port = match.group(6)
        
        ports_section = f'{indent}# ВАЖНО: Не открываем порт наружу напрямую! Прокси через Caddy.\n{indent2}# ports:\n{indent3}#   - "{external_port}:{internal_port}"\n'
        
        return f'{before_ports}{ports_section}'
    
    new_content = re.sub(pattern, comment_ports, content, flags=re.MULTILINE)
    
    if new_content != content:
        console.print(f"[green]✓ Порт отключен для {service_name}[/green]")
        return new_content
    
    return content


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🌐 Переключение на режим доменов (SSL)[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Настроит домены для сервисов")
    console.print("2. Отключит прямой доступ через порты")
    console.print("3. Настроит SSL сертификаты через Caddy")
    console.print("4. Перегенерирует конфигурацию")
    
    if not Confirm.ask("\n[cyan]Продолжить? (y/n): [/cyan]", default=True):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # Загружаем текущую конфигурацию
    load_dotenv()
    
    # Проверяем какие сервисы включены
    n8n_enabled = os.getenv('N8N_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    langflow_enabled = os.getenv('LANGFLOW_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    
    # Настройка доменов
    console.print("\n[bold cyan]📝 Настройка доменов[/bold cyan]")
    console.print("[yellow]💡 Введите домены для ваших сервисов[/yellow]")
    console.print("[yellow]💡 Или введите '-' для пропуска (будет использован IP адрес)[/yellow]\n")
    
    domains = {}
    
    if n8n_enabled:
        n8n_domain = Prompt.ask("Домен для N8N (пример: n8n.yourdomain.com) или '-'", default="-")
        if n8n_domain != '-':
            is_valid, error = validate_domain(n8n_domain)
            if not is_valid:
                console.print(f"[red]❌ {error}[/red]")
                return
            domains['n8n_domain'] = n8n_domain
    
    if langflow_enabled:
        langflow_domain = Prompt.ask("Домен для Langflow (пример: langflow.yourdomain.com) или '-'", default="-")
        if langflow_domain != '-':
            is_valid, error = validate_domain(langflow_domain)
            if not is_valid:
                console.print(f"[red]❌ {error}[/red]")
                return
            domains['langflow_domain'] = langflow_domain
    
    supabase_domain = Prompt.ask("Домен для Supabase (пример: supabase.yourdomain.com) или '-'", default="-")
    if supabase_domain != '-':
        is_valid, error = validate_domain(supabase_domain)
        if not is_valid:
            console.print(f"[red]❌ {error}[/red]")
            return
        domains['supabase_domain'] = supabase_domain
    
    # Настройка SSL
    if any(domains.values()):
        console.print("\n[bold cyan]🔐 Настройка SSL[/bold cyan]")
        console.print("[yellow]⚠ ВАЖНО: Используйте настоящий email адрес![/yellow]\n")
        
        while True:
            email = Prompt.ask("Email для Let's Encrypt")
            is_valid, error = validate_email(email)
            if is_valid:
                break
            else:
                console.print(f"[red]❌ {error}[/red]")
        
        # Выбор между production и staging
        console.print("\n[cyan]🔐 Режим SSL сертификатов:[/cyan]")
        console.print("[yellow]💡 Production - для продакшена (доверяются браузерами)[/yellow]")
        console.print("[yellow]💡 Staging - для тестирования (более высокие лимиты, НЕ доверяются браузерами)[/yellow]\n")
        
        use_staging = Confirm.ask(
            "Использовать Let's Encrypt Staging? (для тестирования)",
            default=False
        )
        
        if use_staging:
            console.print("[yellow]⚠ Staging сертификаты НЕ доверяются браузерами![/yellow]")
            console.print("[yellow]⚠ Используйте только для тестирования конфигурации[/yellow]")
    else:
        console.print("\n[yellow]⚠ Домены не указаны, SSL не будет настроен[/yellow]")
        email = ''
        use_staging = False
    
    # Обновляем .env
    console.print("\n[cyan]Шаг 1: Обновление .env[/cyan]")
    env_path = Path(".env")
    if env_path.exists():
        env_content = env_path.read_text(encoding='utf-8')
        
        # Обновляем домены
        if n8n_enabled:
            env_content = re.sub(
                r'^N8N_DOMAIN=.*$',
                f"N8N_DOMAIN={domains.get('n8n_domain', '')}",
                env_content,
                flags=re.MULTILINE
            )
        
        if langflow_enabled:
            env_content = re.sub(
                r'^LANGFLOW_DOMAIN=.*$',
                f"LANGFLOW_DOMAIN={domains.get('langflow_domain', '')}",
                env_content,
                flags=re.MULTILINE
            )
        
        env_content = re.sub(
            r'^SUPABASE_DOMAIN=.*$',
            f"SUPABASE_DOMAIN={domains.get('supabase_domain', '')}",
            env_content,
            flags=re.MULTILINE
        )
        
        # Обновляем routing_mode
        env_content = re.sub(
            r'^ROUTING_MODE=.*$',
            "ROUTING_MODE=subdomain",
            env_content,
            flags=re.MULTILINE
        )
        
        # Обновляем SSL настройки
        if email:
            env_content = re.sub(
                r'^LETSENCRYPT_EMAIL=.*$',
                f"LETSENCRYPT_EMAIL={email}",
                env_content,
                flags=re.MULTILINE
            )
            env_content = re.sub(
                r'^LETSENCRYPT_STAGING=.*$',
                f"LETSENCRYPT_STAGING={'true' if use_staging else 'false'}",
                env_content,
                flags=re.MULTILINE
            )
            env_content = re.sub(
                r'^SSL_ENABLED=.*$',
                "SSL_ENABLED=true",
                env_content,
                flags=re.MULTILINE
            )
        
        env_path.write_text(env_content, encoding='utf-8')
        console.print("[green]✓ .env обновлен[/green]")
    else:
        console.print("[yellow]⚠ Файл .env не найден[/yellow]")
    
    # Отключаем порты в docker-compose.yml
    console.print("\n[cyan]Шаг 2: Отключение прямых портов[/cyan]")
    content = read_docker_compose()
    if content:
        if n8n_enabled:
            content = disable_ports_for_service(content, 'n8n')
        if langflow_enabled:
            content = disable_ports_for_service(content, 'langflow')
        content = disable_ports_for_service(content, 'supabase-studio')
        write_docker_compose(content)
    
    # Перегенерируем Caddyfile
    console.print("\n[cyan]Шаг 3: Перегенерация Caddyfile[/cyan]")
    try:
        from regenerate_caddyfile import main as regenerate_main
        regenerate_main()
    except ImportError:
        console.print("[yellow]⚠ Скрипт regenerate_caddyfile.py не найден[/yellow]")
        console.print("[cyan]💡 Запустите вручную: python3 regenerate_caddyfile.py[/cyan]")
    except Exception as e:
        console.print(f"[red]❌ Ошибка при перегенерации Caddyfile: {e}[/red]")
    
    # Перезапускаем сервисы
    console.print("\n[cyan]Шаг 4: Перезапуск сервисов[/cyan]")
    if Confirm.ask("Перезапустить сервисы? (y/n)", default=True):
        try:
            subprocess.run(
                ["docker-compose", "restart", "caddy"],
                check=True,
                timeout=30
            )
            console.print("[green]✓ Caddy перезапущен[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Не удалось перезапустить Caddy: {e}[/yellow]")
            console.print("[cyan]💡 Запустите вручную: docker-compose restart caddy[/cyan]")
    
    console.print("\n[bold green]✅ Готово![/bold green]")
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    console.print("1. Убедитесь, что DNS записи (A-записи) указывают на ваш IP сервера")
    console.print("2. Подождите 1-2 минуты для получения SSL сертификатов")
    console.print("3. Проверьте логи: docker-compose logs -f caddy")
    console.print("4. Откройте ваши домены в браузере")
    
    if use_staging:
        console.print("\n[yellow]⚠ Внимание: Staging сертификаты НЕ доверяются браузерами![/yellow]")
        console.print("[yellow]⚠ Для продакшена переключитесь на Production[/yellow]")


if __name__ == "__main__":
    main()

