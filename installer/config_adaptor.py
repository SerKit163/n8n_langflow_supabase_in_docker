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
            # Ollama: для GPU версии больше CPU, для CPU версии меньше
            'ollama': min(1.0, cpu_cores * 0.5) if has_gpu else min(0.5, cpu_cores * 0.3)
        },
        'memory_limits': {
            'n8n': calculate_memory_limit(total_ram, 0.2, min_val=1, max_val=4),
            # Langflow: адаптивный минимум в зависимости от доступной RAM
            # Для VPS < 8GB: минимум 3GB (чтобы не превышать доступную RAM)
            # Для VPS >= 8GB: минимум 4GB (рекомендуется для работы с AI агентами)
            # Оптимально 40% от RAM, максимум 8GB
            'langflow': calculate_memory_limit(total_ram, 0.4, min_val=(3.0 if total_ram < 8 else 4.0), max_val=8),
            'supabase': calculate_memory_limit(total_ram, 0.1, min_val=0.5, max_val=2),
            # Ollama: для GPU версии больше памяти, для CPU версии минимум 2GB
            'ollama': calculate_memory_limit(total_ram, 0.4, min_val=2, max_val=8) if has_gpu else calculate_memory_limit(total_ram, 0.3, min_val=2, max_val=4)
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
    langflow_min_recommended = 4.0 if total_ram >= 8 else 3.0
    
    if total_ram < 8:
        warnings.append(
            f"⚠️  Langflow требует много памяти для работы с ИИ агентами! "
            f"Рекомендуется минимум 8GB RAM для оптимальной работы. "
            f"Текущий лимит: {langflow_memory}GB из {total_ram}GB доступных. "
            f"На малых VPS (< 8GB) используется минимум 3GB вместо 4GB."
        )
    if langflow_memory < langflow_min_recommended:
        warnings.append(
            f"⚠️  Лимит памяти для Langflow ({langflow_memory}GB) может быть недостаточным "
            f"для работы с ИИ агентами. Рекомендуется минимум {langflow_min_recommended}GB, оптимально 4-6GB."
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
    Учитывает только включенные сервисы
    """
    # Проверяем какие сервисы включены
    n8n_enabled = config.get('n8n_enabled', True)
    langflow_enabled = config.get('langflow_enabled', True)
    ollama_enabled = config.get('ollama_enabled', False)
    # Supabase всегда включен
    
    total_cpu = 0
    total_memory = 0
    services_count = 0
    
    # Суммируем только для включенных сервисов
    if n8n_enabled:
        total_cpu += config['cpu_limits'].get('n8n', 0)
        total_memory += config['memory_limits'].get('n8n', 0)
        services_count += 1
    
    if langflow_enabled:
        total_cpu += config['cpu_limits'].get('langflow', 0)
        total_memory += config['memory_limits'].get('langflow', 0)
        services_count += 1
    
    # Supabase всегда включен
    total_cpu += config['cpu_limits'].get('supabase', 0)
    total_memory += config['memory_limits'].get('supabase', 0)
    services_count += 1
    
    if ollama_enabled:
        total_cpu += config['cpu_limits'].get('ollama', 0)
        total_memory += config['memory_limits'].get('ollama', 0)
        services_count += 1
    
    return {
        'total_cpu_cores': total_cpu,
        'total_memory_gb': total_memory,
        'services_count': services_count
    }

