# 🏗 Tender Monitor Bot

Автоматический мониторинг тендеров на трубы DN ≥ 400 мм в Таджикистане.

Бот парсит международные и местные источники тендеров, фильтрует проекты связанные с закупкой труб (водоснабжение, ирригация, канализация) и присылает структурированные уведомления в Telegram.

---

## 📋 Возможности

- 🔄 **Автоматический мониторинг** — сканирование каждые 12 часов
- 🌍 **7 источников** — World Bank, ADB, EBRD, tenders.tj, UN, WSIP-1, МЭВР
- 🔩 **Фильтрация по DN** — только трубы DN ≥ 400 мм
- 🤖 **AI-карточки** — Claude Haiku генерирует структурированное описание
- 📊 **Еженедельный дайджест** — воскресенье, 09:00
- ⏰ **Напоминания** — тендеры с дедлайном < 7 дней
- 🔍 **Поиск** — поиск по базе тендеров
- 💾 **SQLite** — локальная база данных с дедупликацией

---

## 🚀 Установка

### 1. Клонирование

```bash
git clone <repo-url>
cd tender_monitor
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка .env

```bash
cp .env.example .env
```

Заполни `.env` своими данными:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Твой chat_id (узнать через [@userinfobot](https://t.me/userinfobot)) |
| `ANTHROPIC_API_KEY` | API ключ от [Anthropic](https://console.anthropic.com/) |

### 5. Запуск

```bash
python main.py
```

---

## 🤖 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие + инструкция |
| `/status` | Статус бота: последний скан, количество тендеров |
| `/scan` | Запустить немедленный скан всех источников |
| `/report` | Еженедельный дайджест |
| `/history N` | Последние N тендеров (по умолчанию 10) |
| `/search текст` | Поиск по базе тендеров |
| `/active` | Только тендеры со статусом Active |
| `/urgent` | Срочные тендеры (дедлайн < 14 дней) |
| `/settings` | Настройки бота |

---

## 🌐 Источники

| Источник | URL | Приоритет |
|---|---|---|
| UN Tajikistan | tajikistan.un.org | 🔴 Высокий |
| World Bank Projects | projects.worldbank.org | 🔴 Высокий |
| World Bank STEP | projects.worldbank.org/procurement | 🔴 Высокий |
| ADB | adb.org/projects/tenders | 🔴 Высокий |
| EBRD | ebrd.com/procurement | 🟡 Средний |
| tenders.tj | tenders.tj | 🟡 Средний |
| WSIP-1 PMU | wsip-1.tj | 🔴 Высокий |
| МЭВР | mewr.tj | 🟢 Низкий |

---

## 📁 Структура проекта

```
tender_monitor/
├── .env.example              # Шаблон настроек
├── requirements.txt          # Зависимости Python
├── README.md                 # Документация
├── main.py                   # Точка входа
├── config.py                 # Конфигурация из .env
├── database/
│   ├── db.py                 # SQLite CRUD операции
│   └── models.py             # Dataclass моделей
├── scrapers/
│   ├── base.py               # Абстрактный базовый скрапер
│   ├── worldbank.py          # World Bank + UN
│   ├── adb.py                # Asian Development Bank
│   ├── ebrd.py               # EBRD
│   ├── tenders_tj.py         # tenders.tj
│   └── eprocurement.py       # eprocurement.gov.tj
├── core/
│   ├── filter.py             # Фильтрация по keywords + DN
│   ├── deduplicator.py       # SHA256 дедупликация
│   ├── ai_card.py            # Claude Haiku AI карточки
│   └── scheduler.py          # APScheduler расписание
├── bot/
│   ├── handlers.py           # Telegram команды
│   ├── notifier.py           # Форматирование уведомлений
│   └── keyboards.py          # Inline-клавиатуры
└── utils/
    └── logger.py             # Логирование
```

---

## 🔔 Формат уведомлений

```
🔴 🆕 НОВЫЙ ТЕНДЕР
━━━━━━━━━━━━━━━━━━━━━
📌 RWSSP-NCB-W/016 | World Bank
🏗 Supply of Ductile Iron Pipes DN 560 mm

💰 Бюджет: $ 8,160,000
🔩 Трубы: DN 560 мм | ВЧШГ
📏 Протяжённость: 42.5 км
📍 Регион: Khatlon
📅 Дедлайн: 2026-07-15
📊 Статус: Active

🏦 Донор: World Bank IDA

📝 Закупка труб из ВЧШГ DN 560 мм для проекта
   водоснабжения сельских районов Хатлонской области.

🔗 Открыть тендер
━━━━━━━━━━━━━━━━━━━━━
⏱ Найдено: 2026-05-16T14:30:00
```

**Срочность:**
- 🔴 HIGH — дедлайн < 14 дней или Active + бюджет > $5 млн
- 🟡 MEDIUM — дедлайн 14–60 дней
- 🟢 LOW — плановый / не объявлен

---

## 🚀 Деплой

### Railway.app (бесплатно)

1. Создай аккаунт на [Railway](https://railway.app)
2. Подключи GitHub репозиторий
3. Добавь переменные окружения (Settings → Variables)
4. Создай `Procfile`:

```
worker: python main.py
```

5. Railway автоматически задеплоит

### Hetzner VPS

1. Арендуй VPS (CX22 — €4.5/мес достаточно)
2. Подключись по SSH:

```bash
ssh root@your-server-ip
```

3. Установи зависимости:

```bash
apt update && apt install -y python3.11 python3.11-venv git
```

4. Клонируй и настрой:

```bash
git clone <repo-url> /opt/tender_monitor
cd /opt/tender_monitor
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # заполни
```

5. Создай systemd сервис:

```bash
cat > /etc/systemd/system/tender-monitor.service << EOF
[Unit]
Description=Tender Monitor Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tender_monitor
ExecStart=/opt/tender_monitor/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

6. Запусти:

```bash
systemctl daemon-reload
systemctl enable tender-monitor
systemctl start tender-monitor
```

7. Проверь логи:

```bash
journalctl -u tender-monitor -f
```

---

## ⚙️ Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SCAN_INTERVAL_HOURS` | 12 | Интервал сканирования (часы) |
| `MIN_PIPE_DIAMETER_MM` | 400 | Минимальный диаметр DN (мм) |
| `REQUEST_TIMEOUT_SEC` | 30 | Таймаут HTTP запроса |
| `REQUEST_DELAY_SEC` | 2 | Пауза между запросами |
| `DB_PATH` | ./data/tenders.db | Путь к БД |
| `LOG_LEVEL` | INFO | Уровень логирования |
| `LOG_FILE` | ./logs/monitor.log | Путь к лог-файлу |

---

## 📊 Ключевые проекты на мониторинге

| Проект | ID | Донор |
|---|---|---|
| WSIP-1 | P177325 | World Bank |
| RWSSP | P162637 | World Bank |
| Vaksh Basin Irrigation | 53109 | ADB |
| Yavan Water Supply | — | EBRD |
| WSIP-2 (SOP-2) | — | World Bank (ожидается) |

---

## 📝 Лицензия

MIT
