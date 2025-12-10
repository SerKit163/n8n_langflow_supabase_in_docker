"""
Модуль адаптации конфигурации под доступное железо
"""
from typing import Dict
from installer.hardware_detector import detect_hardware


def adapt_config_for_hardware(hardware_info: Dict) -> Dict:
    """
    Адаптирует настройки под доступное железо
    
    Args:
        hardware_info: Информация о железе из hardware_detector
        
    Returns:
        Словарь с рекомендуемыми настройками
    """
    cpu_cores = hardware_info['cpu']['cores']
    total_ram = hardware_info['ram']['total_gb']
    # Для Ollama нужна NVIDIA GPU с CUDA, не просто любая GPU
    has_gpu = hardware_info['gpu']['available'] and hardware_info['gpu'].get('cuda_available', False)
    
    # Базовые лимиты CPU (в долях от общего количества ядер)
    config = {
        'cpu_limits': {
            'n8n': max(0.25, min(0.5, cpu_cores * 0.1)),
            'langflow': max(0.25, min(0.5, cpu_cores * 0.1)),
            'supabase': max(0.2, min(0.3, cpu_cores * 0.05)),
            'ollama': min(1.0, cpu_cores * 0.5) if has_gpu else 0
        },
        'memory_limits': {
            'n8n': calculate_memory_limit(total_ram, 0.2, min_val=1, max_val=4),
            # Langflow: минимум 3GB, оптимально 40% от RAM, максимум 8GB
            # Для 6GB RAM это даст 2.4GB, но минимум 3GB, так что будет 3GB
            # Для 8GB RAM это даст 3.2GB
            'langflow': calculate_memory_limit(total_ram, 0.4, min_val=3, max_val=8),
            'supabase': calculate_memory_limit(total_ram, 0.1, min_val=0.5, max_val=2),
            'ollama': calculate_memory_limit(total_ram, 0.4, min_val=2, max_val=8) if has_gpu else 0
        },
        'use_gpu': has_gpu,
        'ollama_recommended': has_gpu and total_ram >= 8,
        'ollama_image': 'ollama/ollama:latest-gpu' if has_gpu else 'ollama/ollama:latest',
        'gpu_devices': hardware_info['gpu'].get('devices', []) if has_gpu else []
    }
    
    # Предупреждения
    warnings = []
    errors = []
    
    # Проверка минимальных требований
    if total_ram < 4:
        errors.append("Недостаточно RAM! Минимум 4 GB")
    elif total_ram < 8:
        warnings.append("Мало RAM (меньше 8 GB) - некоторые сервисы могут работать медленно")
    
    # Специальные предупреждения для Langflow
    langflow_memory = config['memory_limits']['langflow']
    if total_ram < 8:
        warnings.append(
            f"⚠️  Langflow требует много памяти для работы с ИИ агентами! "
            f"Рекомендуется минимум 8GB RAM. "
            f"Текущий лимит: {langflow_memory}GB из {total_ram}GB доступных. "
            f"При создании сложных агентов память может увеличиться до 4-6GB."
        )
    if langflow_memory < 3:
        warnings.append(
            f"⚠️  Лимит памяти для Langflow ({langflow_memory}GB) может быть недостаточным "
            f"для работы с ИИ агентами. Рекомендуется минимум 3GB, оптимально 4-6GB."
        )
    
    # Проверка Ollama
    if not has_gpu and total_ram < 16:
        warnings.append("Ollama не рекомендуется без NVIDIA GPU с CUDA и менее 16 GB RAM")
    
    # Проверка диска
    free_disk = hardware_info['disk']['free_gb']
    if free_disk < 10:
        errors.append(f"Недостаточно места на диске! Требуется минимум 10 GB, доступно {free_disk:.1f} GB")
    elif free_disk < 20:
        warnings.append(f"Мало места на диске ({free_disk:.1f} GB) - рекомендуется минимум 20 GB")
    
    config['warnings'] = warnings
    config['errors'] = errors
    
    return config


def calculate_memory_limit(total_ram: float, percentage: float, min_val: float = 0.5, max_val: float = 8) -> float:
    """
    Вычисляет лимит памяти на основе процента от общего объема
    
    Args:
        total_ram: Общий объем RAM в GB
        percentage: Процент от общего объема (0.0 - 1.0)
        min_val: Минимальное значение в GB
        max_val: Максимальное значение в GB
        
    Returns:
        Лимит памяти в GB
    """
    calculated = total_ram * percentage
    return round(max(min_val, min(calculated, max_val)), 1)


def get_resource_summary(config: Dict) -> Dict:
    """
    Возвращает сводку по использованию ресурсов
    """
    total_cpu = sum(config['cpu_limits'].values())
    total_memory = sum(config['memory_limits'].values())
    
    return {
        'total_cpu_cores': total_cpu,
        'total_memory_gb': total_memory,
        'services_count': len([v for v in config['memory_limits'].values() if v > 0])
    }

