#!/usr/bin/env python3
"""
Скрипт для переключения Caddy на ZeroSSL вместо Let's Encrypt
ZeroSSL - бесплатная альтернатива без строгих лимитов
"""
import os
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from dotenv import load_dotenv

console = Console()


def get_project_root() -> Path:
    """Возвращает корневую директорию проекта"""
    return Path(__file__).parent


def switch_caddyfile_to_zerossl():
    """Переключает Caddyfile на использование ZeroSSL"""
    caddyfile_path = get_project_root() / "Caddyfile"
    caddyfile_template_path = get_project_root() / "Caddyfile.template"
    
    # Проверяем наличие файлов
    if not caddyfile_path.exists() and not caddyfile_template_path.exists():
        console.print("[red]❌ Caddyfile или Caddyfile.template не найдены![/red]")
        console.print("[yellow]💡 Сначала запустите setup.py для генерации конфигурации[/yellow]")
        return False
    
    # Работаем с шаблоном (основной файл)
    target_file = caddyfile_template_path if caddyfile_template_path.exists() else caddyfile_path
    
    content = target_file.read_text(encoding='utf-8')
    original_content = content
    
    # Проверяем, уже ли используется ZeroSSL
    if 'acme.zerossl.com' in content or 'zerossl' in content.lower():
        console.print("[yellow]⚠ ZeroSSL уже настроен в Caddyfile[/yellow]")
        if not Confirm.ask("Переключить обратно на Let's Encrypt?", default=False):
            return False
        # Удаляем ZeroSSL настройки
        content = re.sub(r'\s+acme_ca\s+https://acme\.zerossl\.com/v2/DV90\n?', '', content)
        content = re.sub(r'\s+# ZeroSSL.*?\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\s+# Переключено на ZeroSSL.*?\n', '', content, flags=re.MULTILINE)
        # Добавляем комментарий про Let's Encrypt
        content = re.sub(
            r'(\{\s*\n\s*email\s+\{[^}]+\})',
            r'\1\n    # Caddy автоматически получает сертификаты от Let\'s Encrypt',
            content
        )
    else:
        # Переключаем на ZeroSSL
        console.print("[cyan]🔄 Переключение на ZeroSSL...[/cyan]")
        
        # Заменяем или добавляем acme_ca для ZeroSSL
        # Ищем глобальный блок { ... }
        global_block_pattern = r'(\{\s*\n)(\s*email\s+\{[^}]+\}\s*\n?)(.*?)(\})'
        
        def add_zerossl(match):
            header = match.group(1)  # "{\n"
            email_line = match.group(2)  # "    email {CADDY_EMAIL}\n"
            rest = match.group(3)  # остальное содержимое
            footer = match.group(4)  # "}"
            
            # Проверяем, есть ли уже acme_ca
            if 'acme_ca' in rest:
                # Заменяем существующий acme_ca на ZeroSSL
                rest = re.sub(
                    r'\s+acme_ca\s+[^\n]+\n?',
                    '    acme_ca https://acme.zerossl.com/v2/DV90\n',
                    rest
                )
            else:
                # Добавляем acme_ca после email
                rest = '    acme_ca https://acme.zerossl.com/v2/DV90\n' + rest
            
            # Добавляем комментарий
            if '# ZeroSSL' not in rest and '# Переключено на ZeroSSL' not in rest:
                rest = '    # ZeroSSL - бесплатная альтернатива Let\'s Encrypt без строгих лимитов\n' + rest
            
            return f"{header}{email_line}{rest}{footer}"
        
        content = re.sub(global_block_pattern, add_zerossl, content, flags=re.DOTALL)
    
    if content != original_content:
        # Создаем резервную копию
        backup_path = target_file.with_suffix(target_file.suffix + '.backup')
        backup_path.write_text(original_content, encoding='utf-8')
        console.print(f"[cyan]📋 Создана резервная копия: {backup_path.name}[/cyan]")
        
        # Сохраняем изменения
        target_file.write_text(content, encoding='utf-8')
        console.print(f"[green]✓ {target_file.name} обновлен[/green]")
        return True
    else:
        console.print("[yellow]⚠ Изменений не требуется[/yellow]")
        return False


def clear_old_certificates():
    """Очищает старые сертификаты Let's Encrypt"""
    console.print("\n[cyan]🧹 Очистка старых сертификатов...[/cyan]")
    
    if not Confirm.ask("Очистить старые сертификаты Let's Encrypt из Caddy?", default=True):
        return False
    
    try:
        import subprocess
        
        # Останавливаем Caddy
        console.print("   Остановка Caddy...")
        subprocess.run(
            ['docker-compose', 'stop', 'caddy'],
            capture_output=True,
            check=False
        )
        
        # Очищаем старые сертификаты
        console.print("   Удаление старых сертификатов...")
        result = subprocess.run(
            ['docker-compose', 'run', '--rm', 'caddy', 'sh', '-c', 'rm -rf /data/caddy/acme/*'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Старые сертификаты удалены[/green]")
            return True
        else:
            console.print("[yellow]⚠ Не удалось удалить сертификаты (возможно, их нет)[/yellow]")
            return False
    except Exception as e:
        console.print(f"[yellow]⚠ Ошибка при очистке сертификатов: {e}[/yellow]")
        return False


def regenerate_caddyfile():
    """Перегенерирует Caddyfile из шаблона"""
    console.print("\n[cyan]📝 Перегенерация Caddyfile...[/cyan]")
    
    try:
        from regenerate_caddyfile import main as regenerate_main
        regenerate_main()
        return True
    except ImportError:
        try:
            from installer.config_generator import generate_caddyfile
            from dotenv import load_dotenv
            import os
            
            load_dotenv()
            
            # Загружаем конфигурацию из .env
            config = {
                'routing_mode': os.getenv('ROUTING_MODE', ''),
                'letsencrypt_email': os.getenv('LETSENCRYPT_EMAIL', ''),
                'n8n_enabled': os.getenv('N8N_ENABLED', 'false').lower() == 'true',
                'langflow_enabled': os.getenv('LANGFLOW_ENABLED', 'false').lower() == 'true',
                'ollama_enabled': os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true',
                'n8n_domain': os.getenv('N8N_DOMAIN', ''),
                'langflow_domain': os.getenv('LANGFLOW_DOMAIN', ''),
                'supabase_domain': os.getenv('SUPABASE_DOMAIN', ''),
                'ollama_domain': os.getenv('OLLAMA_DOMAIN', ''),
                'supabase_admin_login': os.getenv('SUPABASE_ADMIN_LOGIN', 'admin'),
                'supabase_admin_password_hash': os.getenv('SUPABASE_ADMIN_PASSWORD_HASH', ''),
            }
            
            generate_caddyfile(config)
            console.print("[green]✓ Caddyfile перегенерирован[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠ Не удалось перегенерировать Caddyfile: {e}[/yellow]")
            return False


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Переключение на ZeroSSL[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]ZeroSSL - бесплатная альтернатива Let's Encrypt:[/yellow]")
    console.print("  ✓ Без строгих лимитов на количество сертификатов")
    console.print("  ✓ Бесплатные SSL сертификаты")
    console.print("  ✓ Поддерживается Caddy автоматически")
    console.print("  ✓ Не требует дополнительных настроек")
    
    console.print("\n[cyan]💡 Преимущества ZeroSSL:[/cyan]")
    console.print("  • Нет лимита 5 сертификатов/7 дней на домен")
    console.print("  • Более мягкие ограничения на количество запросов")
    console.print("  • Работает так же надежно как Let's Encrypt")
    
    if not Confirm.ask("\n[cyan]Переключить Caddy на ZeroSSL?[/cyan]", default=True):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # 1. Переключаем Caddyfile на ZeroSSL
    if not switch_caddyfile_to_zerossl():
        console.print("[yellow]⚠ Не удалось обновить Caddyfile[/yellow]")
        return
    
    # 2. Перегенерируем Caddyfile из шаблона (если нужно)
    if Confirm.ask("\n[cyan]Перегенерировать Caddyfile из шаблона?[/cyan]", default=True):
        regenerate_caddyfile()
    
    # 3. Очищаем старые сертификаты
    clear_old_certificates()
    
    # 4. Перезапускаем Caddy
    console.print("\n[cyan]🔄 Перезапуск Caddy...[/cyan]")
    try:
        import subprocess
        result = subprocess.run(
            ['docker-compose', 'restart', 'caddy'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Caddy перезапущен[/green]")
        else:
            console.print("[yellow]⚠ Не удалось перезапустить Caddy автоматически[/yellow]")
            console.print("[cyan]💡 Запустите вручную: docker-compose restart caddy[/cyan]")
    except Exception as e:
        console.print(f"[yellow]⚠ Ошибка при перезапуске Caddy: {e}[/yellow]")
        console.print("[cyan]💡 Запустите вручную: docker-compose restart caddy[/cyan]")
    
    console.print("\n[bold green]✅ Переключение на ZeroSSL завершено![/bold green]")
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    console.print("1. Проверьте логи: docker-compose logs -f caddy")
    console.print("2. Дождитесь получения новых сертификатов (может занять 1-2 минуты)")
    console.print("3. Попробуйте открыть ваш домен в браузере")
    console.print("\n[yellow]⚠ Если проблемы сохраняются:[/yellow]")
    console.print("- Убедитесь, что DNS записи правильно настроены")
    console.print("- Проверьте, что порты 80 и 443 открыты")
    console.print("- Очистите DNS кэш на клиенте")


if __name__ == "__main__":
    main()

