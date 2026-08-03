# Описание проекта:

Проект описывает доменную модель сервиса для проверки письма на spam / ham.

## Описание сущностей:

- `User` - пользователь сервиса с ролью и данными для авторизации.
- `CreditBalance` - кредитный баланс пользователя.
- `EmailMessage` - email-сообщение, которое пользователь отправляет на проверку.
- `EmailValidator` - проверяет входные данные и отделяет валидные письма от ошибочных.
- `SpamModel` - ML-модель для классификации email.
- `PredictionRequest` - задача на выполнение ML-предсказания.
- `EmailPrediction` - результат проверки одного письма.
- `Transaction` - базовая операция с кредитным балансом.
- `TopUp` - пополнение баланса.
- `Charge` - списание кредитов за проверку.

## Структура проекта

```text
.
├── app/
│   ├── src/
│   │   ├── check_db.py
│   │   ├── database.py
│   │   ├── init_db.py
│   │   ├── main.py
│   │   ├── orm.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── balance.py
│   │   │   ├── history.py
│   │   │   ├── predict.py
│   │   │   └── users.py
│   │   └── models/
│   │       ├── balance.py
│   │       ├── email.py
│   │       ├── enums.py
│   │       ├── ml.py
│   │       ├── prediction.py
│   │       ├── transaction.py
│   │       └── user.py
│   ├── .env
│   ├── Dockerfile
│   └── requirements.txt
├── web-proxy/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── README.md
```

## Docker Compose

В `docker-compose.yml` описаны backend, инфраструктура и два ML-воркера:

- `app` - backend-приложение. Конфигурируется через `.env` и `app/.env`, исходники подключены через volume.
- `web-proxy` - Nginx reverse proxy. Принимает запросы на портах `80` и `443` и проксирует их в `app`.
- `rabbitmq` - брокер сообщений RabbitMQ с management UI на порту `15672`.
- `database` - PostgreSQL для хранения данных приложения.
- `worker-1`, `worker-2` - consumers одной RabbitMQ-очереди. Задачи распределяются между ними round-robin.

Данные RabbitMQ и PostgreSQL сохраняются в локальной директории `data/`.

Общие переменные для PostgreSQL и RabbitMQ лежат в корневом `.env`.

## ORM и база данных

В проект добавлен ORM-слой на SQLAlchemy:

- `app/src/database.py` - подключение к PostgreSQL через переменные окружения.
- `app/src/orm.py` - таблицы БД и связи между ними.
- `app/src/services.py` - бизнес-операции с пользователями, балансом, транзакциями и ML-задачами.
- `app/src/init_db.py` - идемпотентная инициализация БД.
- `app/src/check_db.py` - сценарий проверки основных операций.

Основные таблицы:

- `users` - пользователи.
- `credit_balances` - кредитные балансы пользователей.
- `spam_models` - доступные ML-модели.
- `prediction_requests` - история ML-запросов.
- `email_predictions` - результаты предсказаний.
- `validation_errors` - ошибки валидации.
- `transactions` - история операций с балансом.

При старте backend-приложения автоматически создаются таблицы и демо-данные:

- `demo@example.com` - демо-пользователь.
- `admin@example.com` - демо-администратор.
- `RUSpam/spam_deberta_v4` - русскоязычная DeBERTa-модель определения спама.

## Запуск

```bash
docker compose up
```

Проверка backend через proxy:

```bash
curl http://localhost/health
```

Проверка БД и бизнес-сценариев:

```bash
docker compose exec app python -m src.check_db
```

## REST API

FastAPI-приложение разбито на группы роутов:

- `/auth/register` - регистрация пользователя.
- `/auth/login` - авторизация по email и паролю, возвращает Bearer-токен.
- `/users/me` - данные текущего пользователя.
- `/balance` - просмотр баланса.
- `/balance/top-up` - пополнение баланса.
- `POST /predict` - постановка асинхронной spam/ham-задачи в RabbitMQ.
- `GET /predict/{task_id}` - статус и результат задачи.
- `/history/predictions` - история ML-запросов.
- `/history/transactions` - история операций с балансом.

Защищённые ручки используют Bearer-авторизацию. Сначала нужно получить токен через `/auth/login`, затем передавать его в заголовке `Authorization`.
ML-предикт выполняется моделью `RUSpam/spam_deberta_v4`. 

Publisher отправляет в очередь `spam_prediction_tasks` JSON:

```json
{
  "task_id": "uuid",
  "features": {"emails": [{"subject": "...", "body": "..."}]},
  "model": "RUSpam/spam_deberta_v4",
  "user_id": 1,
  "timestamp": "2026-01-01T12:00:00+00:00"
}
```

Воркеры валидируют сообщение и письма, выполняют предикт и напрямую сохраняют статус, `worker_id`, ошибки и результаты в PostgreSQL. Кредиты списываются только после успешного предикта. 

Получение токена:

```bash
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "demo"
  }'
```

Пример запроса к ML-сервису:

```bash
curl -X POST http://localhost/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
  "model_name": "RUSpam/spam_deberta_v4",
  "emails": [
    {
      "subject": "Вы выиграли",
      "body": "Получите денежный приз прямо сейчас по ссылке"
    },
    {
      "subject": "Рабочая встреча",
      "body": "Созвон переносится на завтра в 11 часов"
    },
    {
      "subject": "Ошибка",
      "body": ""
    }
  ]
}'
```

API вернёт `task_id`. Получение результата:

```bash
curl http://localhost/predict/<task_id> \
  -H "Authorization: Bearer <access_token>"
```

Проверка распределения задач между воркерами:

```bash
docker compose logs worker-1 worker-2
```
