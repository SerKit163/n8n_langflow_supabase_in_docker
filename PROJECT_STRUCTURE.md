# Структура проекта

## Основные файлы

```
n8n_langflow_supabase_in_docker/
├── setup.py                    # Интерактивный установщик
├── update.py                   # Скрипт обновления
├── requirements.txt            # Python зависимости
├── .gitignore                  # Игнорируемые файлы
├── README.md                    # Основная документация
├── QUICKSTART.md               # Быстрый старт
├── .env.example                 # Пример переменных окружения
│
├── installer/                   # Модули установщика
│   ├── __init__.py
│   ├── hardware_detector.py    # Определение железа
│   ├── config_adaptor.py       # Адаптация под железо
│   ├── resource_checker.py     # Проверка ресурсов
│   ├── validator.py            # Валидация ввода
│   ├── docker_manager.py       # Управление Docker
│   ├── config_generator.py     # Генерация конфигов
│   ├── nginx_config.py         # Генерация Nginx конфигов
│   ├── version_checker.py      # Проверка версий
│   └── utils.py                # Вспомогательные функции
│
├── templates/                   # Шаблоны конфигураций
│   ├── env.template            # Шаблон .env
│   ├── docker-compose.cpu.template    # Docker Compose без GPU
│   └── docker-compose.gpu.template    # Docker Compose с GPU
│
├── nginx/                       # Nginx конфигурации
│   ├── nginx.conf              # Основной конфиг
│   └── conf.d/                 # Конфиги серверов
│       └── .gitkeep
│
├── scripts/                     # Скрипты управления
│   ├── start.sh                # Запуск сервисов
│   ├── stop.sh                 # Остановка сервисов
│   ├── restart-service.sh      # Перезапуск сервиса
│   └── backup.sh               # Создание бэкапа
│
└── volumes/                     # Данные сервисов (создается автоматически)
    ├── n8n_data/
    ├── langflow_data/
    ├── supabase_data/
    └── ollama_data/
```

## Как это работает

### 1. Установка (setup.py)

1. Проверяет системные требования (Docker, Docker Compose)
2. Определяет характеристики железа (CPU, RAM, GPU, диск)
3. Адаптирует настройки под доступное железо
4. Предлагает выбрать режим маршрутизации (поддомены/пути/порты)
5. Настраивает домены и сервисы
6. Генерирует все конфигурационные файлы
7. Запускает сервисы

### 2. Обновление (update.py)

1. Проверяет текущие версии сервисов
2. Ищет доступные обновления
3. Позволяет выбрать что обновлять
4. Создает бэкап перед обновлением
5. Обновляет образы и конфигурации
6. Перезапускает сервисы

### 3. Модули

- **hardware_detector**: Определяет CPU, RAM, GPU, диск, тип системы
- **config_adaptor**: Адаптирует настройки под железо
- **resource_checker**: Проверяет достаточно ли ресурсов
- **validator**: Валидирует ввод пользователя
- **docker_manager**: Управляет Docker контейнерами
- **config_generator**: Генерирует .env и docker-compose.yml
- **nginx_config**: Генерирует конфиги Nginx для доменов
- **version_checker**: Проверяет доступные обновления

## Использование

### Первая установка

```bash
python3 setup.py
```

### Обновление

```bash
python3 update.py
```

### Управление сервисами

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Логи
docker-compose logs -f [service_name]

# Перезапуск
docker-compose restart [service_name]
```

## Особенности

- ✅ Автоматическое определение железа
- ✅ Адаптация под доступные ресурсы
- ✅ Поддержка GPU (NVIDIA)
- ✅ Два режима маршрутизации (поддомены/пути)
- ✅ Автоматическая генерация конфигов
- ✅ Health checks для всех сервисов
- ✅ Ограничения ресурсов
- ✅ Бэкапы перед обновлением
- ✅ Интерактивный установщик
- ✅ Кроссплатформенность (Windows/Linux/Mac)

