# Умный поиск · SetRetail10

Открытый MVP: задайте вопрос о SetRetail10 и получите ответ со ссылками на документацию.
Регистрация и пароль не нужны. Источник — [публичная база знаний Crystal Service](https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/overview).

React + Vite → nginx → FastAPI → PostgreSQL/pgvector. Поиск гибридный, модели работают локально:
Qwen3-Embedding-0.6B, bge-reranker-v2-m3 и Qwen3-1.7B. API-ключ платного AI не требуется.

## Требования

- Linux x86_64 либо Windows с WSL2 / Docker Desktop.
- Docker Engine с Compose v2 с поддержкой `gpus: all`, NVIDIA GPU, совместимый с CUDA 12.8 драйвер и NVIDIA Container Toolkit.
- Интернет для загрузки образов, моделей Hugging Face и страниц Confluence.
- Практический стартовый ориентир: 8 ГБ VRAM, 16 ГБ RAM и 40 ГБ свободного диска. Это ориентир, не подтверждённый минимум: расход зависит от длины контекста.

CPU-only и ARM в текущей поставке не настроены. Первая сборка и загрузка моделей могут занимать десятки минут.

## Запуск после клонирования

```bash
git clone https://github.com/Danil-Umetbaev/my_ai_search.git
cd my_ai_search
cp .env.example .env
# В PowerShell вместо cp можно использовать Copy-Item .env.example .env
```

В `.env` задайте собственный `POSTGRES_PASSWORD`. Для публичного MVP VK-параметры оставьте пустыми / нулевыми.

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

Миграции применяются автоматически. Интерфейс: **http://localhost:8080**.
Новая база пока пуста — загрузите документацию следующими командами. Остановите backend на время индексации, чтобы модели не конкурировали за GPU:

```bash
docker compose stop frontend app
docker compose run --rm --no-deps app python -m src.ai.ingestion.import_knowledge
docker compose up -d
```

В репозитории есть список 1198 исходных URL (`backend/data/knowledge_urls.txt`), но нет чужих диалогов, дампа БД и весов моделей.
Импорт скачивает страницы, разбивает их на фрагменты и строит embeddings. При повторном запуске неизменившиеся документы пропускаются; новые и изменённые индексируются. Ошибки отдельных страниц выводятся в лог и дают ненулевой код завершения; повторный запуск позволяет их догрузить. Недоступные страницы могут требовать корректировки списка URL.
Для короткой проверки добавьте `--limit 3`; для своего списка — `--urls /backend/data/knowledge_urls.txt` (поместите список в образ перед сборкой либо примонтируйте файл).
Модели загружаются до готовности API: `Healthy` появляется после их загрузки. На новой машине первое скачивание может быть долгим; следите за `docker compose logs -f app`.

При переходе со старого Compose сохраните прежний кеш: укажите `HF_CACHE_VOLUME=backend_hf_cache` и `HF_CACHE_EXTERNAL=true` в `.env`, если модели уже находятся в этом Docker volume. Для полностью скачанного кеша можно добавить `HF_HUB_OFFLINE=1`, чтобы запуск не зависел от Hugging Face. На новой машине offline-режим не включайте.

## Публичный сервер

Используйте **тот же `docker-compose.yml` и те же команды**, что выше. Порт 8080 по умолчанию слушает все интерфейсы: `http://SERVER_IP:8080`. Пароля на сайт нет.

Для домена с HTTPS установите на сервере TLS reverse proxy (например, nginx/Caddy): направьте его на `127.0.0.1:8080`, выставьте таймаут ответа минимум 600 секунд. В `.env` поставьте `BIND_ADDRESS=127.0.0.1`, затем `docker compose up -d`. Внешнему миру откройте 80/443 на TLS proxy.

Если используете внешний proxy, настройте доверенный адрес этого proxy через `set_real_ip_from` и `real_ip_header X-Forwarded-For` в `frontend/nginx.conf`, затем пересоберите frontend. Доверяйте только адресу proxy: иначе посетитель сможет подделать IP. Без этого все посетители за proxy будут делить один лимит.

PostgreSQL и FastAPI наружу не опубликованы. `/docs` и OpenAPI в основном режиме выключены.
Для защиты GPU обрабатывается один AI-запрос одновременно; занятый сервис возвращает 429 с предложением повторить запрос. nginx также ограничивает частоту запросов. Это открытый MVP с ограниченной пропускной способностью, без очереди. Не увеличивайте число uvicorn workers: каждый загрузит собственные модели.

Данные и модели сохраняются в volumes `pg_data` и `hf_cache` проекта Compose. `docker compose down` сохраняет их; **`down -v` удаляет данные**. Не меняйте имя проекта Compose при обновлении.

Обновление:

```bash
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Перед обновлением сделайте резервную копию базы. Команды ниже предназначены для bash на сервере (бинарный dump не пропускайте через PowerShell pipeline):

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/database.dump
```

Восстановление полного dump выполняется в пустую базу **до первого запуска app и его миграций**:

```bash
docker compose up -d db
# Дождитесь healthy в docker compose ps
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error' < backups/database.dump
docker compose up -d --build
```

Не публикуйте dump и `.env` в Git. Если база уже содержит таблицы, не восстанавливайте поверх неё: используйте отдельную пустую базу/проект. Полный dump содержит также историю чатов.

## Разработка

Для локального изменения backend используйте дополнительный Compose-файл (исходники примонтированы, API и Swagger доступны только через localhost:7777):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
# После изменения Python-кода:
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart app
```

Для frontend с hot reload нужен Node.js 22:

```bash
cd frontend
npm ci
npm run dev
```

Откройте http://localhost:5173. Vite проксирует `/api` на localhost:7777.
После работы с dev-конфигурацией остановите её через `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`, затем запустите обычный Compose.

## Проверка

- Откройте сайт без пароля, создайте чат и спросите о товарных полках SetRetail10.
- Проверьте ответ и ссылки; обновите страницу — диалог должен сохраниться.
- Задайте вопрос, которого нет в документации: без VK получите `not_found`, без обещания отправки специалистам.
- При одновременной нагрузке допустим 429; после завершения ответа сервис должен снова принимать вопросы.

Проверки benchmark, валидации и ограничения параллелизма:

```bash
docker compose run --rm --no-deps app python -m unittest discover -s checks -v
```

API integration-тесты лежат в `backend/tests`; используют отдельную БД с суффиксом `_tests`, её нужно заранее создать и применить миграции. Они подменяют RAG и уведомления, реальный GPU-поиск не проверяют.

Benchmark реального RAG (запускайте при остановленном app, как импорт, чтобы не занять GPU дважды):

```bash
docker compose stop frontend app
docker compose run --rm --no-deps -v ./backend/test_output:/backend/test_output app python -m src.ai.test_rag --release
docker compose up -d
```

`--start 39 --end 150` запускает часть набора со стабильными ID; `--list` показывает вопросы без моделей.
Анализ JSONL: `python -m src.ai.analyze_rag test_output/ИМЯ_ФАЙЛА.jsonl` из каталога backend с Python-зависимостями.
Совпадение статуса не является оценкой полноты ответа. Порог reranker оставлен 0.30; известны ложный ответ про офисный Wi-Fi и неполные перечисления ролей. Метрика 97.3% не подтверждена проверкой качества ответов.

## Что хранится и что опционально

Чаты анонимные; список диалогов и метаданные источников интерфейс сохраняет в localStorage браузера, тексты — в БД. Это публичное демо без разграничения доступа по пользователям: UUID диалога не заменяет авторизацию. Не отправляйте конфиденциальные данные.

VK-эскалация включается только при заполнении `VK_TOKEN`, `VK_PEER_ID`, `VK_GROUP_ID`. Без них неизвестный вопрос просто получает `not_found`. При включённой интеграции вопросы вне найденной документации уходят в указанный VK-чат.

Основные каталоги: `backend/src` — API и RAG; `backend/data` — URL базы знаний; `backend/tests` и `backend/checks` — проверки; `frontend/src` — интерфейс; `deploy/init-db.sql` — расширение pgvector. Экспериментальные скрипты, старые Compose-конфигурации и отчёты передачи удалены.
