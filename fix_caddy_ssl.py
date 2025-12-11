#!/usr/bin/env python3
"""
Скрипт для исправления проблем с SSL сертификатами в Caddy
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()


def run_command(cmd, description):
    """Выполняет команду и выводит результат"""
    console.print(f"\n[cyan]▶ {description}...[/cyan]")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            console.print(f"[green]✓ {description} - успешно[/green]")
            if result.stdout:
                console.print(result.stdout)
            return True
        else:
            console.print(f"[yellow]⚠ {description} - код возврата: {result.returncode}[/yellow]")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        return False


def check_dns_and_email():
    """Проверяет DNS и email настройки (на основе рекомендаций из проекта lisa)"""
    console.print("\n[cyan]🔍 Проверка настроек...[/cyan]")
    
    # Проверяем .env файл
    env_path = Path(".env")
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        import os
        
        email = os.getenv("LETSENCRYPT_EMAIL", "")
        if not email or email == "":
            console.print("[yellow]⚠ Email для Let's Encrypt не установлен в .env[/yellow]")
        elif "@" not in email or email.count("@") != 1:
            console.print("[red]❌ Email для Let's Encrypt выглядит неверно: {email}[/red]")
            console.print("[yellow]💡 ВАЖНО: Используйте настоящий email адрес![/yellow]")
            console.print("[yellow]💡 Let's Encrypt не принимает фейковые email (например, test@test.test)[/yellow]")
        else:
            console.print(f"[green]✓ Email настроен: {email}[/green]")
    else:
        console.print("[yellow]⚠ Файл .env не найден[/yellow]")
    
    console.print("\n[cyan]💡 Рекомендации из проекта lisa:[/cyan]")
    console.print("1. Проверьте DNS — A-записи должны указывать на ваш сервер")
    console.print("2. Убедитесь, что email в .env настоящий (не фейковый)")
    console.print("3. Проверьте, что порты 80 и 443 открыты")


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔧 Исправление проблем с SSL в Caddy[/bold cyan]",
        border_style="cyan"
    ))
    
    # Проверяем настройки перед началом
    check_dns_and_email()
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Остановит Caddy")
    console.print("2. Очистит старые сертификаты (которые вызывают ошибки)")
    console.print("3. Перегенерирует Caddyfile с правильными настройками")
    console.print("4. Перезапустит Caddy")
    
    if not console.input("\n[cyan]Продолжить? (y/n): [/cyan]").lower().startswith('y'):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # 1. Останавливаем Caddy
    run_command("docker-compose stop caddy", "Остановка Caddy")
    
    # 2. Очищаем старые проблемные сертификаты из volume
    console.print("\n[cyan]🧹 Очистка проблемных сертификатов...[/cyan]")
    console.print("[yellow]⚠ Это удалит старые сертификаты, Caddy получит новые от Let's Encrypt[/yellow]")
    if console.input("[cyan]Продолжить очистку? (y/n): [/cyan]").lower().startswith('y'):
        run_command(
            "docker-compose run --rm caddy sh -c 'rm -rf /data/caddy/acme/*'",
            "Очистка кеша ACME сертификатов"
        )
    else:
        console.print("[yellow]Очистка пропущена[/yellow]")
    
    # 3. Перегенерируем Caddyfile
    console.print("\n[cyan]📝 Перегенерация Caddyfile...[/cyan]")
    try:
        from regenerate_caddyfile import load_config_from_env, main as regenerate_main
        regenerate_main()
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось использовать regenerate_caddyfile.py: {e}[/yellow]")
        console.print("[cyan]Продолжаем без перегенерации...[/cyan]")
    
    # 4. Перезапускаем Caddy
    run_command("docker-compose up -d caddy", "Запуск Caddy")
    
    # 5. Проверяем логи
    console.print("\n[cyan]📋 Проверка логов Caddy (последние 20 строк)...[/cyan]")
    run_command("docker-compose logs --tail=20 caddy", "Логи Caddy")
    
    console.print("\n[bold green]✅ Готово![/bold green]")
    console.print("\n[cyan]💡 Следующие шаги (на основе рекомендаций проекта lisa):[/cyan]")
    console.print("1. Проверьте логи: docker-compose logs -f caddy")
    console.print("2. Проверьте DNS — A-записи должны указывать на ваш сервер")
    console.print("3. Очистите DNS кэш на клиенте:")
    console.print("   - Mac: sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder")
    console.print("   - Linux: sudo systemd-resolve --flush-caches")
    console.print("   - Windows: ipconfig /flushdns")
    console.print("4. Подождите 1-2 минуты, пока Caddy получит сертификаты от Let's Encrypt")
    console.print("5. Проверьте логи: docker-compose logs -f caddy")
    console.print("6. Попробуйте открыть сайт в браузере")
    console.print("7. Если Caddy не может получить сертификат из-за rate limit, подождите несколько часов")
    console.print("\n[yellow]⚠ Если проблема сохраняется:[/yellow]")
    console.print("- Убедитесь, что email в .env настоящий (не фейковый)")
    console.print("- Проверьте, что порты 80 и 443 открыты на сервере")
    console.print("- Убедитесь, что DNS записи правильно настроены")


if __name__ == "__main__":
    main()

