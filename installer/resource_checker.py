"""
Модуль проверки ресурсов перед установкой
"""
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from installer.config_adaptor import get_resource_summary

console = Console()


def check_resources(hardware: Dict, config: Dict) -> tuple[bool, List[str], List[str]]:
    """
    Проверяет достаточно ли ресурсов для установки
    
    Returns:
        (can_proceed, errors, warnings)
    """
    errors = []
    warnings = []
    
    # Проверка RAM
    summary = get_resource_summary(config)
    required_ram = summary['total_memory_gb']
    available_ram = hardware['ram']['available_gb']
    
    if required_ram > available_ram:
        errors.append(
            f"❌ Недостаточно RAM!\n"
            f"   Требуется: {required_ram:.1f} GB\n"
            f"   Доступно: {available_ram:.1f} GB\n"
            f"   Необходимо освободить: {required_ram - available_ram:.1f} GB"
        )
    elif required_ram > available_ram * 0.9:
        warnings.append(
            f"⚠ Мало свободной RAM!\n"
            f"   Требуется: {required_ram:.1f} GB\n"
            f"   Доступно: {available_ram:.1f} GB\n"
            f"   Рекомендуется иметь запас минимум 2 GB"
        )
    
    # Проверка диска
    required_disk = 20  # Минимум для всех сервисов
    free_disk = hardware['disk']['free_gb']
    
    if free_disk < required_disk:
        errors.append(
            f"❌ Недостаточно места на диске!\n"
            f"   Требуется: {required_disk} GB\n"
            f"   Доступно: {free_disk:.1f} GB\n"
            f"   Необходимо освободить: {required_disk - free_disk:.1f} GB"
        )
    elif free_disk < required_disk * 1.5:
        warnings.append(
            f"⚠ Мало места на диске!\n"
            f"   Доступно: {free_disk:.1f} GB\n"
            f"   Рекомендуется минимум {required_disk * 1.5:.0f} GB для комфортной работы"
        )
    
    # Проверка CPU
    required_cpu = summary['total_cpu_cores']
    available_cores = hardware['cpu']['cores']
    
    if required_cpu > available_cores:
        warnings.append(
            f"⚠ Может не хватить CPU!\n"
            f"   Требуется: {required_cpu:.1f} ядер\n"
            f"   Доступно: {available_cores} ядер"
        )
    
    # Общие предупреждения
    if hardware['ram']['total_gb'] < 8:
        warnings.append(
            "⚠ Мало RAM - некоторые сервисы могут работать медленно\n"
            "   Рекомендуется минимум 8 GB для комфортной работы"
        )
    
    can_proceed = len(errors) == 0
    
    return can_proceed, errors, warnings


def display_resource_check(hardware: Dict, config: Dict) -> bool:
    """
    Отображает проверку ресурсов и возвращает можно ли продолжить
    """
    can_proceed, errors, warnings = check_resources(hardware, config)
    
    # Показываем ошибки
    if errors:
        console.print("\n[red]❌ Критические ошибки:[/red]")
        for error in errors:
            console.print(Panel(error, border_style="red"))
    
    # Показываем предупреждения
    if warnings:
        console.print("\n[yellow]⚠ Предупреждения:[/yellow]")
        for warning in warnings:
            console.print(Panel(warning, border_style="yellow"))
    
    # Показываем сводку
    summary = get_resource_summary(config)
    console.print("\n[cyan]📊 Сводка по ресурсам:[/cyan]")
    console.print(f"  CPU: {summary['total_cpu_cores']:.1f} ядер")
    console.print(f"  RAM: {summary['total_memory_gb']:.1f} GB")
    console.print(f"  Сервисов: {summary['services_count']}")
    
    return can_proceed

