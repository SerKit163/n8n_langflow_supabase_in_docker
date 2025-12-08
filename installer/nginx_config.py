"""
Модуль генерации конфигураций Nginx
"""
from pathlib import Path
from typing import Dict, Optional
from installer.utils import get_project_root, write_file, ensure_dir


def generate_nginx_configs(config: Dict) -> None:
    """
    Генерирует конфигурации Nginx в зависимости от режима маршрутизации
    """
    routing_mode = config.get('routing_mode', '')
    
    if routing_mode == 'subdomain':
        generate_subdomain_configs(config)
    elif routing_mode == 'path':
        generate_path_config(config)
    # Если routing_mode пустой - Nginx не нужен


def generate_subdomain_configs(config: Dict) -> None:
    """Генерирует конфиги для режима поддоменов"""
    nginx_dir = get_project_root() / "nginx" / "conf.d"
    ensure_dir(str(nginx_dir))
    
    # N8N
    if config.get('n8n_domain'):
        n8n_config = generate_subdomain_server_config(
            domain=config['n8n_domain'],
            service='n8n',
            port=config.get('n8n_port', 5678),
            ssl_enabled=config.get('ssl_enabled', True)
        )
        write_file(str(nginx_dir / "n8n.conf"), n8n_config)
    
    # Langflow
    if config.get('langflow_domain'):
        langflow_config = generate_subdomain_server_config(
            domain=config['langflow_domain'],
            service='langflow',
            port=config.get('langflow_port', 7860),
            ssl_enabled=config.get('ssl_enabled', True)
        )
        write_file(str(nginx_dir / "langflow.conf"), langflow_config)
    
    # Supabase
    if config.get('supabase_domain'):
        supabase_config = generate_subdomain_server_config(
            domain=config['supabase_domain'],
            service='supabase',
            port=config.get('supabase_port', 8000),
            ssl_enabled=config.get('ssl_enabled', True)
        )
        write_file(str(nginx_dir / "supabase.conf"), supabase_config)
    
    # Ollama
    if config.get('ollama_enabled') and config.get('ollama_domain'):
        ollama_config = generate_subdomain_server_config(
            domain=config['ollama_domain'],
            service='ollama',
            port=config.get('ollama_port', 11434),
            ssl_enabled=config.get('ssl_enabled', True)
        )
        write_file(str(nginx_dir / "ollama.conf"), ollama_config)


def generate_path_config(config: Dict) -> None:
    """Генерирует конфиг для режима путей"""
    nginx_dir = get_project_root() / "nginx" / "conf.d"
    ensure_dir(str(nginx_dir))
    
    base_domain = config.get('base_domain', 'localhost')
    ssl_enabled = config.get('ssl_enabled', True)
    
    main_config = generate_path_server_config(
        domain=base_domain,
        services={
            'n8n': {
                'path': config.get('n8n_path', '/n8n'),
                'port': config.get('n8n_port', 5678)
            },
            'langflow': {
                'path': config.get('langflow_path', '/langflow'),
                'port': config.get('langflow_port', 7860)
            },
            'supabase': {
                'path': config.get('supabase_path', '/supabase'),
                'port': config.get('supabase_port', 8000)
            }
        },
        ssl_enabled=ssl_enabled
    )
    
    # Добавляем Ollama если включен
    if config.get('ollama_enabled'):
        main_config += generate_path_location(
            path=config.get('ollama_path', '/ollama'),
            service='ollama',
            port=config.get('ollama_port', 11434)
        )
    
    write_file(str(nginx_dir / "main.conf"), main_config)


def generate_subdomain_server_config(domain: str, service: str, port: int, ssl_enabled: bool = True) -> str:
    """Генерирует конфиг сервера для поддомена"""
    config = f"""server {{
    listen 80;
    server_name {domain};
    
    # Редирект на HTTPS если SSL включен
    {f'return 301 https://$server_name$request_uri;' if ssl_enabled else ''}
    {'' if ssl_enabled else '# SSL не включен'}
}}

{f'''server {{
    listen 443 ssl http2;
    server_name {domain};
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {{
        proxy_pass http://{service}:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }}
}}''' if ssl_enabled else f'''server {{
    listen 80;
    server_name {domain};
    
    location / {{
        proxy_pass http://{service}:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }}
}}'''}
"""
    return config


def generate_path_server_config(domain: str, services: Dict, ssl_enabled: bool = True) -> str:
    """Генерирует конфиг сервера для режима путей"""
    locations = ""
    for service_name, service_config in services.items():
        locations += generate_path_location(
            path=service_config['path'],
            service=service_name,
            port=service_config['port']
        )
    
    config = f"""server {{
    listen 80;
    server_name {domain};
    
    {f'return 301 https://$server_name$request_uri;' if ssl_enabled else ''}
    {'' if ssl_enabled else '# SSL не включен'}
}}

{f'''server {{
    listen 443 ssl http2;
    server_name {domain};
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
{locations}
}}''' if ssl_enabled else f'''server {{
    listen 80;
    server_name {domain};
    
{locations}
}}'''}
"""
    return config


def generate_path_location(path: str, service: str, port: int) -> str:
    """Генерирует location блок для пути"""
    return f"""    location {path}/ {{
        rewrite ^{path}/(.*)$ /$1 break;
        proxy_pass http://{service}:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }}
"""

