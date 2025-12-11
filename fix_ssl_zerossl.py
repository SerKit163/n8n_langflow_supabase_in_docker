#!/usr/bin/env python3
"""
Быстрое исправление SSL проблем через ZeroSSL
Объединяет все необходимые шаги в один скрипт
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

console = Console()


def run_command(cmd: list, description: str, check: bool = False) -> bool:
    """Выполняет команду"""
    console.print(f"\n[cyan]▶ {description}...[/cyan]")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        if result.returncode == 0:
            console.print(f"[green]✓ {description} - успешно[/green]")
            if result.stdout:
                console.print(result.stdout[:500])  # Показываем первые 500 символов
            return True
        else:
            console.print(f"[yellow]⚠ {description} - код: {result.returncode}[/yellow]")
            if result.stderr:
                console.print(result.stderr[:500])
            return False
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        return False


def main():
    """Главная функция - быстрое исправление SSL"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Быстрое исправление SSL через ZeroSSL[/bold cyan]",
        border_style="cyan"
    ))
    
    console.print("\n[yellow]Этот скрипт:[/yellow]")
    console.print("1. Переключит Caddy на ZeroSSL (без лимитов)")
    console.print("2. Очистит старые проблемные сертификаты")
    console.print("3. Перегенерирует Caddyfile")
    console.print("4. Перезапустит Caddy")
    
    console.print("\n[green]✓ ZeroSSL - бесплатная альтернатива Let's Encrypt[/green]")
    console.print("  • Нет лимита 5 сертификатов/7 дней")
    console.print("  • Более мягкие ограничения")
    console.print("  • Работает так же надежно")
    
    if not console.input("\n[cyan]Продолжить? (y/n): [/cyan]").lower().startswith('y'):
        console.print("[yellow]Отменено[/yellow]")
        return
    
    # 1. Переключаем на ZeroSSL
    console.print("\n[bold cyan]Шаг 1: Переключение на ZeroSSL[/bold cyan]")
    try:
        from switch_to_zerossl import switch_caddyfile_to_zerossl, clear_old_certificates, regenerate_caddyfile
        
        if switch_caddyfile_to_zerossl():
            console.print("[green]✓ Переключено на ZeroSSL[/green]")
        else:
            console.print("[yellow]⚠ ZeroSSL уже настроен или ошибка[/yellow]")
    except ImportError:
        console.print("[yellow]⚠ Не удалось импортировать switch_to_zerossl.py[/yellow]")
        console.print("[cyan]💡 Убедитесь, что файл существует[/cyan]")
        return
    
    # 2. Перегенерируем Caddyfile
    console.print("\n[bold cyan]Шаг 2: Перегенерация Caddyfile[/bold cyan]")
    if regenerate_caddyfile():
        console.print("[green]✓ Caddyfile перегенерирован[/green]")
    else:
        console.print("[yellow]⚠ Не удалось перегенерировать Caddyfile[/yellow]")
        console.print("[cyan]💡 Попробуйте: python3 regenerate_caddyfile.py[/cyan]")
    
    # 3. Очищаем старые сертификаты
    console.print("\n[bold cyan]Шаг 3: Очистка старых сертификатов[/bold cyan]")
    clear_old_certificates()
    
    # 4. Перезапускаем Caddy
    console.print("\n[bold cyan]Шаг 4: Перезапуск Caddy[/bold cyan]")
    run_command(
        ['docker-compose', 'restart', 'caddy'],
        "Перезапуск Caddy"
    )
    
    # 5. Показываем логи
    console.print("\n[bold cyan]Шаг 5: Проверка логов[/bold cyan]")
    console.print("[cyan]💡 Показываю последние 30 строк логов Caddy...[/cyan]")
    run_command(
        ['docker-compose', 'logs', '--tail=30', 'caddy'],
        "Логи Caddy",
        check=False
    )
    
    console.print("\n[bold green]✅ Готово![/bold green]")
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    console.print("1. Подождите 1-2 минуты для получения новых сертификатов")
    console.print("2. Проверьте логи: docker-compose logs -f caddy")
    console.print("3. Попробуйте открыть ваш домен в браузере")
    console.print("\n[yellow]⚠ Если проблемы сохраняются:[/yellow]")
    console.print("- Проверьте DNS записи (A-записи должны указывать на ваш IP)")
    console.print("- Убедитесь, что порты 80 и 443 открыты")
    console.print("- Очистите DNS кэш: ipconfig /flushdns (Windows) или sudo systemd-resolve --flush-caches (Linux)")


if __name__ == "__main__":
    main()

