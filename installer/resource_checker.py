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
    # Используем общую RAM VPS, а не доступную в данный момент
    # так как Docker будет использовать лимиты, а не всю доступную RAM
    summary = get_resource_summary(config)
    required_ram = summary['total_memory_gb']
    total_ram = hardware['ram']['total_gb']
    available_ram = hardware['ram']['available_gb']
    
    # Небольшая погрешность для сравнения чисел с плавающей точкой (0.1 GB)
    # Это позволяет избежать ложных срабатываний из-за округления
    epsilon = 0.1
    
    # Проверяем только минимальные требования (без запаса)
    # Критическая ошибка только если требуемая RAM строго превышает общую RAM VPS
    if required_ram > total_ram + epsilon:
        errors.append(
            f"❌ Недостаточно RAM на VPS!\n"
            f"   Требуется: {required_ram:.1f} GB\n"
            f"   Всего на VPS: {total_ram:.1f} GB\n"
            f"   Необходимо увеличить RAM VPS на: {required_ram - total_ram:.1f} GB"
        )
    else:
        # Мягкие рекомендации (не блокирующие установку)
        # Рекомендуем иметь запас, но не требуем его
        if total_ram < 8:
            warnings.append(
                f"💡 Рекомендация: для комфортной работы рекомендуется минимум 8 GB RAM\n"
                f"   Текущая RAM: {total_ram:.1f} GB\n"
                f"   Требуется для сервисов: {required_ram:.1f} GB\n"
                f"   Установка возможна, но некоторые сервисы могут работать медленнее"
            )
        elif required_ram > total_ram * 0.8:
            # Если используется более 80% RAM, мягко рекомендуем увеличить
            warnings.append(
                f"💡 Рекомендация: для оптимальной работы рекомендуется увеличить RAM\n"
                f"   Текущая RAM: {total_ram:.1f} GB\n"
                f"   Требуется для сервисов: {required_ram:.1f} GB ({required_ram/total_ram*100:.0f}%)\n"
                f"   Рекомендуется иметь запас 1-2 GB для системы"
            )
    
    # Проверка диска (учитываем только выбранные сервисы)
    # Базовые требования: 5GB для Supabase + по 3GB на каждый дополнительный сервис
    n8n_enabled = config.get('n8n_enabled', True)
    langflow_enabled = config.get('langflow_enabled', True)
    ollama_enabled = config.get('ollama_enabled', False)
    
    # Supabase всегда включен (5GB)
    required_disk = 5
    if n8n_enabled:
        required_disk += 3
    if langflow_enabled:
        required_disk += 3
    if ollama_enabled:
        required_disk += 5  # Ollama требует больше места для моделей
    
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

