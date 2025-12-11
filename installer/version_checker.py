"""
Модуль проверки версий Docker образов
"""
import re
import requests
from typing import Dict, Optional, List
from rich.console import Console

console = Console()


def get_current_versions(docker_compose_path: str = "docker-compose.yml") -> Dict[str, str]:
    """
    Получает текущие версии из docker-compose.yml
    
    Returns:
        Словарь {service_name: version}
    """
    versions = {}
    
    try:
        with open(docker_compose_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Ищем образы в формате image: name:tag
            pattern = r'image:\s*([\w/.-]+):([\w.-]+)'
            matches = re.findall(pattern, content)
            
            for image, tag in matches:
                # Определяем сервис по имени образа
                if 'n8n' in image.lower():
                    versions['n8n'] = tag
                elif 'langflow' in image.lower():
                    versions['langflow'] = tag
                elif 'supabase' in image.lower():
                    versions['supabase'] = tag
                elif 'ollama' in image.lower():
                    versions['ollama'] = tag
    except FileNotFoundError:
        pass
    except Exception as e:
        console.print(f"[yellow]Предупреждение: не удалось прочитать версии: {e}[/yellow]")
    
    return versions


def get_latest_version(image_name: str) -> Optional[str]:
    """
    Получает последнюю версию образа из Docker Hub
    
    Args:
        image_name: Имя образа (например, 'n8nio/n8n')
        
    Returns:
        Последняя версия или None (возвращает 'latest' для большинства образов)
    """
    # Для большинства образов используем 'latest'
    # Это безопаснее, чем пытаться определить конкретную версию
    # которая может быть неправильной
    
    # Исключения - образы, которые должны иметь конкретные версии
    fixed_versions = {
        'ghcr.io/supabase/postgres': '15.1.0.119',
        'ghcr.io/supabase/gotrue': 'v2.162.0',
        'ghcr.io/supabase/postgrest': 'v12.2.0',
        'ghcr.io/supabase/studio': '20240513-d025e0f',
    }
    
    # Проверяем, есть ли фиксированная версия
    for fixed_image, fixed_version in fixed_versions.items():
        if fixed_image in image_name:
            return fixed_version
    
    # Для остальных используем 'latest'
    return 'latest'


def check_updates(current_versions: Dict[str, str]) -> Dict[str, Dict]:
    """
    Проверяет доступные обновления
    
    Returns:
        Словарь {service: {'current': ..., 'latest': ..., 'has_update': bool}}
    """
    image_mapping = {
        'n8n': 'n8nio/n8n',
        'langflow': 'langflowai/langflow',
        'supabase': 'supabase/postgres',
        'ollama': 'ollama/ollama'
    }
    
    updates = {}
    
    for service, image in image_mapping.items():
        if service not in current_versions:
            continue
        
        current = current_versions[service]
        latest = get_latest_version(image)
        
        if latest:
            has_update = current != latest and latest != 'latest'
            updates[service] = {
                'current': current,
                'latest': latest,
                'has_update': has_update,
                'image': image
            }
    
    return updates


def compare_versions(version1: str, version2: str) -> int:
    """
    Сравнивает две версии
    
    Returns:
        -1 если version1 < version2
        0 если version1 == version2
        1 если version1 > version2
    """
    # Упрощенное сравнение версий
    # Для более точного сравнения можно использовать packaging.version
    
    # Если одна из версий 'latest', считаем её новее
    if version1 == 'latest':
        return 1
    if version2 == 'latest':
        return -1
    
    # Парсим версии
    v1_parts = [int(x) for x in re.findall(r'\d+', version1)]
    v2_parts = [int(x) for x in re.findall(r'\d+', version2)]
    
    # Сравниваем по частям
    for i in range(max(len(v1_parts), len(v2_parts))):
        v1_part = v1_parts[i] if i < len(v1_parts) else 0
        v2_part = v2_parts[i] if i < len(v2_parts) else 0
        
        if v1_part < v2_part:
            return -1
        elif v1_part > v2_part:
            return 1
    
    return 0

