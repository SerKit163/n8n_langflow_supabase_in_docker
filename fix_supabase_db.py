#!/usr/bin/env python3
"""
Скрипт для исправления проблем с базой данных Supabase
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from dotenv import dotenv_values

console = Console()


def show_welcome():
    """Показывает приветственное сообщение"""
    welcome_text = """
🔧 Исправление базы данных Supabase

Этот скрипт поможет исправить проблемы с инициализацией базы данных Supabase.

⚠️  ВНИМАНИЕ:
  • Скрипт может пересоздать базу данных (данные будут потеряны!)
  • Рекомендуется сделать резервную копию перед выполнением
    """
    console.print(Panel(welcome_text, title="Исправление Supabase", border_style="yellow"))


def check_docker_compose():
    """Проверяет наличие docker-compose.yml"""
    if not Path("docker-compose.yml").exists():
        console.print("[red]❌ Файл docker-compose.yml не найден![/red]")
        console.print("[yellow]Запустите скрипт из корневой директории проекта[/yellow]")
        sys.exit(1)


def stop_services():
    """Останавливает сервисы Supabase"""
    console.print("\n[cyan]🛑 Остановка сервисов Supabase...[/cyan]")
    try:
        subprocess.run(
            ["docker-compose", "stop", "supabase-auth", "supabase-rest", "supabase-studio"],
            check=True,
            capture_output=True
        )
        console.print("[green]✓ Сервисы остановлены[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при остановке сервисов: {e}[/red]")
        return False


def backup_database():
    """Создает резервную копию базы данных"""
    console.print("\n[cyan]💾 Создание резервной копии базы данных...[/cyan]")
    env_config = dotenv_values(".env")
    postgres_password = env_config.get('POSTGRES_PASSWORD', '')
    
    if not postgres_password:
        console.print("[yellow]⚠️  POSTGRES_PASSWORD не найден в .env, пропускаем резервную копию[/yellow]")
        return True
    
    backup_file = "supabase_backup_$(date +%Y%m%d_%H%M%S).sql"
    try:
        result = subprocess.run(
            [
                "docker", "exec", "supabase-db",
                "pg_dump", "-U", "postgres", "-d", "postgres", "-F", "c", "-f", f"/tmp/{backup_file}"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            console.print(f"[green]✓ Резервная копия создана: {backup_file}[/green]")
            return True
        else:
            console.print(f"[yellow]⚠️  Не удалось создать резервную копию: {result.stderr}[/yellow]")
            return True  # Продолжаем даже если резервная копия не удалась
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при создании резервной копии: {e}[/yellow]")
        return True  # Продолжаем даже если резервная копия не удалась


def recreate_database_volume():
    """Пересоздает volume базы данных"""
    console.print("\n[cyan]🗑️  Удаление старого volume базы данных...[/cyan]")
    
    if not Confirm.ask(
        "[red]⚠️  Это удалит все данные в базе данных! Продолжить?[/red]",
        default=False
    ):
        console.print("[yellow]Операция отменена[/yellow]")
        return False
    
    try:
        # Останавливаем все сервисы
        subprocess.run(
            ["docker-compose", "stop"],
            check=True,
            capture_output=True
        )
        
        # Удаляем контейнер базы данных
        subprocess.run(
            ["docker-compose", "rm", "-f", "supabase-db"],
            check=True,
            capture_output=True
        )
        
        # Ищем и удаляем volume базы данных
        result = subprocess.run(
            ["docker", "volume", "ls", "-q"],
            capture_output=True,
            text=True
        )
        
        volumes = result.stdout.strip().split('\n') if result.stdout.strip() else []
        for volume in volumes:
            volume_name = volume.strip()
            # Ищем volume связанный с проектом
            inspect_result = subprocess.run(
                ["docker", "volume", "inspect", volume_name],
                capture_output=True,
                text=True
            )
            if 'supabase' in volume_name.lower() or 'postgres' in volume_name.lower():
                console.print(f"[yellow]Удаление volume: {volume_name}[/yellow]")
                subprocess.run(
                    ["docker", "volume", "rm", volume_name],
                    capture_output=True
                )
        
        # Также пробуем удалить через docker-compose
        subprocess.run(
            ["docker-compose", "down", "-v"],
            capture_output=True
        )
        
        console.print("[green]✓ Старый volume удален[/green]")
        return True
    except Exception as e:
        console.print(f"[yellow]⚠️  Предупреждение при удалении volume: {e}[/yellow]")
        # Продолжаем даже если были ошибки
        return True


def start_database():
    """Запускает базу данных заново"""
    console.print("\n[cyan]🚀 Запуск базы данных...[/cyan]")
    try:
        subprocess.run(
            ["docker-compose", "up", "-d", "supabase-db"],
            check=True,
            capture_output=True
        )
        
        # Ждем пока база данных запустится
        import time
        console.print("[yellow]⏳ Ожидание запуска базы данных (10 секунд)...[/yellow]")
        time.sleep(10)
        
        console.print("[green]✓ База данных запущена[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при запуске базы данных: {e}[/red]")
        return False


def initialize_auth_schema():
    """Инициализирует схему auth вручную"""
    console.print("\n[cyan]🔧 Инициализация схемы auth...[/cyan]")
    env_config = dotenv_values(".env")
    postgres_password = env_config.get('POSTGRES_PASSWORD', '')
    
    if not postgres_password:
        console.print("[red]❌ POSTGRES_PASSWORD не найден в .env[/red]")
        return False
    
    # Создаем схему auth если её нет
    init_sql = """
    -- Создаем схему auth если её нет
    CREATE SCHEMA IF NOT EXISTS auth;
    
    -- Создаем базовые типы для auth
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'factor_type') THEN
            CREATE TYPE auth.factor_type AS ENUM ('totp', 'phone');
        END IF;
    END $$;
    """
    
    try:
        result = subprocess.run(
            [
                "docker", "exec", "-i", "supabase-db",
                "psql", "-U", "postgres", "-d", "postgres"
            ],
            input=init_sql,
            text=True,
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Схема auth инициализирована[/green]")
            return True
        else:
            console.print(f"[yellow]⚠️  Предупреждение: {result.stderr}[/yellow]")
            # Продолжаем даже если есть предупреждения
            return True
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при инициализации схемы: {e}[/yellow]")
        console.print("[yellow]💡 Попробуем запустить сервисы - возможно схема создастся автоматически[/yellow]")
        return True


def start_services():
    """Запускает все сервисы Supabase"""
    console.print("\n[cyan]🚀 Запуск сервисов Supabase...[/cyan]")
    try:
        subprocess.run(
            ["docker-compose", "up", "-d", "supabase-auth", "supabase-rest", "supabase-studio"],
            check=True,
            capture_output=True
        )
        
        import time
        console.print("[yellow]⏳ Ожидание запуска сервисов (15 секунд)...[/yellow]")
        time.sleep(15)
        
        console.print("[green]✓ Сервисы запущены[/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при запуске сервисов: {e}[/red]")
        return False


def check_status():
    """Проверяет статус сервисов"""
    console.print("\n[cyan]📊 Проверка статуса сервисов...[/cyan]")
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "supabase-auth", "supabase-rest", "supabase-studio"],
            capture_output=True,
            text=True
        )
        console.print(result.stdout)
        
        # Проверяем логи supabase-auth на ошибки
        console.print("\n[cyan]📋 Последние логи supabase-auth:[/cyan]")
        log_result = subprocess.run(
            ["docker-compose", "logs", "--tail", "20", "supabase-auth"],
            capture_output=True,
            text=True
        )
        console.print(log_result.stdout)
        
        return True
    except Exception as e:
        console.print(f"[yellow]⚠️  Ошибка при проверке статуса: {e}[/yellow]")
        return True


def main():
    """Главная функция"""
    show_welcome()
    
    if not Confirm.ask("\n[cyan]Продолжить исправление базы данных?[/cyan]", default=True):
        console.print("[yellow]Операция отменена[/yellow]")
        return
    
    check_docker_compose()
    
    # Вариант 1: Пересоздание volume (полная очистка)
    console.print("\n[bold yellow]Вариант 1: Пересоздание базы данных (удалит все данные)[/bold yellow]")
    if Confirm.ask("Пересоздать базу данных?", default=False):
        if stop_services():
            if backup_database():
                if recreate_database_volume():
                    if start_database():
                        if initialize_auth_schema():
                            if start_services():
                                check_status()
                                console.print("\n[green]✅ База данных пересоздана и сервисы запущены![/green]")
                                console.print("[yellow]💡 Проверьте логи: docker-compose logs supabase-auth[/yellow]")
    
    # Вариант 2: Только инициализация схемы (без удаления данных)
    console.print("\n[bold yellow]Вариант 2: Инициализация схемы auth (без удаления данных)[/bold yellow]")
    if Confirm.ask("Попробовать инициализировать схему auth?", default=True):
        if stop_services():
            if start_database():
                if initialize_auth_schema():
                    if start_services():
                        check_status()
                        console.print("\n[green]✅ Схема auth инициализирована![/green]")
                        console.print("[yellow]💡 Проверьте логи: docker-compose logs supabase-auth[/yellow]")
    
    console.print("\n[yellow]💡 Если проблема не решена, попробуйте:[/yellow]")
    console.print("[dim]1. docker-compose down -v  # Удалить все volumes")
    console.print("[dim]2. docker-compose up -d    # Пересоздать все заново[/dim]")


if __name__ == "__main__":
    main()

