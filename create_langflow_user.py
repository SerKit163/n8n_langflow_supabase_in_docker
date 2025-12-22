#!/usr/bin/env python3
"""
Скрипт для создания пользователя в Langflow
Использует прямое обращение к SQLite базе данных
"""
import sys
import subprocess
import bcrypt
import json

def create_langflow_user(username: str, password: str):
    """Создает пользователя в Langflow через прямое обращение к базе"""
    
    # Хешируем пароль
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    password_hash = hashed.decode('utf-8')
    
    # Создаем Python скрипт для выполнения внутри контейнера
    # Используем прямое обращение к SQLite базе
    script = f"""
import sys
import os
import sqlite3
import bcrypt
from datetime import datetime

username = '{username}'
password_hash = '{password_hash}'

# Находим базу данных Langflow
db_paths = [
    '/app/data/.langflow/langflow.db',
    '/app/data/langflow.db',
    '/app/.langflow/langflow.db'
]

db_path = None
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print('❌ База данных Langflow не найдена!')
    print('Проверенные пути:')
    for path in db_paths:
        print(f'  - {{path}}')
    sys.exit(1)

print(f'Найдена база данных: {{db_path}}')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем есть ли таблица user
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    if not cursor.fetchone():
        print('❌ Таблица user не найдена в базе данных!')
        print('Возможно, база данных еще не инициализирована.')
        conn.close()
        sys.exit(1)
    
    # Проверяем есть ли уже такой пользователь
    cursor.execute("SELECT id, username, is_superuser, is_active FROM user WHERE username=?", (username,))
    existing = cursor.fetchone()
    
    if existing:
        print(f'⚠ Пользователь {{username}} уже существует!')
        print(f'  ID: {{existing[0]}}')
        print(f'  Superuser: {{existing[2]}}')
        print(f'  Active: {{existing[3]}}')
        conn.close()
        sys.exit(0)
    
    # Создаем пользователя
    now = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO user (username, password, is_superuser, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, password_hash, True, True, now, now)
    )
    
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    
    print(f'✓ Пользователь {{username}} успешно создан!')
    print(f'  ID: {{user_id}}')
    print(f'  Пароль: {password}')
    sys.exit(0)
    
except sqlite3.Error as e:
    print(f'❌ Ошибка базы данных: {{e}}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Ошибка: {{e}}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
    
    # Выполняем скрипт в контейнере
    result = subprocess.run(
        ['docker-compose', 'exec', '-T', 'langflow', 'python', '-c', script],
        capture_output=True,
        text=True,
        cwd='.'
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    
    return result.returncode == 0

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Использование: python3 create_langflow_user.py <username> <password>")
        print("Пример: python3 create_langflow_user.py admin mypassword123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    print(f"Создание пользователя {username} в Langflow...")
    if create_langflow_user(username, password):
        print("\n✓ Готово! Теперь можно:")
        print("  1. Установить LANGFLOW_AUTO_LOGIN=false в docker-compose.yml")
        print("  2. Добавить LANGFLOW_SECRET_KEY")
        print("  3. Пересоздать контейнер: docker-compose up -d --force-recreate langflow")
    else:
        print("\n❌ Не удалось создать пользователя")
        sys.exit(1)

