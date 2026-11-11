import { knowledgeSpace, isSourceUrl } from "../knowledge";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { request } from "../api/client";
import { pendingForSession, outgoingMessage } from "./supportPending";
import "./SupportWorkspace.css";

const STATUS = { open: "Новая", in_progress: "В работе", resolved: "Решена" };
const LABELS = { paper_facts: "Условия работы с бумагой", diagnostic_facts: "Уточнённые данные", problem_changes: "Изменения проблемы", performed_checks: "Выполненные проверки", receipt_facts: "Факты о кассе", completed_procedures: "Пройденные процедуры", problem: "Проблема", environment: "Окружение", impact: "Влияние", attempts: "Проверки", check_result: "Результат проверки", hypotheses: "Гипотезы — не подтверждены", unknowns: "Нужно уточнить", additional_context: "Дополнение", observations: "Ответы на вопросы", fact_changes: "Уточнения фактов", resolution: "Результат" };

function readStorage(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function writeStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

function Sources({ sources = [] }) {
  return <ul className="support-sources">{sources.filter(source => isSourceUrl(source.url)).map((source, index) => <li key={index}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>{source.quote && <blockquote>{source.quote}</blockquote>}</li>)}</ul>;
}

function ReplyText({ text }) {
  return <div className="support-reply">{text.split("\n").filter(line => line.trim()).map((line, index) => {
    const picture = line.match(/^!\[([^\]]*)\]\((\/api\/v1\/knowledge-assets\/[a-f0-9]{64}\.png)\)$/);
    if (picture) return <a key={index} href={picture[2]} target="_blank" rel="noreferrer"><img className="support-manual-image" src={picture[2]} alt={picture[1]} loading="lazy" /></a>;
    const match = line.match(/^(.*?):\s*((?:https?:\/\/|\/api\/)[^\s]+)$/);
    if (match && isSourceUrl(match[2])) return <a className="support-source-link" key={index} href={match[2]} target="_blank" rel="noreferrer">{match[1]} ↗</a>;
    return <p key={index}>{line}</p>;
  })}</div>;
}

function FactValue({ value }) {
  if (value == null) return "Неизвестно";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return <ul>{value.map((entry, index) => <li key={index}><FactValue value={entry} /></li>)}</ul>;
  const labels = { selected_answer: "Понятый ответ", previous: "Раньше", current: "Теперь", value: "Новое значение", invalidated: "Нужно уточнить заново", previous_facts: "Прежние условия бумаги", previous_diagnostic_facts: "Прежние данные", instruction: "Инструкция", result: "Результат", sources: "Источники", title: "Документ", url: "Ссылка", model: "Модель", symptom: "Симптом", paper_present: "Рулон установлен", paper_width_mm: "Ширина ленты, мм", layout: "Расположение", error_text: "Сообщение устройства", error_status: "Наличие ошибки", problem_resolved: "Проблема решена", cover_opens: "Крышка открывается", suitable_roll_available: "Есть подходящий рулон", question: "Вопрос", answer: "Ответ", field: "Факт", before: "Раньше", after: "Теперь", text: "Сообщение пользователя", reason: "Причина изменения" };
  return <dl>{Object.entries(value).map(([key, entry]) => <div key={key}><dt>{labels[key] || key}</dt><dd><FactValue value={entry} /></dd></div>)}</dl>;
}

export default function SupportWorkspace({ user, onClose }) {
  const storageKey = `support-session-${knowledgeSpace}-${user.id}`;
  const pendingKey = `support-pending-${knowledgeSpace}-${user.id}`;
  const panelRef = useRef(null);
  const latestReply = useRef(null);
  const sendingRef = useRef(false);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [choices, setChoices] = useState([]);
  const [phase, setPhase] = useState("collect");
  const [input, setInput] = useState("");
  const [pendingSend, setPendingSend] = useState(null);
  const [mode, setMode] = useState(null);
  const [view, setView] = useState("diagnosis");
  const [tickets, setTickets] = useState([]);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState("");
  const [hasNext, setHasNext] = useState(false);
  const [detail, setDetail] = useState(null);
  const [edit, setEdit] = useState({ status: "open", resolution: "", comment: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const staff = ["admin", "it"].includes(user.role);

  async function run(action) {
    if (sendingRef.current) return;
    sendingRef.current = true; setBusy(true); setError("");
    try { await action(); } catch (err) { setError(err.userMessage || err.message); }
    finally { sendingRef.current = false; setBusy(false); }
  }

  function restore(data) {
    setSession(data.id);
    setChoices(data.choices || []);
    setPhase(data.ticket_id ? "ticket_created" : data.state?._phase || "collect");
    setMessages(data.history?.length ? data.history : [{ role: "assistant", content: data.answer || "Опишите неисправность и текст ошибки. Не отправляйте пароли и коды подтверждения." }]);
  }

  useEffect(() => {
    latestReply.current?.scrollIntoView({ block: "start" });
  }, [messages, view]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setBusy(true);
    (async () => {
      const saved = readStorage(storageKey) || localStorage.getItem(storageKey);
      let data;
      if (saved) {
        try { data = await request(`/support/sessions/${saved}`, { signal: controller.signal }); }
        catch (err) { if (err.status !== 404) throw err; }
      }
      if (!data) data = await request("/support/sessions", { method: "POST", signal: controller.signal });
      if (!active) return;
      restore(data); writeStorage(storageKey, data.id);
      const pending = readStorage(pendingKey);
      const remaining = pendingForSession(pending, data);
      setPendingSend(remaining);
      if (pending?.session === data.id && !remaining) writeStorage(pendingKey, null);
    })().catch(err => { if (active) setError(err.userMessage || err.message); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; controller.abort(); };
  }, [user.id]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const refresh = () => request("/support/status", { signal: controller.signal }).then(data => { if (active) setMode(data); }).catch(() => {});
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => { active = false; clearInterval(timer); controller.abort(); };
  }, []);

  useEffect(() => {
    const previous = document.activeElement;
    const shell = document.querySelector(".app-shell");
    const wasInert = shell?.inert;
    if (shell) shell.inert = true;
    panelRef.current?.focus();
    return () => {
      if (shell) shell.inert = wasInert;
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, []);

  function trapFocus(event) {
    if (event.key === "Escape" && !busy) { onClose(); return; }
    if (event.key !== "Tab") return;
    const items = [...panelRef.current.querySelectorAll('button:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href]')];
    const first = items[0]; const last = items[items.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panelRef.current)) { event.preventDefault(); first.focus(); }
  }

  async function send(text, choiceId = null, action = null) {
    const message = text.trim();
    if (!message || !session || busy) return;
    await run(async () => {
      const outgoing = outgoingMessage(pendingSend, session, message, choiceId);
      if (!pendingSend) outgoing.action = action;
      const requestId = outgoing.id;
      writeStorage(pendingKey, outgoing);
      setPendingSend(outgoing);
      const clearPending = () => {
        if (readStorage(pendingKey)?.id === requestId) writeStorage(pendingKey, null);
        setPendingSend(null);
      };
      try {
        const reply = await request(`/support/sessions/${session}/messages`, { method: "POST", body: JSON.stringify({ message: outgoing.message, request_id: requestId, choice_id: outgoing.choiceId, action: outgoing.action || null }), signal: AbortSignal.timeout(65000) });
        setMessages(previous => [...previous, { role: "user", content: outgoing.message }, { role: "assistant", content: reply.answer }]);
        setChoices(reply.choices);
        setPhase(reply.phase);
        setInput(""); clearPending();
      } catch (err) {
        if (err.status === 409) { restore(await request(`/support/sessions/${session}`)); clearPending(); }
        throw err;
      }
    });
  }

  async function loadTickets(nextView = view, nextPage = page, nextFilter = filter) {
    const params = new URLSearchParams({ queue: String(nextView === "queue"), offset: String(nextPage * 20), limit: "21" });
    if (nextFilter) params.set("status", nextFilter);
    const data = await request(`/support/tickets?${params}`);
    setTickets(data.slice(0, 20)); setHasNext(data.length > 20);
    setView(nextView); setPage(nextPage); setFilter(nextFilter);
  }

  async function openTicket(id) {
    const data = await request(`/support/tickets/${id}`);
    setDetail(data); setEdit({ status: data.status, resolution: data.resolution, comment: "" });
  }

  const terminal = ["cancelled", "resolved", "ticket_created"].includes(phase);
  return createPortal(<div className="support-backdrop">
    <section className="support-panel" role="dialog" aria-modal="true" aria-labelledby="support-title" ref={panelRef} tabIndex={-1} onKeyDown={trapFocus}>
      <header><div><span className="support-eyebrow">СЛУЖБА ПОДДЕРЖКИ</span><h2 id="support-title">Разберёмся с проблемой</h2></div><button type="button" disabled={busy} onClick={onClose}>Закрыть</button></header>
      <nav aria-label="Разделы поддержки">{[["diagnosis", "Диагностика"], ["mine", "Мои заявки"], ...(staff ? [["queue", "Панель специалиста"]] : [])].map(([key, label]) => <button type="button" key={key} disabled={busy} aria-current={view === key ? "page" : undefined} onClick={() => key === "diagnosis" ? (setView(key), setDetail(null)) : run(async () => { await loadTickets(key, 0, ""); setDetail(null); })}>{label}</button>)}</nav>
      {error && <p className="support-error" role="alert">{error}</p>}
      {busy && <p className="support-progress" role="status">Обрабатываем запрос…</p>}
      {view === "diagnosis" ? <>

        <div className="support-conversation" aria-live="polite">{messages.map((message, index) => <article ref={index === messages.length - 1 ? latestReply : null} key={index} className={`support-message support-message--${message.role}`}><strong>{message.role === "user" ? "Вы" : "Диагност"}</strong><ReplyText text={message.content} /></article>)}</div>
        {!terminal && choices.length > 0 && <div className="support-choices" aria-label="Варианты ответа">{choices.map(choice => <button type="button" key={choice.id} disabled={busy || !!pendingSend} onClick={() => send(choice.label, choice.id)}>{choice.label}</button>)}</div>}
        {pendingSend && <div role="status"><p>Отправка не подтверждена: {pendingSend.message}</p><button type="button" disabled={busy} onClick={() => send(pendingSend.message, pendingSend.choiceId, pendingSend.action)}>Повторить отправку</button></div>}
        {!terminal && !pendingSend && <form className="support-composer" onSubmit={event => { event.preventDefault(); send(input, null, phase === "confirm" ? "send_with_details" : null); }}>
          {phase === "confirm" && <label htmlFor="support-message">Что ещё стоит знать специалисту? Необязательно.</label>}
          <textarea id="support-message" aria-label={phase === "confirm" ? "Дополнение для специалиста" : "Ваш ответ"} maxLength={4000} disabled={busy || !session} value={input} onChange={event => setInput(event.target.value)} placeholder={phase === "confirm" ? "Когда началось, что видно на экране или что уже пробовали. Уже отправленное повторять не нужно." : "Опишите симптомы или результат проверки"} />
          <div className="support-actions"><button className="support-primary" disabled={busy || !session || !input.trim()}>{phase === "confirm" ? "Отправить с дополнением" : "Отправить"}</button>{phase === "confirm" ? <button type="button" disabled={busy || !session} onClick={() => send("Отправить без дополнения", null, "send_without_details")}>Отправить без дополнения</button> : <button type="button" disabled={busy || !session} onClick={() => send("передать специалисту")}>Нужен специалист</button>}<button type="button" disabled={busy || !session} onClick={() => send("отмена")}>Отменить обращение</button></div>
        </form>}
        <button type="button" disabled={busy} onClick={() => run(async () => { const data = await request("/support/sessions", { method: "POST" }); restore(data); writeStorage(storageKey, data.id); writeStorage(pendingKey, null); setPendingSend(null); setInput(""); })}>Новое обращение</button>
      </> : detail ? <>
        <button type="button" disabled={busy} onClick={() => setDetail(null)}>← К списку</button>
        <h3>Заявка {detail.id}</h3><p>{STATUS[detail.status]} · {new Date(detail.created_at).toLocaleString()} · Исполнитель: {detail.assigned_to || "не назначен"}</p>
        <dl className="support-facts">{Object.entries(detail.details).filter(([key]) => key in LABELS).map(([key, value]) => <div key={key}><dt>{LABELS[key] || key}</dt><dd><FactValue value={value} /></dd></div>)}</dl>
        <Sources sources={detail.details.sources} />
        {detail.resolution && <p className="support-resolution"><strong>Решение:</strong> {detail.resolution}</p>}
        {staff && <form onSubmit={event => { event.preventDefault(); run(async () => { await request(`/support/tickets/${detail.id}`, { method: "PATCH", body: JSON.stringify({ ...edit, version: detail.version, assign_to_me: true }) }); await openTicket(detail.id); await loadTickets(); }); }}>
          <label htmlFor="support-ticket-status">Статус</label><select id="support-ticket-status" disabled={busy} value={edit.status} onChange={event => setEdit({ ...edit, status: event.target.value })}>{Object.entries(STATUS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
          <label htmlFor="support-resolution">Решение (обязательно для закрытия)</label><textarea id="support-resolution" maxLength={4000} required={edit.status === "resolved"} value={edit.resolution} onChange={event => setEdit({ ...edit, resolution: event.target.value })} />
          <label htmlFor="support-comment">Комментарий, видимый автору заявки</label><textarea id="support-comment" maxLength={2000} value={edit.comment} onChange={event => setEdit({ ...edit, comment: event.target.value })} />
          <button className="support-primary" disabled={busy}>Сохранить и назначить на себя</button><button type="button" disabled={busy} onClick={() => run(() => openTicket(detail.id))}>Обновить карточку</button>
        </form>}
        <h3>История изменений</h3>{detail.events.map(event => <p key={event.id}>{new Date(event.created_at).toLocaleString()} · {STATUS[event.payload.status]} · {event.payload.comment || event.payload.resolution || "Заявка зарегистрирована"}</p>)}
        <details><summary>Диалог диагностики</summary>{detail.history.map((message, index) => <p key={index}><strong>{message.role === "user" ? "Пользователь" : "Диагност"}:</strong> {message.content}</p>)}</details>
      </> : <>
        <div className="support-list-tools"><label>Статус <select disabled={busy} value={filter} onChange={event => run(() => loadTickets(view, 0, event.target.value))}><option value="">Все</option>{Object.entries(STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button disabled={busy} onClick={() => run(() => loadTickets())}>Обновить</button></div>
        {!tickets.length && <p>Заявок пока нет.</p>}
        {tickets.map(ticket => <button className="support-ticket-card" key={ticket.id} disabled={busy} onClick={() => run(() => openTicket(ticket.id))}><span>{STATUS[ticket.status]} · {new Date(ticket.created_at).toLocaleString()}</span><strong>{ticket.details.problem || "Обращение в поддержку"}</strong><small>{ticket.id}</small></button>)}
        <div className="support-actions"><button disabled={busy || page === 0} onClick={() => run(() => loadTickets(view, page - 1))}>Назад</button><span>Страница {page + 1}</span><button disabled={busy || !hasNext} onClick={() => run(() => loadTickets(view, page + 1))}>Далее</button></div>
      </>}
    </section>
  </div>, document.body);
}
