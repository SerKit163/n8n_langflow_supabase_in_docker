#!/usr/bin/env python3
"""
Скрипт для перегенерации Caddyfile из текущей конфигурации .env
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from installer.config_generator import generate_caddyfile

console = Console()


def load_config_from_env() -> dict:
    """Загружает конфигурацию из .env файла"""
    env_path = project_root / ".env"
    
    if not env_path.exists():
        console.print("[red]❌ Файл .env не найден![/red]")
        console.print(f"   Ожидаемый путь: {env_path}")
        sys.exit(1)
    
    # Загружаем переменные окружения
    load_dotenv(env_path)
    
    # Читаем .env файл для получения всех значений
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # Преобразуем в формат конфигурации
    config = {
        'routing_mode': env_vars.get('ROUTING_MODE', ''),
        'letsencrypt_email': env_vars.get('LETSENCRYPT_EMAIL', ''),
        'n8n_enabled': env_vars.get('N8N_ENABLED', 'true').lower() == 'true',
        'langflow_enabled': env_vars.get('LANGFLOW_ENABLED', 'true').lower() == 'true',
        'ollama_enabled': env_vars.get('OLLAMA_ENABLED', 'false').lower() == 'true',
        'n8n_domain': env_vars.get('N8N_DOMAIN', ''),
        'langflow_domain': env_vars.get('LANGFLOW_DOMAIN', ''),
        'supabase_domain': env_vars.get('SUPABASE_DOMAIN', ''),
        'ollama_domain': env_vars.get('OLLAMA_DOMAIN', ''),
        'supabase_admin_login': env_vars.get('SUPABASE_ADMIN_LOGIN', 'admin'),
        'supabase_admin_password_hash': env_vars.get('SUPABASE_ADMIN_PASSWORD_HASH', ''),
    }
    
    return config


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔄 Перегенерация Caddyfile[/bold cyan]",
        border_style="cyan"
    ))
    
    try:
        # Загружаем конфигурацию из .env
        console.print("\n[cyan]📖 Загрузка конфигурации из .env...[/cyan]")
        config = load_config_from_env()
        
        # Генерируем Caddyfile
        console.print("[cyan]📝 Генерация Caddyfile...[/cyan]")
        generate_caddyfile(config, output_path="Caddyfile")
        console.print("[green]✓ Caddyfile перегенерирован[/green]")
        
        # Перезапускаем Caddy
        console.print("\n[cyan]🔄 Перезапуск Caddy...[/cyan]")
        import subprocess
        result = subprocess.run(
            ["docker-compose", "restart", "caddy"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Caddy перезапущен[/green]")
            console.print("\n[bold green]✅ Готово![/bold green]")
            console.print("\n[cyan]💡 Проверьте логи Caddy:[/cyan]")
            console.print("   docker-compose logs -f caddy")
        else:
            console.print("[yellow]⚠ Не удалось перезапустить Caddy автоматически[/yellow]")
            console.print("[cyan]💡 Перезапустите вручную:[/cyan]")
            console.print("   docker-compose restart caddy")
            
    except Exception as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

