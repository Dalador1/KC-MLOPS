

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

В `docker-compose.yml` описаны четыре сервиса:

- `app` - backend-приложение. Конфигурируется через `.env` и `app/.env`, исходники подключены через volume.
- `web-proxy` - Nginx reverse proxy. Принимает запросы на портах `80` и `443` и проксирует их в `app`.
- `rabbitmq` - брокер сообщений RabbitMQ с management UI на порту `15672`.
- `database` - PostgreSQL для хранения данных приложения.

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
- `spam-ham-default` - базовая ML-модель.

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
- `/auth/login` - авторизация по email и паролю.
- `/users/me` - данные текущего пользователя.
- `/balance` - просмотр баланса.
- `/balance/top-up` - пополнение баланса.
- `/predict` - проверка писем на spam/ham.
- `/history/predictions` - история ML-запросов.
- `/history/transactions` - история операций с балансом.

Авторизация в текущем задании простая: защищённые ручки получают `email` и `password` в теле запроса.
Настоящая ML-модель пока замокана: сервис возвращает `spam` для писем с простыми рекламными словами и `ham` для остальных.

Пример запроса:

```bash
curl -X POST http://localhost/predict \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "demo",
    "model_name": "spam-ham-default",
    "emails": [
      {"subject": "Sale", "body": "Buy now"},
      {"subject": "Meeting", "body": "See you tomorrow"},
      {"subject": "Broken", "body": ""}
    ]
  }'
```
