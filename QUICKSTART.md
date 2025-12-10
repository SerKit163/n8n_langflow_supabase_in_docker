# Быстрый старт

## Установка за 3 шага

### 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/SerKit163/n8n_langflow_supabase_in_docker.git
cd n8n_langflow_supabase_in_docker
pip3 install -r requirements.txt
```

### 2. Запуск установщика

```bash
python3 setup.py
```

> **Примечание:** Если команда `python` не найдена, используйте `python3`

Следуйте инструкциям установщика:
- Выберите режим маршрутизации (поддомены/пути/порты)
- Настройте домены (если нужно)
- Выберите настройки сервисов
- Установщик автоматически определит ваше железо и предложит оптимальные настройки

### 3. Готово!

После установки сервисы будут доступны:
- **N8N**: http://localhost:5678 (или ваш домен)
- **Langflow**: http://localhost:7860 (или ваш домен)
- **Supabase**: http://localhost:8000 (или ваш домен)

## Обновление

### Обновление проекта с GitHub

Обновляет код и конфигурацию с сохранением настроек:

```bash
python3 update_from_github.py
```

### Обновление версий Docker образов

```bash
python3 update.py
```

## Управление сервисами

### Запуск
```bash
docker-compose up -d
# или
./scripts/start.sh
```

### Остановка
```bash
docker-compose down
# или
./scripts/stop.sh
```

### Перезапуск отдельного сервиса
```bash
./scripts/restart-service.sh n8n
```

### Просмотр логов
```bash
docker-compose logs -f [service_name]
```

## Примеры использования

### Создание автоматизации в n8n

1. Откройте n8n в браузере
2. Создайте новый workflow
3. Добавьте HTTP Request node для вызова Langflow API:
   ```
   URL: http://langflow:7860/api/v1/run/{flow_id}
   Method: POST
   Headers: Authorization: Bearer {LANGFLOW_API_KEY}
   ```

### Создание AI агента в Langflow

1. Откройте Langflow
2. Создайте новый flow
3. Используйте Ollama (если есть GPU) или OpenRouter для LLM
4. Настройте RAG с Supabase

### Интеграция с Google Calendar

Пример workflow в n8n:
- **Триггер**: Webhook от Langflow агента
- **Действие**: Google Calendar - Create Event
- **Сохранение**: Supabase - Insert Record

## Troubleshooting

### Сервисы не запускаются
```bash
docker-compose logs
```

### Недостаточно ресурсов
- Уменьшите лимиты памяти в `.env`
- Отключите Ollama если нет GPU
- Используйте OpenRouter вместо Ollama

### Проблемы с доменами
- Проверьте DNS записи
- Убедитесь что порты 80/443 открыты
- Проверьте конфиги Nginx в `nginx/conf.d/`

## Дополнительная информация

См. [README.md](README.md) для полной документации.

