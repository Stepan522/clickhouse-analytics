# Инструкция

Скрипт переносит строки со статусом `ready` из Google Sheets в PostgreSQL, получает координаты адреса через Yandex Geocoder API и после успешной записи меняет статус строки на `completed`.

Требуется Python 3.9 или новее.

## Установка

1. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

2. Скопируйте `.env.example` в `.env` и заполните своими данными.

3. Положите JSON-файл сервисного аккаунта Google рядом со скриптом. По умолчанию скрипт ищет файл `service_account.json`.

4. Запустите скрипт:

   ```bash
   python parser.py
   ```

## Переменные окружения

- `YANDEX_API_KEY` - API-ключ Yandex Geocoder.
- `SPREADSHEET_NAME` - название Google-таблицы.
- `WORKSHEET_NAME` - название листа, по умолчанию `Clients`.
- `SERVICE_ACCOUNT_FILE` - путь к JSON-файлу сервисного аккаунта Google, по умолчанию `service_account.json`.
- `POSTGRES_HOST` - хост PostgreSQL.
- `POSTGRES_PORT` - порт PostgreSQL, по умолчанию `5432`.
- `POSTGRES_DB` - имя базы данных.
- `POSTGRES_USER` - пользователь базы данных.
- `POSTGRES_PASSWORD` - пароль пользователя базы данных.
