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
# Ищем все возможные пути
db_paths = [
    '/app/data/.langflow/langflow.db',
    '/app/data/langflow.db',
    '/app/.langflow/langflow.db',
    '/app/data/.langflow/database.db',
    '/app/data/database.db',
]

# Также ищем все .db файлы в директориях данных
search_dirs = [
    '/app/data/.langflow',
    '/app/data',
    '/app/.langflow',
]

db_path = None

# Сначала проверяем известные пути
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

# Если не нашли, ищем все .db файлы в директориях (кроме venv)
if not db_path:
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            try:
                for file in os.listdir(search_dir):
                    if file.endswith('.db') and 'venv' not in search_dir:
                        db_path = os.path.join(search_dir, file)
                        print(f'Найдена база данных: {{db_path}}')
                        break
                if db_path:
                    break
            except PermissionError:
                pass

if not db_path:
    print('❌ База данных Langflow не найдена!')
    print('Проверенные пути:')
    for path in db_paths:
        exists = '✓' if os.path.exists(path) else '✗'
        print(f'  {{exists}} {{path}}')
    print('\\nПроверенные директории:')
    for search_dir in search_dirs:
        exists = '✓' if os.path.exists(search_dir) else '✗'
        print(f'  {{exists}} {{search_dir}}')
        if os.path.exists(search_dir):
            try:
                files = os.listdir(search_dir)
                print(f'    Файлы: {{", ".join(files[:10])}}')
            except:
                pass
    print('\\n💡 Попробуем найти базу данных через find...')
    import subprocess
    result = subprocess.run(['find', '/app/data', '-name', '*.db', '-type', 'f', '!', '-path', '*/venv/*'], 
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0 and result.stdout.strip():
        print('Найденные .db файлы в /app/data:')
        for line in result.stdout.strip().split('\\n'):
            if line and 'venv' not in line:
                print(f'  - {{line}}')
        # Берем первый найденный (не из venv)
        db_files = [l for l in result.stdout.strip().split('\\n') if l and 'venv' not in l]
        if db_files:
            db_path = db_files[0]
            print(f'\\nИспользуем: {{db_path}}')
        else:
            print('\\n❌ Не найдено подходящих баз данных (исключая venv)')
            db_path = None
    else:
        print('\\n❌ База данных Langflow не найдена!')
        print('💡 Возможно, база данных еще не создана.')
        print('   Попробуйте:')
        print('   1. Открыть Langflow в браузере и дождаться полной загрузки')
        print('   2. Подождать 1-2 минуты после запуска')
        print('   3. Затем запустить скрипт снова')
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
    
    # Проверяем структуру таблицы user
    cursor.execute("PRAGMA table_info(user)")
    columns = {{col[1]: col[2] for col in cursor.fetchall()}}
    print(f'Колонки в таблице user: {{", ".join(columns.keys())}}')
    
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
    
    # Создаем пользователя - используем только те колонки, которые есть
    now = datetime.utcnow().isoformat()
    
    # Базовые колонки
    base_cols = ['username', 'password', 'is_superuser', 'is_active']
    base_vals = [username, password_hash, True, True]
    
    # Добавляем временные метки если они есть
    if 'created_at' in columns:
        base_cols.append('created_at')
        base_vals.append(now)
    if 'updated_at' in columns:
        base_cols.append('updated_at')
        base_vals.append(now)
    
    cols_str = ', '.join(base_cols)
    placeholders = ', '.join(['?'] * len(base_cols))
    
    cursor.execute(
        f"INSERT INTO user ({{cols_str}}) VALUES ({{placeholders}})",
        base_vals
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

