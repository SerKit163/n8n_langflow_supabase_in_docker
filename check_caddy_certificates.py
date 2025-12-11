#!/usr/bin/env python3
"""
Скрипт для проверки существующих сертификатов Caddy и их использования
"""
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def run_command(cmd, description=""):
    """Выполняет команду и возвращает результат"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_certificates():
    """Проверяет существующие сертификаты в Caddy volume"""
    console.print("\n[cyan]🔍 Проверка существующих сертификатов...[/cyan]")
    
    # Проверяем, запущен ли контейнер Caddy
    success, output, _ = run_command("docker ps --filter name=caddy --format '{{.Names}}'")
    caddy_running = success and "caddy" in output
    
    if not caddy_running:
        console.print("[yellow]⚠ Контейнер Caddy не запущен, проверяем volume напрямую...[/yellow]")
        # Пытаемся проверить через docker volume inspect
        cmd = "docker volume inspect n8n_langflow_supabase_in_docker_caddy_data 2>/dev/null | grep -q Mountpoint || echo 'not found'"
        success, _, _ = run_command(cmd)
        if not success:
            console.print("[yellow]⚠ Volume caddy_data не найден[/yellow]")
            return False
    
    # Проверяем сертификаты в volume
    console.print("\n[cyan]📋 Поиск сертификатов в volume caddy_data...[/cyan]")
    
    if caddy_running:
        # Выполняем команду внутри контейнера
        cmd = "docker-compose exec -T caddy sh -c 'find /data/caddy/acme -type f -name \"*.crt\" -o -name \"*.key\" 2>/dev/null | head -20'"
    else:
        # Пытаемся через временный контейнер
        cmd = "docker run --rm -v n8n_langflow_supabase_in_docker_caddy_data:/data alpine find /data/caddy/acme -type f 2>/dev/null | head -20"
    
    success, output, error = run_command(cmd)
    
    if success and output.strip():
        console.print("[green]✓ Найдены файлы сертификатов:[/green]")
        cert_files = [line.strip() for line in output.strip().split('\n') if line.strip()]
        for cert_file in cert_files[:10]:  # Показываем первые 10
            console.print(f"  - {cert_file}")
        if len(cert_files) > 10:
            console.print(f"  ... и еще {len(cert_files) - 10} файлов")
        
        # Проверяем конкретные домены - ищем в правильных местах
        console.print("\n[cyan]🔍 Проверка сертификатов для ваших доменов...[/cyan]")
        domains_to_check = ["n8n.ai-agents-seed.ru", "langflow.ai-agents-seed.ru", "supabase.ai-agents-seed.ru"]
        
        found_any = False
        for domain in domains_to_check:
            # Caddy хранит сертификаты в разных местах, проверяем все варианты
            search_paths = [
                f"/data/caddy/acme/acme-v02.api.letsencrypt.org-directory/sites/{domain}",
                f"/data/caddy/acme/acme-v02.api.letsencrypt.org-directory/sites/*{domain.replace('.', '_')}*",
                f"/data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/{domain}",
            ]
            
            found = False
            for search_path in search_paths:
                if caddy_running:
                    check_cmd = f"docker-compose exec -T caddy sh -c 'test -d {search_path} && echo found || (ls -d {search_path} 2>/dev/null | head -1)'"
                else:
                    check_cmd = f"docker run --rm -v n8n_langflow_supabase_in_docker_caddy_data:/data alpine sh -c 'test -d /data{search_path} && echo found || (ls -d /data{search_path} 2>/dev/null | head -1)'"
                
                success, output, _ = run_command(check_cmd)
                if success and output.strip() and "found" in output:
                    console.print(f"  [green]✓ Сертификат для {domain} найден[/green]")
                    found = True
                    found_any = True
                    break
            
            if not found:
                console.print(f"  [yellow]⚠ Сертификат для {domain} не найден[/yellow]")
        
        return found_any
        
        return True
    else:
        console.print("[yellow]⚠ Сертификаты не найдены в volume[/yellow]")
        if error:
            console.print(f"[red]{error}[/red]")
        return False


def check_caddyfile_config():
    """Проверяет конфигурацию Caddyfile"""
    console.print("\n[cyan]📝 Проверка Caddyfile...[/cyan]")
    
    caddyfile_path = Path("Caddyfile")
    if not caddyfile_path.exists():
        console.print("[red]❌ Caddyfile не найден![/red]")
        return False
    
    content = caddyfile_path.read_text(encoding='utf-8')
    
    # Проверяем наличие tls internal
    if "tls internal" in content:
        console.print("[yellow]⚠ В Caddyfile используется 'tls internal' (самоподписанные сертификаты)[/yellow]")
        console.print("[cyan]💡 Caddy будет использовать самоподписанные сертификаты[/cyan]")
    else:
        console.print("[green]✓ Caddyfile настроен на автоматическое получение сертификатов[/green]")
        console.print("[cyan]💡 Caddy автоматически использует существующие сертификаты из volume, если они есть[/cyan]")
    
    return True


def show_certificate_info():
    """Показывает информацию о сертификатах"""
    console.print("\n[cyan]📊 Детальная информация о сертификатах:[/cyan]")
    
    # Проверяем домены из Caddyfile
    caddyfile_path = Path("Caddyfile")
    if caddyfile_path.exists():
        content = caddyfile_path.read_text(encoding='utf-8')
        # Ищем домены (простой парсинг)
        import re
        domains = re.findall(r'([a-zA-Z0-9.-]+\.(?:ru|com|net|org|io))', content)
        if domains:
            console.print(f"\n[cyan]Домены в Caddyfile:[/cyan]")
            for domain in set(domains):
                console.print(f"  - {domain}")
    
    # Пытаемся получить информацию о сертификатах из Caddy API
    console.print("\n[cyan]Проверка через Caddy API...[/cyan]")
    cmd = "docker-compose exec -T caddy curl -s http://localhost:2019/config/apps/http/servers 2>/dev/null | head -50"
    success, output, _ = run_command(cmd)
    
    if success and output:
        console.print("[green]✓ Caddy API доступен[/green]")
    else:
        console.print("[yellow]⚠ Не удалось получить информацию через Caddy API[/yellow]")


def main():
    """Главная функция"""
    console.print(Panel.fit(
        "[bold cyan]🔐 Проверка сертификатов Caddy[/bold cyan]",
        border_style="cyan"
    ))
    
    # Проверяем конфигурацию
    check_caddyfile_config()
    
    # Проверяем сертификаты
    has_certs = check_certificates()
    
    # Показываем детальную информацию
    show_certificate_info()
    
    # Итоговые рекомендации
    console.print("\n[bold cyan]💡 Рекомендации:[/bold cyan]")
    
    if has_certs:
        console.print("[green]✓ Сертификаты найдены в volume[/green]")
        console.print("[cyan]Caddy должен автоматически использовать существующие сертификаты[/cyan]")
        console.print("\n[yellow]Если сертификаты не работают:[/yellow]")
        console.print("1. Проверьте логи: docker-compose logs caddy")
        console.print("2. Убедитесь, что домены в Caddyfile совпадают с доменами в сертификатах")
        console.print("3. Проверьте срок действия сертификатов")
    else:
        console.print("[yellow]⚠ Сертификаты для доменов не найдены в volume[/yellow]")
        console.print("[yellow]⚠ Найдены только ключи аккаунта Let's Encrypt[/yellow]")
        console.print("\n[cyan]💡 Причина:[/cyan]")
        console.print("Rate limit Let's Encrypt достигнут - нельзя получить новые сертификаты")
        console.print("Сертификаты для доменов отсутствуют или были удалены")
        console.print("\n[bold cyan]🔧 Варианты решения:[/bold cyan]")
        console.print("\n[cyan]1. Включить прямой доступ через порты (рекомендуется сейчас):[/cyan]")
        console.print("   python3 enable_direct_ports.py")
        console.print("   docker-compose up -d")
        console.print("   # Сервисы будут доступны: http://localhost:ПОРТ")
        console.print("\n[cyan]2. Подождать сброса rate limit Let's Encrypt:[/cyan]")
        console.print("   - n8n: после 2025-12-12 06:57:11 UTC")
        console.print("   - langflow: после 2025-12-12 00:22:28 UTC")
        console.print("   - supabase: после 2025-12-12 07:09:29 UTC")
        console.print("\n[cyan]3. Использовать самоподписанные сертификаты (временно):[/cyan]")
        console.print("   # Добавьте 'tls internal' в каждый блок домена в Caddyfile")
        console.print("   # Затем: docker-compose restart caddy")
    
    console.print("\n[cyan]📌 Полезные команды:[/cyan]")
    console.print("  - Просмотр логов: docker-compose logs -f caddy")
    console.print("  - Проверка сертификатов: docker-compose exec caddy ls -la /data/caddy/acme/")
    console.print("  - Включение прямого доступа: python3 enable_direct_ports.py")


if __name__ == "__main__":
    main()

