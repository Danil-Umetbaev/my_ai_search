"""Explicit live check: PYTHONPATH=. python tests/support_app_check.py.

Creates isolated temporary users; removes their sessions and tickets in finally.
Uses the running API; SUPPORT_CHECK_URL selects nginx if required.
Fault injection runs in a separate ASGI process against temporary test sessions.
Speed checks are opt-in (--load); never starts models or rebuilds containers.
"""

import argparse
import asyncio
import json
import math
import os
import secrets
from time import perf_counter
from uuid import uuid4

import asyncpg
import httpx

from src.config import settings
from src.services.auth import AuthService


async def connection():
    return await asyncpg.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER,
        password=settings.DB_PASS, database=settings.DB_NAME,
    )


async def cleanup(db, ids):
    async with db.transaction():
        await db.execute("UPDATE support_sessions SET ticket_id=NULL WHERE user_id=ANY($1::int[])", ids)
        await db.execute("DELETE FROM support_tickets WHERE user_id=ANY($1::int[])", ids)
        await db.execute("DELETE FROM support_sessions WHERE user_id=ANY($1::int[])", ids)
        await db.execute("DELETE FROM users WHERE id=ANY($1::int[])", ids)


async def call(client, method, path, payload=None, expected=200):
    response = await client.request(method, path, json=payload)
    assert response.status_code == expected, (path, response.status_code, response.text[:500])
    return response.json()


async def new_session(client):
    return (await call(client, "POST", "/support/sessions", expected=201))["id"]


async def send(client, session, text, choice=None, request_id=None):
    return await call(client, "POST", f"/support/sessions/{session}/messages", {
        "message": text, "choice_id": choice, "request_id": request_id or str(uuid4()),
    })


async def lifecycle(clients):
    client, other = clients[:2]
    session = await new_session(client)
    rid = str(uuid4())
    replies = await asyncio.gather(*[
        send(client, session, "Не печатает чек", request_id=rid) for _ in range(5)
    ])
    assert all(reply == replies[0] for reply in replies)
    row = await call(client, "GET", f"/support/sessions/{session}")
    assert len(row["history"]) == 2
    await call(other, "GET", f"/support/sessions/{session}", expected=404)
    reply = replies[0]
    for label in ("Пирит 2Ф", "Нет", "Да", "Да"):
        assert any(c["label"] == label for c in reply["choices"]), (label, reply)
        choice = next(c for c in reply["choices"] if c["label"] == label)
        reply = await send(client, session, label, choice["id"])
    assert reply["phase"] == "diagnosing" and "1." in reply["answer"], reply
    await send(client, session, "Не помогло")
    rid = str(uuid4())
    replies = await asyncio.gather(*[send(client, session, "да", request_id=rid) for _ in range(5)])
    ticket_id = replies[0]["ticket_id"]
    assert ticket_id and all(r["ticket_id"] == ticket_id for r in replies)
    ticket = await call(client, "GET", f"/support/tickets/{ticket_id}")
    details = ticket["details"]
    assert details["check_result"] == "Не помогло"
    assert details["receipt_facts"]["model"] == "Пирит 2Ф"
    assert details["completed_procedures"] and details["fact_changes"]
    assert details["sources"] and details["transcript"]
    assert len(ticket["events"]) == 1
    await call(other, "GET", f"/support/tickets/{ticket_id}", expected=404)
    fresh = await new_session(client)
    row = await call(client, "GET", f"/support/sessions/{fresh}")
    assert not row["history"] and not row["ticket_id"]
    reply = await send(client, fresh, "Не печатает чек")
    stale = reply["choices"][0]
    await send(client, fresh, "Пирит 2Ф")
    await call(client, "POST", f"/support/sessions/{fresh}/messages", {
        "message": stale["label"], "choice_id": stale["id"], "request_id": str(uuid4()),
    }, expected=409)
    await send(client, fresh, "Бумаги нет")
    await send(client, fresh, "Да")
    await send(client, fresh, "Да")
    resolved = await send(client, fresh, "Да, помогло")
    assert resolved["phase"] == "resolved" and not resolved["ticket_id"]
    row = await call(client, "GET", f"/support/sessions/{session}")
    assert row["ticket_id"] == ticket_id
    print("Lifecycle: duplicate messages/tickets, reload history, ownership, stale buttons, resolution, new session PASS", flush=True)


def statistics(samples):
    ordered = sorted(samples)
    return {"count": len(ordered), "p50": round(ordered[math.ceil(len(ordered)*.5)-1], 3),
            "p95": round(ordered[math.ceil(len(ordered)*.95)-1], 3), "max": round(max(ordered), 3)}


async def load(clients):
    clarification, searches = [], []
    queries = [
        "Пирит 2Ф: какие интерфейсы подключения поддерживаются?",
        "АТОЛ FPrint-22ПТК: какая скорость печати?",
        "Вики Принт: как проверить связь с компьютером?",
        "Пирит 2Ф: БАТАРЕЯ РАЗРЯЖЕНА, что означает?",
    ]

    async def worker(client, number):
        for index in range(40):
            session = await new_session(client)
            start = perf_counter()
            reply = await send(client, session, "Не печатает чек")
            clarification.append(perf_counter()-start)
            assert reply["choices"]
            session = await new_session(client)
            start = perf_counter()
            await send(client, session, queries[(index+number) % len(queries)])
            duration = perf_counter()-start
            row = await call(client, "GET", f"/support/sessions/{session}")
            assert row["state"].get("next_action") in {"inform", "offer_specialist"}, row["state"]
            searches.append(duration)
    start = perf_counter()
    await asyncio.gather(*(worker(client, index) for index, client in enumerate(clients)))
    result = {"users": len(clients), "elapsed": round(perf_counter()-start, 2),
              "clarifications": statistics(clarification), "knowledge_answers": statistics(searches)}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    assert result["knowledge_answers"]["p95"] <= 25
    assert result["clarifications"]["p95"] <= 1.5



async def isolation(clients):
    sessions = await asyncio.gather(*(new_session(c) for c in clients))
    await asyncio.gather(*(send(c, sid, f"Не печатает чек, магазин {i+100}") for i, (c, sid) in enumerate(zip(clients, sessions))))
    for i, (client, sid) in enumerate(zip(clients, sessions)):
        row = await call(client, "GET", f"/support/sessions/{sid}")
        assert len(row["history"]) == 2
        assert str(i+100) in row["history"][0]["content"]
        await call(clients[(i+1)%len(clients)], "GET", f"/support/sessions/{sid}", expected=404)
    print("Five simultaneous users: isolated histories PASS", flush=True)


async def failures(authenticated):
    from unittest.mock import patch, AsyncMock
    from src.main import app
    from src.services.support_knowledge import SupportKnowledgeService
    app.state.models = {"status": "loading"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://app/api/v1",
                                cookies=authenticated.cookies, headers={"Origin": "http://localhost:18081"}) as client:
        status = await call(client, "GET", "/support/status")
        assert status["models"] == "loading"
        sid = await new_session(client)
        reply = await send(client, sid, "Не печатает чек")
        assert reply["choices"]
        sid = await new_session(client)
        with patch.object(SupportKnowledgeService, "lookup", AsyncMock(side_effect=RuntimeError("Injected search outage"))):
            reply = await send(client, sid, "Пирит 2Ф: БАТАРЕЯ РАЗРЯЖЕНА, что означает?")
        row = await call(client, "GET", f"/support/sessions/{sid}")
        assert row["state"]["next_action"] == "retry_search"
        assert "временно недоступен" in reply["answer"]
        assert row["state"]["receipt_facts"]["model"] == "Пирит 2Ф"
        reply = await send(client, sid, "Повтори поиск")
        row = await call(client, "GET", f"/support/sessions/{sid}")
        assert row["state"].get("search_status") != "unavailable", row["state"]
        assert len(row["history"]) == 4
    print("API fault injection: loading, outage, preserved facts, retry PASS", flush=True)


async def main():
    db = await connection()
    ids, clients = [], []
    try:
        password = secrets.token_urlsafe(20)
        hashed = AuthService().hash_password(password)
        for index in range(5):
            email = f"support-check-{uuid4()}@example.com"
            ids.append(await db.fetchval("INSERT INTO users(email,role,hashed_password) VALUES($1,'kassir',$2) RETURNING id", email, hashed))
            client = httpx.AsyncClient(base_url=os.getenv("SUPPORT_CHECK_URL", "http://app:8000/api/v1"),
                                       headers={"Origin": "http://localhost:18081"}, timeout=70)
            clients.append(client)
            await call(client, "POST", "/auth/login", {"email": email, "password": password})
        await lifecycle(clients)
        await isolation(clients)
        await failures(clients[0])
        if args.load:
            await load(clients)
    finally:
        for client in clients:
            await client.aclose()
        await cleanup(db, ids)
        await db.close()
        print("Temporary accounts, sessions and tickets removed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    asyncio.run(main())

