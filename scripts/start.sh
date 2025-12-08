#!/bin/bash
# Скрипт запуска всех сервисов

echo "🚀 Запуск сервисов..."

docker-compose up -d

if [ $? -eq 0 ]; then
    echo "✓ Сервисы запущены!"
    echo ""
    echo "Доступные сервисы:"
    echo "  N8N: http://localhost:5678"
    echo "  Langflow: http://localhost:7860"
    echo "  Supabase: http://localhost:8000"
else
    echo "❌ Ошибка при запуске сервисов"
    exit 1
fi

