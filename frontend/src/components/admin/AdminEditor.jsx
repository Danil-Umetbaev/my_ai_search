import { useEffect, useRef, useState } from "react";
import { adminRequest } from "../../api/client";
import { ROLE_LABELS } from "../AuthScreen";
import { DELIVERY, WORK, SECTIONS, dateLabel, errorLabel, SafeLink, Badge } from "./AdminPanel";

const blank = { title: "", content: "", source_url: "", url: "", role: "kassir", assigned_to: "", resolution: "", work_status: "new" };
export default function AdminEditor({ section, editor, user, onBusy, onClose, onSaved }) {
  const editing = editor.mode === "edit";
  const viewing = editor.mode === "view";
  const importing = editor.mode === "import";
  const [record, setRecord] = useState(editor.row || null);
  const [form, setForm] = useState({ ...blank, ...editor.row });
  const [original, setOriginal] = useState(null);
  const [specialists, setSpecialists] = useState([]);
  const [loading, setLoading] = useState(editing);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [retry, setRetry] = useState(0);
  const dirty = viewing ? false : editing ? original && Object.keys(form).some((key) => form[key] !== original[key]) : Object.keys(blank).some((key) => form[key] !== blank[key]);
  const dialog = useRef(null); const locked = useRef(false); const closeRef = useRef(null);
  function close() { if (!locked.current && (!dirty || window.confirm("Закрыть без сохранения?"))) onClose(); }
  closeRef.current = close;
  useEffect(() => {
    const previous = document.activeElement; dialog.current.focus();
    const keydown = (event) => {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key !== "Tab") return;
      const fields = [...dialog.current.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href]')].filter((node) => node.getClientRects().length);
      const first = fields[0], last = fields[fields.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", keydown);
    return () => { document.removeEventListener("keydown", keydown); previous?.isConnected && previous.focus(); };
  }, []);
  useEffect(() => { onBusy(busy); return () => onBusy(false); }, [busy, onBusy]);
  useEffect(() => {
    if (!editing) return;
    let active = true; const controller = new AbortController(); setLoading(true); setError("");
    Promise.all([adminRequest(`${section}/${editor.row.id}`, { signal: controller.signal }), section === "escalations" ? adminRequest("specialists", { signal: controller.signal }) : Promise.resolve([])]).then(([data, people]) => {
      if (!active) return;
      const values = { ...blank, ...data, assigned_to: data.assigned_to == null ? "" : String(data.assigned_to) };
      setRecord(data); setForm(values); setOriginal(values); setSpecialists(people);
    }).catch((e) => { if (active) setError(errorLabel(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [editing, section, editor.row?.id, retry]);
  function change(key, value) { setForm((current) => ({ ...current, [key]: value })); }
  async function perform(action, data) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError("");
    try {
      const id = record?.id;
      if (["archive", "restore", "refresh", "reindex"].includes(action)) await adminRequest(`documents/${id}/${action}`, { method: "POST" });
      else if (action === "retry-notification") await adminRequest(`escalations/${id}/retry-notification`, { method: "POST" });
      else if (action === "block" || action === "unblock") await adminRequest(`users/${id}`, { method: "PATCH", data: { is_active: action === "unblock" } });
      else await adminRequest(importing ? "documents/import" : editing ? `${section}/${id}` : section, { method: editing ? "PATCH" : "POST", data });
      onSaved({ archive: "Документ убран из поиска.", restore: "Документ снова доступен в поиске.", refresh: "Документ обновлён из источника.", reindex: "Индекс обновлён.", block: "Доступ заблокирован. Старые сессии завершены.", unblock: "Доступ открыт. Пользователь может войти снова.", "retry-notification": "Уведомление отправлено." }[action] || (section === "documents" ? "Документ сохранён и доступен в поиске." : "Изменения сохранены."));
    } catch (e) { setError(errorLabel(e)); setConfirmation(null); }
    finally { locked.current = false; setBusy(false); }
  }
  function submit(event) {
    event.preventDefault();
    const keys = importing ? ["url"] : section === "documents" ? (editing ? ["title", "content"] : ["title", "content", "source_url"]) : section === "users" ? ["role"] : ["assigned_to", "work_status", "resolution"];
    if (section === "escalations") {
      if (form.work_status === "in_progress" && !form.assigned_to) { setError("Выберите ответственного."); return; }
      if (["resolved", "closed"].includes(form.work_status) && !form.resolution.trim()) { setError("Кратко напишите, чем закончилось обращение."); return; }
    }
    const data = Object.fromEntries(keys.filter((key) => !editing || form[key] !== original[key]).map((key) => [key, key === "assigned_to" ? (form[key] ? Number(form[key]) : null) : form[key]]));
    if (editing && !Object.keys(data).length) return;
    perform("save", data);
  }
  function field(key, title, options = {}) {
    const { multiline, ...attrs } = options;
    return <label className="ad-field" key={key}><span>{title}</span>{multiline ? <textarea value={form[key] || ""} onChange={(e) => change(key, e.target.value)} required rows={key === "content" ? 16 : 3} {...attrs} /> : <input value={form[key] || ""} onChange={(e) => change(key, e.target.value)} required {...attrs} />}</label>;
  }
  const self = section === "users" && record?.id === user.id;
  const archived = section === "documents" && record?.is_archived;
  const canSave = !viewing && !archived && !(self && section === "users") && (!editing || !!dirty);
  const titles = { archive: "Убрать документ из поиска?", restore: "Вернуть документ в поиск?", refresh: "Заменить текст версией из источника?", reindex: "Перестроить индекс?", block: "Заблокировать доступ?", unblock: "Открыть доступ?" };
  return <div className="ad-overlay"><section className="ad-dialog" ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="ad-editor-title">
    <header className="ad-dialog-header"><h2 id="ad-editor-title">{importing ? "Добавить по ссылке" : section === "users" ? record?.email : SECTIONS[section].singular}</h2><button className="ad-close" disabled={busy} onClick={close} aria-label="Закрыть">×</button></header>
    <div className="ad-dialog-body">
      {error && <div className="ad-error" role="alert">{error}{editing && !original && !loading && <button className="ad-button" onClick={() => setRetry((v) => v + 1)}>Повторить</button>}</div>}
      {loading ? <div className="ad-empty" role="status"><span className="ad-spinner" />Загрузка…</div> : (!editing || original) && <>
        {viewing ? <><h3>{record.title || record.question}</h3><Messages conversationId={section === "conversations" ? record.id : record.conversation_id} /></> : <>
        {archived && <div className="ad-tip">Документ в архиве. Он сохранён, но не используется в новых ответах.</div>}
        <form id="ad-record-form" onSubmit={submit}><fieldset disabled={busy || !!confirmation || archived}>
          {importing ? field("url", "Ссылка на страницу SetRetail10", { type: "url", placeholder: "https://crystals.atlassian.net/wiki/…", maxLength: 2048 }) : section === "documents" ? <>
            {field("title", "Название", { maxLength: 512 })}
            {editing ? <div className="ad-document-meta"><SafeLink url={record.source_url} /></div> : field("source_url", "Ссылка на источник", { type: "url", maxLength: 2048 })}
            {field("content", "Текст", { multiline: true, maxLength: 300000 })}
          </> : section === "users" ? <>
            <label className="ad-field"><span>Роль</span><select value={form.role} disabled={self} onChange={(e) => change("role", e.target.value)}>{Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            {!self && <p className="ad-helper">После смены роли потребуется войти заново.</p>}
            <div className="ad-document-meta"><Badge value={record.is_active ? "sent" : "failed"}>{record.is_active ? "Доступ открыт" : "Доступ заблокирован"}</Badge></div>
          </> : <>
            <h3 className="ad-question">{record.question}</h3>
            <div className="ad-action-line"><button type="button" className="ad-button" disabled={busy || !!dirty || (record.work_status === "in_progress" && record.assigned_to === user.id)} onClick={() => perform("save", { assigned_to: user.id, work_status: "in_progress" })}>Взять в работу</button></div>
            <label className="ad-field"><span>Ответственный</span><select value={form.assigned_to} onChange={(e) => change("assigned_to", e.target.value)}><option value="">Не назначен</option>{form.assigned_to && !specialists.some((p) => String(p.id) === form.assigned_to) && <option value={form.assigned_to}>Недоступный сотрудник — выберите другого</option>}{specialists.map((p) => <option key={p.id} value={p.id}>{p.email}{p.id === user.id ? " (вы)" : ""}</option>)}</select></label>
            <label className="ad-field"><span>Статус</span><select value={form.work_status} onChange={(e) => change("work_status", e.target.value)}>{Object.entries(WORK).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            {field("resolution", "Итог обращения", { multiline: true, maxLength: 4000, required: ["resolved", "closed"].includes(form.work_status), placeholder: "Что сделали или почему закрыли обращение" })}
          </>}
        </fieldset></form>
        {section === "escalations" && <><details className="ad-details"><summary>Переписка</summary><Messages conversationId={record.conversation_id} /></details><div className="ad-delivery"><span>Уведомление VK: {DELIVERY[record.status]}</span>{record.status !== "sent" && <button className="ad-button" disabled={busy || !!dirty} onClick={() => perform("retry-notification")}>Повторить отправку</button>}</div></>}
        {editing && !confirmation && <div className="ad-advanced">
          {section === "documents" && (archived ? <button className="ad-button ad-primary" disabled={busy} onClick={() => setConfirmation("restore")}>Вернуть в поиск</button> : <><div className="ad-action-line">{record.source_type === "confluence" && <button className="ad-button" disabled={busy || !!dirty} onClick={() => setConfirmation("refresh")}>Обновить из источника</button>}<button className="ad-button" disabled={busy || !!dirty} onClick={() => setConfirmation("archive")}>В архив</button></div><details className="ad-details"><summary>Дополнительно</summary><button className="ad-button" disabled={busy || !!dirty} onClick={() => setConfirmation("reindex")}>Перестроить индекс</button></details></>)}
          {section === "users" && !self && <button className={`ad-button ${record.is_active ? "ad-danger" : ""}`} disabled={busy || !!dirty} onClick={() => setConfirmation(record.is_active ? "block" : "unblock")}>{record.is_active ? "Заблокировать доступ" : "Открыть доступ"}</button>}
        </div>}
        </>}
        {confirmation && <div className="ad-confirm" role="alert"><h3>{titles[confirmation]}</h3><p>{confirmation === "archive" ? "Старые ответы и их источники сохранятся. Документ можно вернуть в поиск." : confirmation === "refresh" ? "Ручные правки будут заменены текстом из Confluence." : confirmation === "block" ? "Пользователь не сможет войти. Его текущие сессии перестанут действовать." : confirmation === "unblock" ? "Пользователь сможет войти заново со своим паролем." : "Подготовка документа к поиску может занять некоторое время."}</p><div className="ad-action-line"><button className="ad-button ad-primary" disabled={busy} onClick={() => perform(confirmation)}>Подтвердить</button><button className="ad-button" disabled={busy} onClick={() => setConfirmation(null)}>Отмена</button></div></div>}
      </>}
    </div>
    <footer className="ad-dialog-footer">{busy ? <span className="ad-working" role="status"><span className="ad-spinner" />{section === "documents" ? "Обрабатываем документ…" : "Сохраняем…"}</span> : <><button className="ad-button" onClick={close}>Закрыть</button>{!loading && (!editing || original) && !confirmation && canSave && <button className="ad-button ad-primary" form="ad-record-form" type="submit">{importing ? "Добавить" : "Сохранить"}</button>}</>}</footer>
  </section></div>;
}

function Messages({ conversationId }) {
  const [offset, setOffset] = useState(0); const [page, setPage] = useState(null); const [error, setError] = useState(""); const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; const controller = new AbortController(); setPage(null); setError("");
    adminRequest(`conversations/${conversationId}/messages?limit=20&offset=${offset}`, { signal: controller.signal }).then((data) => { if (active) setPage(data); }).catch((e) => { if (active) setError(errorLabel(e)); });
    return () => { active = false; controller.abort(); };
  }, [conversationId, offset, retry]);
  return <section className="ad-messages">{error ? <div className="ad-error" role="alert">{error}<button className="ad-button" onClick={() => setRetry((v) => v + 1)}>Повторить</button></div> : !page ? <p role="status">Загрузка сообщений…</p> : !page.items.length ? <p>Сообщений пока нет.</p> : <>{page.items.map((message) => <article key={message.id} className={`ad-message ad-message--${message.role}`}><header><strong>{message.role === "user" ? "Пользователь" : "Помощник"}</strong><time>{dateLabel(message.created_at)}</time></header><p>{message.content}</p>{message.response_meta?.sources?.map((source, i) => <div className="ad-message-source" key={i}><span>{source.title}</span> <SafeLink url={source.url} /></div>)}</article>)}<div className="ad-action-line"><button className="ad-button" disabled={offset === 0} onClick={() => setOffset((n) => Math.max(0, n - 20))}>← Раньше</button><button className="ad-button" disabled={offset + 20 >= page.total} onClick={() => setOffset((n) => n + 20)}>Позже →</button></div></>}</section>;
}
