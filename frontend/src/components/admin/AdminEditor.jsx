import { useEffect, useRef, useState } from "react";
import { adminRequest } from "../../api/client";
import { ROLE_LABELS } from "../AuthScreen";
import { DELIVERY, SECTIONS, dateLabel, errorLabel, SafeLink, Badge } from "./AdminPanel";

const blank = { title: "", content: "", source_url: "", url: "", email: "", password: "", role: "kassir", conversation_id: "", question: "", reason: "", status: "pending" };
export default function AdminEditor({ section, editor, user, onBusy, onClose, onSaved }) {
  const editing = editor.mode === "edit";
  const importing = editor.mode === "import";
  const [record, setRecord] = useState(editor.row || null);
  const [form, setForm] = useState({ ...blank, ...editor.row });
  const [original, setOriginal] = useState(null);
  const [loading, setLoading] = useState(editing);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [retry, setRetry] = useState(0);
  const dirty = editing ? original && Object.keys(form).some((key) => form[key] !== original[key]) : Object.keys(blank).some((key) => form[key] !== blank[key]);
  const dialog = useRef(null); const locked = useRef(false); const closeRef = useRef(null);
  function close() { if (!locked.current && (!dirty || window.confirm("Закрыть без сохранения изменений?"))) onClose(); }
  closeRef.current = close;
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current.focus();
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
    let active = true; const controller = new AbortController();
    setLoading(true); setError("");
    adminRequest(`${section}/${editor.row.id}`, { signal: controller.signal }).then((data) => {
      if (!active) return;
      const values = { ...blank, ...data, password: "" };
      setRecord(data); setForm(values); setOriginal(values);
    }).catch((e) => { if (active) setError(errorLabel(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [editing, section, editor.row?.id, retry]);
  function change(key, value) { setForm((current) => ({ ...current, [key]: value })); }
  async function perform(action, data) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError("");
    try {
      const id = record?.id;
      if (action === "delete") await adminRequest(`${section}/${id}`, { method: "DELETE" });
      else if (action === "refresh" || action === "reindex") await adminRequest(`documents/${id}/${action}`, { method: "POST" });
      else await adminRequest(importing ? "documents/import" : editing ? `${section}/${id}` : section, { method: editing ? "PATCH" : "POST", data });
      onSaved(action === "delete" ? "Запись удалена." : action === "reindex" ? "Индекс документа обновлён." : action === "refresh" ? "Документ обновлён из источника и проиндексирован." : section === "documents" ? "Документ сохранён. Индекс готов к поиску." : "Изменения сохранены.");
    } catch (e) { setError(errorLabel(e)); setConfirmation(null); }
    finally { locked.current = false; setBusy(false); }
  }
  function submit(event) {
    event.preventDefault();
    const keys = importing ? ["url"] : section === "documents" ? (editing ? ["title", "content"] : ["title", "content", "source_url"]) : section === "users" ? ["email", "role", "password"] : section === "conversations" ? ["title"] : (editing ? ["question", "reason", "status"] : ["conversation_id", "question", "reason", "status"]);
    if (section === "users" && form.password && new TextEncoder().encode(form.password).length > 72) { setError("Пароль занимает больше 72 байт. Сократите его, особенно если используете кириллицу."); return; }
    const data = Object.fromEntries(keys.filter((key) => !(editing && key === "password" && !form.password) && (!editing || form[key] !== original[key])).map((key) => [key, form[key]]));
    if (editing && !Object.keys(data).length) { setError("Нет изменений для сохранения."); return; }
    perform("save", data);
  }
  function field(key, title, options = {}) {
    const { multiline, hint, ...attrs } = options;
    return <label className="ad-field" key={key}><span>{title}</span>{multiline ? <textarea value={form[key] || ""} onChange={(e) => change(key, e.target.value)} required rows={key === "content" ? 16 : 3} {...attrs} /> : <input value={form[key] || ""} onChange={(e) => change(key, e.target.value)} required {...attrs} />}{hint && <small>{hint}</small>}</label>;
  }
  const self = section === "users" && record?.id === user.id;
  const titles = { delete: "Удалить запись?", refresh: "Обновить из источника?", reindex: "Перестроить индекс?" };
  return <div className="ad-overlay"><section className="ad-dialog" ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="ad-editor-title">
    <header className="ad-dialog-header"><div><span className="ad-eyebrow">{SECTIONS[section].title}</span><h2 id="ad-editor-title">{importing ? "Импорт из базы знаний" : editing ? SECTIONS[section].singular : SECTIONS[section].create}</h2>{record?.id && <small className="ad-id">ID: {record.id}</small>}</div><button className="ad-close" disabled={busy} onClick={close} aria-label="Закрыть">×</button></header>
    <div className="ad-dialog-body">
      {error && <div className="ad-error" role="alert">{error}{editing && !original && !loading && <button className="ad-button" onClick={() => setRetry((v) => v + 1)}>Повторить загрузку</button>}</div>}
      {loading ? <div className="ad-empty" role="status"><span className="ad-spinner" />Загружаем запись…</div> : (!editing || original) && <>
        {importing && <div className="ad-tip">Вставьте ссылку на страницу SetRetail10 в Confluence. Система загрузит текст и подготовит его для поиска.</div>}
        <form id="ad-record-form" onSubmit={submit}><fieldset disabled={busy || !!confirmation}>
          {importing ? field("url", "Ссылка на страницу", { type: "url", placeholder: "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/…", maxLength: 2048 }) : section === "documents" ? <>
            {field("title", "Название документа", { maxLength: 512 })}
            {editing ? <div className="ad-document-meta"><Badge value={record.source_type}>{record.source_type === "confluence" ? "Confluence" : "Ручной документ"}</Badge><SafeLink url={record.source_url} /></div> : field("source_url", "Ссылка на источник", { type: "url", maxLength: 2048, hint: "Будет показана пользователю в источниках ответа." })}
            {field("content", "Текст документа", { multiline: true, maxLength: 300000, hint: `${(form.content || "").length.toLocaleString("ru-RU")} / 300 000 символов · При сохранении текст и заголовок переиндексируются.` })}
          </> : section === "users" ? <>
            {field("email", "Email", { type: "email", maxLength: 100, autoComplete: "off" })}
            <label className="ad-field"><span>Роль</span><select value={form.role} disabled={self} onChange={(e) => change("role", e.target.value)}>{Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select><small>{self ? "Собственную роль администратора изменить нельзя." : "Новая роль применяется после повторного входа. Действующие токены не отзываются."}</small></label>
            {field("password", editing ? "Новый пароль" : "Пароль", { type: "password", autoComplete: "new-password", required: !editing, minLength: 8, maxLength: 72, hint: editing ? "Оставьте пустым, чтобы сохранить текущий пароль." : "От 8 символов, максимум 72 байта." })}
          </> : section === "conversations" ? field("title", "Название диалога", { maxLength: 255 }) : <>
            {field("conversation_id", "ID диалога", { readOnly: editing, placeholder: "UUID существующего диалога" })}
            {field("question", "Вопрос пользователя", { multiline: true, maxLength: 4000 })}
            {field("reason", "Причина обращения", { multiline: true, maxLength: 4000 })}
            <label className="ad-field"><span>Статус доставки</span><select value={form.status} onChange={(e) => change("status", e.target.value)}>{Object.entries(DELIVERY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select><small>Изменение статуса вручную не отправляет сообщение в VK.</small></label>
          </>}
        </fieldset></form>
        {editing && section === "conversations" && <Messages conversationId={record.id} />}
        {editing && !confirmation && <div className="ad-advanced"><h3>Действия с записью</h3>{section === "documents" && <div className="ad-action-line"><button className="ad-button" disabled={busy || !!dirty} onClick={() => setConfirmation("reindex")}>Перестроить индекс</button>{record.source_type === "confluence" && <button className="ad-button" disabled={busy || !!dirty} onClick={() => setConfirmation("refresh")}>Обновить из Confluence</button>}{dirty && <small>Сначала сохраните изменения или заново откройте документ.</small>}</div>}<button className="ad-button ad-danger" disabled={busy || self} onClick={() => setConfirmation("delete")}>Удалить {SECTIONS[section].singular.toLowerCase()}</button></div>}
        {confirmation && <div className="ad-confirm" role="alert"><h3>{titles[confirmation]}</h3><p>{confirmation === "delete" ? section === "conversations" ? "Диалог, все сообщения и связанные эскалации будут удалены без возможности восстановления." : "Это действие нельзя отменить. Связанные со старыми ответами документы защищены от удаления." : confirmation === "refresh" ? "Текст будет заново загружен из Confluence. Ручные правки заменятся версией из источника." : "Индекс будет построен заново по сохранённому тексту. Это может занять некоторое время."}</p><div className="ad-action-line"><button className={`ad-button ${confirmation === "delete" ? "ad-danger" : "ad-primary"}`} disabled={busy} onClick={() => perform(confirmation)}>Подтвердить</button><button className="ad-button" disabled={busy} onClick={() => setConfirmation(null)}>Отмена</button></div></div>}
      </>}
    </div>
    <footer className="ad-dialog-footer">{busy ? <span className="ad-working" role="status"><span className="ad-spinner" />{section === "documents" ? "Выполняем операцию с документом. Дождитесь результата…" : "Сохраняем изменения…"}</span> : <><button className="ad-button" onClick={close}>Закрыть</button>{!loading && (!editing || original) && !confirmation && <button className="ad-button ad-primary" form="ad-record-form" type="submit">{importing ? "Загрузить и проиндексировать" : section === "documents" ? "Сохранить и проиндексировать" : "Сохранить изменения"}</button>}</>}</footer>
  </section></div>;
}

function Messages({ conversationId }) {
  const [offset, setOffset] = useState(0); const [page, setPage] = useState(null); const [error, setError] = useState(""); const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; const controller = new AbortController(); setPage(null); setError("");
    adminRequest(`conversations/${conversationId}/messages?limit=20&offset=${offset}`, { signal: controller.signal }).then((data) => { if (active) setPage(data); }).catch((e) => { if (active) setError(errorLabel(e)); });
    return () => { active = false; controller.abort(); };
  }, [conversationId, offset, retry]);
  return <section className="ad-messages"><h3>Переписка {page && <small>· {page.total} сообщений</small>}</h3>{error ? <div className="ad-error" role="alert">{error}<button className="ad-button" onClick={() => setRetry((v) => v + 1)}>Повторить</button></div> : !page ? <p role="status">Загрузка сообщений…</p> : !page.items.length ? <p>В этом диалоге пока нет сообщений.</p> : <>{page.items.map((message) => <article key={message.id} className={`ad-message ad-message--${message.role}`}><header><strong>{message.role === "user" ? "Пользователь" : "Помощник"}</strong><time>{dateLabel(message.created_at)}</time></header><p>{message.content}</p>{message.response_meta?.status && <Badge value={message.response_meta.status}>{message.response_meta.status}</Badge>}</article>)}<div className="ad-action-line"><button className="ad-button" disabled={offset === 0} onClick={() => setOffset((n) => Math.max(0, n - 20))}>← Раньше</button><span>{offset + 1}–{Math.min(offset + 20, page.total)}</span><button className="ad-button" disabled={offset + 20 >= page.total} onClick={() => setOffset((n) => n + 20)}>Позже →</button></div></>}</section>;
}
