

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
│   │   ├── main.py
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

- `app` - backend-приложение. Конфигурируется через `app/.env`, исходники подключены через volume.
- `web-proxy` - Nginx reverse proxy. Принимает запросы на портах `80` и `443` и проксирует их в `app`.
- `rabbitmq` - брокер сообщений RabbitMQ с management UI на порту `15672`.
- `database` - PostgreSQL для хранения данных приложения.

Данные RabbitMQ и PostgreSQL сохраняются в локальной директории `data/`.

## Запуск

```bash
docker compose up
```

Проверка backend через proxy:

```bash
curl http://localhost/health
```
