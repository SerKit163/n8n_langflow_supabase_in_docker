#!/usr/bin/env python3
"""
Скрипт для настройки обхода лимитов Let's Encrypt в Caddy
Основано на статьях:
- https://habr.com/ru/articles/923150/
- https://samjmck.com/en/blog/using-caddy-with-cloudflare/
"""
import os
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from dotenv import load_dotenv

console = Console()

def setup_dns_challenge_cloudflare():
    """Настройка DNS challenge через Cloudflare"""
    console.print("\n[cyan]🔧 Настройка DNS Challenge через Cloudflare[/cyan]")
    console.print("[yellow]Это позволит обойти HTTP-01 проверку и лимиты Let's Encrypt[/yellow]")
    console.print("[dim]⚠ ОПЦИОНАЛЬНО: Нужно только если используете Cloudflare DNS[/dim]")
    
    use_cloudflare = Confirm.ask("Используете Cloudflare для ваших доменов?", default=False)
    
    if not use_cloudflare:
        console.print("[cyan]ℹ Пропускаем настройку Cloudflare (не обязательно)[/cyan]")
        return None
    
    console.print("\n[yellow]💡 Как получить Cloudflare API Token:[/yellow]")
    console.print("1. Зайдите в Cloudflare Dashboard → My Profile → API Tokens")
    console.print("2. Create Token → Permissions: Zone → DNS → Edit")
    console.print("3. Zone Resources: Include → All zones")
    console.print("4. Скопируйте токен\n")
    
    cloudflare_token = Prompt.ask(
        "Введите Cloudflare API Token (или нажмите Enter чтобы пропустить)",
        default="",
        password=True
    )
    
    if not cloudflare_token:
        console.print("[yellow]⚠ API Token не указан, пропускаем настройку Cloudflare[/yellow]")
        console.print("[cyan]ℹ Это нормально - ротация email работает без Cloudflare[/cyan]")
        return None
    
    return {
        'enabled': True,
        'token': cloudflare_token,
        'provider': 'cloudflare'
    }

def setup_email_rotation():
    """Настройка ротации email для обхода лимитов"""
    console.print("\n[cyan]📧 Настройка ротации email аккаунтов[/cyan]")
    console.print("[yellow]Let's Encrypt: 300 сертификатов/3 часа на аккаунт, 10 аккаунтов/IP = 3000/3 часа[/yellow]")
    
    use_rotation = Confirm.ask(
        "Включить автоматическую ротацию email для обхода лимитов?",
        default=False
    )
    
    if not use_rotation:
        return None
    
    base_email = Prompt.ask(
        "Введите базовый email (например: no-reply@example.com)",
        default=""
    )
    
    if not base_email or "@" not in base_email:
        console.print("[red]❌ Неверный формат email[/red]")
        return None
    
    email_prefix = base_email.split("@")[0]
    email_domain = base_email.split("@")[1]
    
    num_accounts = Prompt.ask(
        "Сколько email аккаунтов использовать? (рекомендуется 3-10)",
        default="3"
    )
    
    try:
        num_accounts = int(num_accounts)
        if num_accounts < 1 or num_accounts > 10:
            console.print("[yellow]⚠ Количество аккаунтов должно быть от 1 до 10[/yellow]")
            num_accounts = min(max(num_accounts, 1), 10)
    except ValueError:
        num_accounts = 3
    
    return {
        'enabled': True,
        'base_email': base_email,
        'email_prefix': email_prefix,
        'email_domain': email_domain,
        'num_accounts': num_accounts
    }

def setup_tls_on_demand():
    """Настройка TLS on Demand для автоматического выпуска сертификатов"""
    console.print("\n[cyan]⚡ Настройка TLS on Demand[/cyan]")
    console.print("[yellow]Автоматический выпуск сертификатов при первом обращении к домену[/yellow]")
    console.print("[dim]⚠ ОПЦИОНАЛЬНО: Нужно только для 100+ доменов[/dim]")
    console.print("[dim]   Для 3-5 доменов не требуется[/dim]")
    
    use_on_demand = Confirm.ask(
        "Включить TLS on Demand? (полезно для большого количества доменов)",
        default=False
    )
    
    if not use_on_demand:
        console.print("[cyan]ℹ Пропускаем TLS on Demand (не обязательно для вашего случая)[/cyan]")
        return None
    
    console.print("\n[yellow]💡 TLS on Demand требует API endpoint для проверки доменов[/yellow]")
    console.print("[dim]Пример: http://api.example.com/check?domain=example.com[/dim]")
    console.print("[dim]API должен возвращать 200 если домен валиден[/dim]\n")
    
    api_url = Prompt.ask(
        "URL API для проверки валидности домена (или Enter чтобы пропустить)",
        default=""
    )
    
    if not api_url:
        console.print("[yellow]⚠ API URL не указан, TLS on Demand будет отключен[/yellow]")
        console.print("[cyan]ℹ Это нормально - для вашего случая не требуется[/cyan]")
        return None
    
    return {
        'enabled': True,
        'api_url': api_url
    }

def update_caddyfile_template(cloudflare_config, email_rotation, tls_on_demand):
    """Обновляет Caddyfile.template с новыми настройками"""
    template_path = Path("Caddyfile.template")
    
    if not template_path.exists():
        console.print("[red]❌ Caddyfile.template не найден![/red]")
        return False
    
    content = template_path.read_text(encoding='utf-8')
    original_content = content
    
    # Обновляем глобальную секцию
    global_section_pattern = r'(\{[^\n]*\n)(\s+email\s+\{[^}]+\}\n)?'
    
    def update_global_section(match):
        header = match.group(1)
        
        new_lines = []
        new_lines.append("    email {CADDY_EMAIL}")
        
        # Добавляем Cloudflare DNS challenge если настроен
        if cloudflare_config and cloudflare_config.get('enabled'):
            new_lines.append("    # DNS Challenge через Cloudflare для обхода лимитов Let's Encrypt")
            new_lines.append("    # Требуется установка модуля: xcaddy build --with github.com/caddy-dns/cloudflare")
        
        # Добавляем TLS on Demand если настроен
        if tls_on_demand and tls_on_demand.get('enabled'):
            new_lines.append("    # TLS on Demand - автоматический выпуск сертификатов")
            new_lines.append(f"    on_demand_tls {{")
            new_lines.append(f"        ask {tls_on_demand['api_url']}")
            new_lines.append("    }")
        
        return f"{header}{chr(10).join('    ' + line for line in new_lines)}\n"
    
    content = re.sub(global_section_pattern, update_global_section, content, flags=re.MULTILINE)
    
    # Обновляем секции доменов для использования DNS challenge
    if cloudflare_config and cloudflare_config.get('enabled'):
        # Обновляем каждую секцию домена
        domain_pattern = r'(\{[A-Z_]+\_DOMAIN\}\s+\{[^\n]*\n)(\s+reverse_proxy)'
        
        def add_dns_challenge(match):
            domain_header = match.group(1)
            reverse_proxy = match.group(2)
            
            # Добавляем DNS challenge в секцию tls
            tls_section = f"""    tls {{
        dns cloudflare {{
            env.CLOUDFLARE_API_TOKEN
        }}
    }}
"""
            return f"{domain_header}{tls_section}{reverse_proxy}"
        
        content = re.sub(domain_pattern, add_dns_challenge, content, flags=re.MULTILINE)
    
    if content != original_content:
        # Создаем резервную копию
        backup_path = template_path.with_suffix('.template.backup')
        backup_path.write_text(original_content, encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        template_path.write_text(content, encoding='utf-8')
        console.print("[green]✓ Caddyfile.template обновлен[/green]")
        return True
    else:
        console.print("[yellow]⚠ Изменений не требуется[/yellow]")
        return False

def update_env_file(cloudflare_config, email_rotation):
    """Обновляет .env файл с новыми переменными"""
    env_path = Path(".env")
    
    if not env_path.exists():
        console.print("[yellow]⚠ .env файл не найден, создайте его через setup.py[/yellow]")
        return False
    
    load_dotenv(env_path)
    content = env_path.read_text(encoding='utf-8')
    original_content = content
    
    # Добавляем Cloudflare токен если настроен
    if cloudflare_config and cloudflare_config.get('enabled'):
        if 'CLOUDFLARE_API_TOKEN' not in content:
            content += f"\n# Cloudflare DNS Challenge\nCLOUDFLARE_API_TOKEN={cloudflare_config['token']}\n"
        else:
            content = re.sub(
                r'CLOUDFLARE_API_TOKEN=.*',
                f"CLOUDFLARE_API_TOKEN={cloudflare_config['token']}",
                content
            )
    
    # Добавляем настройки ротации email
    if email_rotation and email_rotation.get('enabled'):
        if 'CADDY_EMAIL_ROTATION_ENABLED' not in content:
            content += f"\n# Ротация email для обхода лимитов Let's Encrypt\n"
            content += f"CADDY_EMAIL_ROTATION_ENABLED=true\n"
            content += f"CADDY_EMAIL_PREFIX={email_rotation['email_prefix']}\n"
            content += f"CADDY_EMAIL_DOMAIN={email_rotation['email_domain']}\n"
            content += f"CADDY_EMAIL_COUNT={email_rotation['num_accounts']}\n"
        else:
            content = re.sub(r'CADDY_EMAIL_ROTATION_ENABLED=.*', 'CADDY_EMAIL_ROTATION_ENABLED=true', content)
            content = re.sub(r'CADDY_EMAIL_PREFIX=.*', f"CADDY_EMAIL_PREFIX={email_rotation['email_prefix']}", content)
            content = re.sub(r'CADDY_EMAIL_DOMAIN=.*', f"CADDY_EMAIL_DOMAIN={email_rotation['email_domain']}", content)
            content = re.sub(r'CADDY_EMAIL_COUNT=.*', f"CADDY_EMAIL_COUNT={email_rotation['num_accounts']}", content)
    
    if content != original_content:
        # Создаем резервную копию
        backup_path = env_path.with_suffix('.env.backup')
        backup_path.write_text(original_content, encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        env_path.write_text(content, encoding='utf-8')
        console.print("[green]✓ .env файл обновлен[/green]")
        return True
    else:
        return False

def create_email_rotation_script(email_rotation):
    """Создает скрипт для автоматической ротации email"""
    if not email_rotation or not email_rotation.get('enabled'):
        return
    
    script_content = f"""#!/usr/bin/env python3
\"\"\"
Скрипт для автоматической ротации email аккаунтов в Caddy
Основано на: https://habr.com/ru/articles/923150/
\"\"\"
import requests
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Путь к файлу индекса (в директории проекта для надежности)
PROJECT_DIR = Path(__file__).parent if '__file__' in globals() else Path.cwd()
INDEX_FILE = PROJECT_DIR / ".caddy_email_index.txt"

EMAIL_PREFIX = os.getenv("CADDY_EMAIL_PREFIX", "{email_rotation['email_prefix']}")
EMAIL_DOMAIN = os.getenv("CADDY_EMAIL_DOMAIN", "{email_rotation['email_domain']}")
EMAIL_COUNT = int(os.getenv("CADDY_EMAIL_COUNT", "{email_rotation['num_accounts']}"))

# Caddy API endpoint для изменения email
# Используем более простой путь через admin API
CADDY_API_BASE = os.getenv("CADDY_API", "http://localhost:2019")

def get_current_index():
    \"\"\"Получает текущий индекс email из файла\"\"\"
    if INDEX_FILE.exists():
        try:
            return int(INDEX_FILE.read_text().strip())
        except:
            return 0
    return 0

def set_current_index(index):
    \"\"\"Сохраняет текущий индекс email в файл\"\"\"
    INDEX_FILE.write_text(str(index))

def rotate_email():
    \"\"\"Ротирует email аккаунт в Caddy\"\"\"
    current_index = get_current_index()
    next_index = (current_index + 1) % EMAIL_COUNT
    
    new_email = f"{{EMAIL_PREFIX}}{{next_index}}@{{EMAIL_DOMAIN}}"
    
    try:
        # Получаем текущую конфигурацию Caddy
        config_url = f"{{CADDY_API_BASE}}/config/"
        response = requests.get(config_url, timeout=5)
        
        if response.status_code != 200:
            print(f"[{{datetime.now()}}] ⚠ Не удалось подключиться к Caddy API (код: {{response.status_code}})")
            print(f"[{{datetime.now()}}] 💡 Убедитесь, что Caddy запущен и доступен на порту 2019")
            return False
        
        # Обновляем email в глобальной секции
        # Путь к email в конфигурации: apps.http.servers.srv0.listen[0].tls.connection_policies[0].certificates.management.issuers[0].acme.email
        email_path = "apps/http/servers/srv0/listen/0/tls/connection_policies/0/certificates/management/issuers/0/acme/email"
        
        # Пробуем обновить через PATCH
        patch_url = f"{{CADDY_API_BASE}}/config/{{email_path}}"
        patch_response = requests.patch(patch_url, json=new_email, timeout=5)
        
        if patch_response.status_code in [200, 204]:
            set_current_index(next_index)
            print(f"[{{datetime.now()}}] ✓ Email изменен на: {{new_email}}")
            return True
        else:
            # Если PATCH не работает, пробуем через PUT
            put_url = f"{{CADDY_API_BASE}}/config/{{email_path}}"
            put_response = requests.put(put_url, json=new_email, timeout=5)
            
            if put_response.status_code in [200, 204]:
                set_current_index(next_index)
                print(f"[{{datetime.now()}}] ✓ Email изменен на: {{new_email}}")
                return True
            else:
                print(f"[{{datetime.now()}}] ⚠ Ошибка при изменении email (PATCH: {{patch_response.status_code}}, PUT: {{put_response.status_code}})")
                print(f"[{{datetime.now()}}] 💡 Возможно, нужно перезапустить Caddy или проверить конфигурацию")
                return False
                
    except requests.exceptions.ConnectionError:
        print(f"[{{datetime.now()}}] ⚠ Не удалось подключиться к Caddy API")
        print(f"[{{datetime.now()}}] 💡 Убедитесь, что Caddy запущен: docker-compose ps caddy")
        return False
    except Exception as e:
        print(f"[{{datetime.now()}}] ⚠ Ошибка: {{e}}")
        return False

if __name__ == "__main__":
    rotate_email()
"""
    
    script_path = Path("caddy_rotate_email.py")
    script_path.write_text(script_content, encoding='utf-8')
    script_path.chmod(0o755)
    
    # Получаем абсолютный путь для cron
    abs_script_path = script_path.resolve()
    
    console.print(f"[green]✓ Создан скрипт ротации email: {script_path}[/green]")
    console.print(f"[green]✓ Абсолютный путь: {abs_script_path}[/green]")
    
    # Предлагаем автоматически добавить в cron
    if Confirm.ask("\n[cyan]Добавить скрипт в crontab автоматически?[/cyan]", default=True):
        import subprocess
        cron_line = f"*/20 * * * * cd {abs_script_path.parent} && /usr/bin/python3 {abs_script_path.name}\n"
        
        try:
            # Получаем текущий crontab
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=False)
            existing_crontab = result.stdout if result.returncode == 0 else ""
            
            # Проверяем, есть ли уже эта строка
            if abs_script_path.name in existing_crontab or 'caddy_rotate_email' in existing_crontab:
                console.print("[yellow]⚠ Запись уже есть в crontab[/yellow]")
            else:
                # Добавляем новую строку
                new_crontab = existing_crontab
                if new_crontab and not new_crontab.endswith('\n'):
                    new_crontab += '\n'
                new_crontab += cron_line
                
                # Устанавливаем новый crontab
                process = subprocess.run(['crontab', '-'], input=new_crontab, text=True, check=True, capture_output=True)
                console.print("[green]✓ Скрипт добавлен в crontab![/green]")
                console.print("[cyan]   Ротация email будет происходить каждые 20 минут[/cyan]")
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]⚠ Не удалось автоматически добавить в crontab: {e}[/yellow]")
            console.print("[cyan]Добавьте вручную:[/cyan]")
        except Exception as e:
            console.print(f"[yellow]⚠ Ошибка: {e}[/yellow]")
            console.print("[cyan]Добавьте вручную:[/cyan]")
    else:
        console.print("\n[cyan]💡 Добавьте в crontab вручную для автоматической ротации каждые 20 минут:[/cyan]")
    
    console.print(f"   [bold]crontab -e[/bold]")
    console.print(f"   [bold]*/20 * * * * cd {abs_script_path.parent} && /usr/bin/python3 {abs_script_path.name}[/bold]")

def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Настройка обхода лимитов Let's Encrypt в Caddy[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт поможет настроить:[/yellow]")
    console.print("1. DNS Challenge через Cloudflare (обход HTTP-01 проверки)")
    console.print("2. Ротацию email аккаунтов (300 сертификатов/3ч на аккаунт)")
    console.print("3. TLS on Demand (автоматический выпуск при первом обращении)")
    console.print("4. Fallback на ZeroSSL (автоматически в Caddy)")
    
    if not Confirm.ask("\n[cyan]Продолжить настройку?[/cyan]", default=True):
        return
    
    # Настройка компонентов
    cloudflare_config = setup_dns_challenge_cloudflare()
    email_rotation = setup_email_rotation()
    tls_on_demand = setup_tls_on_demand()
    
    # Обновляем файлы
    console.print("\n[cyan]📝 Обновление конфигурационных файлов...[/cyan]")
    
    caddyfile_updated = update_caddyfile_template(cloudflare_config, email_rotation, tls_on_demand)
    env_updated = update_env_file(cloudflare_config, email_rotation)
    
    # Создаем скрипт ротации email
    if email_rotation:
        create_email_rotation_script(email_rotation)
    
    console.print("\n[bold green]✅ Настройка завершена![/bold green]")
    
    # Показываем что настроено
    console.print("\n[cyan]📋 Что настроено:[/cyan]")
    if email_rotation and email_rotation.get('enabled'):
        console.print(f"  ✓ Ротация email: {email_rotation['num_accounts']} аккаунтов")
        console.print(f"    → До {email_rotation['num_accounts'] * 300} сертификатов/3 часа")
    else:
        console.print("  ⚠ Ротация email: не настроена")
    
    if cloudflare_config and cloudflare_config.get('enabled'):
        console.print("  ✓ Cloudflare DNS Challenge: настроен")
    else:
        console.print("  ℹ Cloudflare DNS Challenge: не настроен (не обязательно)")
    
    if tls_on_demand and tls_on_demand.get('enabled'):
        console.print("  ✓ TLS on Demand: настроен")
    else:
        console.print("  ℹ TLS on Demand: не настроен (не обязательно для вашего случая)")
    
    console.print("  ✓ ZeroSSL fallback: автоматически (встроен в Caddy)")
    
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    
    if email_rotation and email_rotation.get('enabled'):
        console.print("\n[bold yellow]1. Настройте автоматическую ротацию email:[/bold yellow]")
        script_path = Path("caddy_rotate_email.py")
        if script_path.exists():
            abs_path = script_path.resolve()
            console.print(f"   [green]crontab -e[/green]")
            console.print(f"   [green]*/20 * * * * cd {abs_path.parent} && /usr/bin/python3 {abs_path.name}[/green]")
        else:
            console.print("   Скрипт caddy_rotate_email.py должен быть создан")
    
    if cloudflare_config and cloudflare_config.get('enabled'):
        console.print("\n[bold yellow]2. Настройте Cloudflare DNS Challenge:[/bold yellow]")
        console.print("   - Установите модуль: xcaddy build --with github.com/caddy-dns/cloudflare")
        console.print("   - Или используйте образ: caddy:builder")
    
    console.print("\n[bold yellow]3. Примените изменения:[/bold yellow]")
    console.print("   [green]python3 regenerate_caddyfile.py[/green]")
    console.print("   [green]docker-compose restart caddy[/green]")
    
    console.print("\n[yellow]⚠ Важно:[/yellow]")
    console.print("- Let's Encrypt лимит: 300 сертификатов/3 часа на аккаунт")
    if email_rotation and email_rotation.get('enabled'):
        console.print(f"- С ротацией email: до {email_rotation['num_accounts'] * 300} сертификатов/3 часа")
    console.print("- Максимум 10 аккаунтов с одного IP = 3000 сертификатов/3 часа")
    console.print("- Caddy автоматически использует ZeroSSL как fallback")
    console.print("- Cloudflare DNS Challenge опционален (нужен только если используете Cloudflare)")

if __name__ == "__main__":
    main()

