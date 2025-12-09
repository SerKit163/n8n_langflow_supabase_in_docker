# Решение проблем с доменами и Langflow

## Исправления в последней версии

### 1. Langflow - исправлен entrypoint
- Убран флаг `--backend-only=false` (не поддерживается в последних версиях)
- Команда теперь: `langflow run --host 0.0.0.0 --port 7860`

### 2. nginx-proxy - обновлены образы и конфигурация
- Обновлен образ: `nginxproxy/nginx-proxy:latest` (вместо `jwilder/nginx-proxy`)
- Обновлен образ для SSL: `nginxproxy/acme-companion:latest` (вместо `jrcs/letsencrypt-nginx-proxy-companion`)
- Исправлен путь к docker.sock: `/var/run/docker.sock` (вместо `/tmp/docker.sock`)
- Добавлен volume `acme` для хранения сертификатов
- Добавлена переменная `NGINX_PROXY_CONTAINER=nginx-proxy`

## Что нужно сделать после обновления

### 1. Пересоздать docker-compose.yml
```bash
# Удалите старый docker-compose.yml
rm docker-compose.yml

# Запустите установщик заново (или сгенерируйте вручную)
python3 setup.py
```

### 2. Остановите и удалите старые контейнеры
```bash
docker-compose down
docker-compose rm -f nginx-proxy nginx-proxy-letsencrypt langflow
```

### 3. Проверьте .env файл
Убедитесь, что в `.env` правильно указаны:
```env
ROUTING_MODE=subdomain
VIRTUAL_HOST_N8N=n8n.ваш-домен.ru
VIRTUAL_HOST_LANGFLOW=langflow.ваш-домен.ru
VIRTUAL_HOST_SUPABASE=supabase.ваш-домен.ru
LETSENCRYPT_HOST_N8N=n8n.ваш-домен.ru
LETSENCRYPT_HOST_LANGFLOW=langflow.ваш-домен.ru
LETSENCRYPT_HOST_SUPABASE=supabase.ваш-домен.ru
LETSENCRYPT_EMAIL=ваш-email@example.com
```

### 4. Запустите контейнеры заново
```bash
docker-compose up -d
```

### 5. Проверьте логи
```bash
# Проверьте Langflow
docker-compose logs langflow

# Проверьте nginx-proxy
docker-compose logs nginx-proxy

# Проверьте nginx-proxy-letsencrypt
docker-compose logs nginx-proxy-letsencrypt
```

### 6. Проверьте переменные окружения в контейнерах
```bash
# Проверьте переменные в контейнере n8n
docker-compose exec n8n env | grep VIRTUAL_HOST

# Проверьте переменные в контейнере langflow
docker-compose exec langflow env | grep VIRTUAL_HOST
```

## Частые проблемы

### Домены не работают

1. **Проверьте DNS записи**
   ```bash
   nslookup n8n.ваш-домен.ru
   ```
   Должен вернуть IP вашего сервера

2. **Проверьте, что порты 80 и 443 открыты**
   ```bash
   sudo ufw status
   # или
   sudo iptables -L -n | grep -E '80|443'
   ```

3. **Проверьте, что nginx-proxy запущен**
   ```bash
   docker-compose ps nginx-proxy
   ```

4. **Проверьте логи nginx-proxy**
   ```bash
   docker-compose logs nginx-proxy | tail -50
   ```

### Langflow не запускается

1. **Проверьте логи**
   ```bash
   docker-compose logs langflow | tail -50
   ```

2. **Проверьте права доступа к volume**
   ```bash
   docker-compose exec langflow ls -la /app/data
   ```

3. **Проверьте, что порт 7860 свободен**
   ```bash
   netstat -tuln | grep 7860
   # или
   ss -tuln | grep 7860
   ```

4. **Попробуйте пересоздать контейнер**
   ```bash
   docker-compose stop langflow
   docker-compose rm -f langflow
   docker-compose up -d langflow
   ```

### SSL сертификаты не генерируются

1. **Проверьте, что домены указывают на ваш IP**
   ```bash
   nslookup n8n.ваш-домен.ru
   ```

2. **Проверьте логи letsencrypt**
   ```bash
   docker-compose logs nginx-proxy-letsencrypt | tail -50
   ```

3. **Проверьте, что порты 80 и 443 открыты и доступны извне**

4. **Убедитесь, что email указан правильно**
   ```bash
   grep LETSENCRYPT_EMAIL .env
   ```

## Дополнительная информация

- nginx-proxy автоматически обнаруживает контейнеры с переменной `VIRTUAL_HOST`
- SSL сертификаты генерируются автоматически через Let's Encrypt
- Первая генерация сертификата может занять несколько минут

