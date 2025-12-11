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


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔧 Исправление проблем с SSL в Caddy[/bold cyan]",
        border_style="cyan"
    ))
    
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
    
    # 2. Очищаем старые сертификаты из volume (только проблемные)
    console.print("\n[cyan]🧹 Очистка проблемных сертификатов...[/cyan]")
    run_command(
        "docker-compose run --rm caddy sh -c 'rm -rf /data/caddy/acme/*'",
        "Очистка кеша ACME сертификатов"
    )
    
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
    console.print("\n[cyan]💡 Следующие шаги:[/cyan]")
    console.print("1. Проверьте логи: docker-compose logs -f caddy")
    console.print("2. Попробуйте открыть сайт в браузере")
    console.print("3. Если браузер показывает предупреждение о сертификате - это нормально для самоподписанных сертификатов")
    console.print("4. Нажмите 'Advanced' → 'Proceed to site' в браузере")


if __name__ == "__main__":
    main()

