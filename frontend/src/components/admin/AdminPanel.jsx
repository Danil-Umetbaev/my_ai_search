import { isSourceUrl } from "../../knowledge";
import { useEffect, useState } from "react";
import { adminRequest } from "../../api/client";
import { Icon } from "../Icons";
import { ROLE_LABELS } from "../AuthScreen";
import AdminEditor from "./AdminEditor";
import "./admin.css";

export const SECTIONS = {
  documents: { title: "База знаний", singular: "Документ", icon: "file" },
  escalations: { title: "Обращения", singular: "Обращение", icon: "alert" },
  unanswered: { title: "Без ответа", singular: "Вопрос без ответа", icon: "search" },
  conversations: { title: "Диалоги", singular: "Диалог", icon: "chat" },
  users: { title: "Пользователи", singular: "Пользователь", icon: "users" },
};
export const DELIVERY = { pending: "Не отправлено", sent: "Отправлено", failed: "Ошибка отправки" };
export const WORK = { new: "Новое", in_progress: "В работе", resolved: "Решено", closed: "Закрыто" };
export const dateLabel = (value) => value ? new Date(value).toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" }) : "—";
export function errorLabel(error) {
  if (error.status === 403) return "Нет доступа. Проверьте аккаунт и разрешённый адрес сайта.";
  if (error.status === 409) return "Не удалось сохранить: проверьте заполненные поля и актуальность записи. Для обращения в работе нужен ответственный, для закрытия — итог.";
  if ([502, 504].includes(error.status) && error.code !== "NOTIFICATION_FAILED") return "Сервер или источник не ответил. Обновите список перед повтором: операция могла завершиться.";
  if (error.status === 413) return "Документ слишком большой для загрузки.";
  if (error.status === 422) return "Проверьте заполнение полей и формат ссылки.";
  return error.payload?.message || (typeof error.payload?.detail === "string" ? error.payload.detail : null) || error.userMessage || "Не удалось выполнить операцию.";
}
export function Badge({ value, children }) { return <span className={`ad-badge ad-badge--${value}`}>{children}</span>; }
export function SafeLink({ url }) {
  if (!isSourceUrl(url)) return null;
  return <a href={url} target="_blank" rel="noopener noreferrer">Источник ↗</a>;
}

export default function AdminPanel({ user, onBack, onLogout, logoutBusy, logoutError }) {
  const [section, setSection] = useState("documents");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!busy) return;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);
  return <div className="ad-shell">
    <aside className="ad-sidebar">
      <div className="ad-brand"><img src="/logo.png" alt="" /><div><strong>Умный поиск</strong><span>Управление</span></div></div>
      <nav aria-label="Разделы">{Object.entries(SECTIONS).map(([key, item]) => <button key={key} disabled={busy} aria-current={section === key ? "page" : undefined} className={section === key ? "is-active" : ""} onClick={() => setSection(key)}><Icon name={item.icon} /><span>{item.title}</span></button>)}</nav>
      <div className="ad-sidebar-bottom"><div className="ad-profile"><span className="ad-avatar">{user.email[0].toUpperCase()}</span><div><strong title={user.email}>{user.email}</strong><small>Администратор</small></div></div><button className="ad-back" disabled={busy} onClick={onBack}>← К поиску</button><button className="ad-logout" disabled={busy || logoutBusy} onClick={onLogout}>{logoutBusy ? "Выходим…" : "Выйти"}</button>{logoutError && <p role="alert">{logoutError}</p>}</div>
    </aside>
    <main className="ad-main"><Resource key={section} section={section} user={user} onBusy={setBusy} /></main>
  </div>;
}

function Resource({ section, user, onBusy }) {
  const info = SECTIONS[section];
  const [page, setPage] = useState({ items: [], total: 0 });
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState(section === "escalations" ? "new" : "");
  const [editor, setEditor] = useState(null);
  const [notice, setNotice] = useState("");
  const limit = 25;
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setLoading(true); setError("");
    const extra = section === "documents" ? `&archived=${filter === "archived"}` : section === "escalations" && filter ? `&work_status=${filter}` : "";
    adminRequest(`${section}?limit=${limit}&offset=${offset}${extra}`, { signal: controller.signal }).then((data) => {
      if (!active) return;
      if (offset > 0 && offset >= data.total) { setOffset(Math.max(0, Math.floor((data.total - 1) / limit) * limit)); return; }
      setPage(data);
    }).catch((e) => { if (active) setError(errorLabel(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [section, offset, revision, filter]);
  const filters = section === "escalations" ? { "": "Все обращения", ...WORK } : section === "documents" ? { "": "В поиске", archived: "Архив" } : null;
  const refresh = () => setRevision((v) => v + 1);
  const open = (row) => setEditor({ mode: ["conversations", "unanswered"].includes(section) ? "view" : "edit", row });
  return <section className="ad-content">
    <div className="ad-heading"><div><h1>{info.title}{!loading && !error && <span className="ad-heading-count">{page.total}</span>}</h1>{section === "unanswered" && <p>Вопросы, для которых не нашлось ответа в базе знаний.</p>}</div>{section === "documents" && <div className="ad-heading-actions"><button className="ad-button" onClick={() => setEditor({ mode: "create" })}>Написать документ</button><button className="ad-button ad-primary" onClick={() => setEditor({ mode: "import" })}>Добавить по ссылке</button></div>}</div>
    {notice && <div className="ad-notice" role="status">✓ {notice}<button aria-label="Закрыть уведомление" onClick={() => setNotice("")}>×</button></div>}
    <div className="ad-card"><div className="ad-tools">{filters && <select aria-label="Показать" value={filter} onChange={(e) => { setFilter(e.target.value); setOffset(0); }}>{Object.entries(filters).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}<button className="ad-button" disabled={loading} onClick={refresh}>↻ Обновить</button></div>
      {loading ? <div className="ad-empty" role="status"><span className="ad-spinner" />Загрузка…</div> : error ? <div className="ad-empty"><p role="alert">{error}</p><button className="ad-button" onClick={refresh}>Повторить</button></div> : !page.items.length ? <div className="ad-empty"><Icon name={info.icon} size={36} /><h3>{section === "escalations" ? "Таких обращений пока нет" : section === "unanswered" ? "Вопросов без ответа пока нет" : "Здесь пока пусто"}</h3></div> : <div className="ad-table-scroll"><table className="ad-table"><thead><tr><th>{section === "users" ? "Пользователь" : ["unanswered", "escalations"].includes(section) ? "Вопрос" : "Название"}</th><th>{section === "users" ? "Роль" : section === "escalations" ? "Статус" : section === "documents" ? "Источник" : "Дата"}</th>{section === "users" && <th>Доступ</th>}<th><span className="ad-sr">Открыть</span></th></tr></thead><tbody>{page.items.map((row) => <tr key={row.id}><td><button className="ad-record" onClick={() => open(row)}><span className="ad-record-icon"><Icon name={info.icon} /></span><span><strong>{row.title || row.email || row.question}</strong>{section === "users" && row.id === user.id && <small>Это вы</small>}{section === "escalations" && <small>{dateLabel(row.created_at)}</small>}</span></button></td><td>{section === "users" ? ROLE_LABELS[row.role] || row.role : section === "escalations" ? <Badge value={row.work_status}>{WORK[row.work_status]}</Badge> : section === "documents" ? <SafeLink url={row.source_url} /> : <span className="ad-date">{dateLabel(row.created_at)}</span>}</td>{section === "users" && <td><Badge value={row.is_active ? "sent" : "failed"}>{row.is_active ? "Открыт" : "Заблокирован"}</Badge></td>}<td><button className="ad-row-open" aria-label="Открыть запись" onClick={() => open(row)}>↗</button></td></tr>)}</tbody></table></div>}
      <footer className="ad-pagination"><span>{!loading && !error ? `${page.total ? offset + 1 : 0}–${Math.min(offset + limit, page.total)} из ${page.total}` : ""}</span><div><button className="ad-button" aria-label="Предыдущая страница" disabled={loading || offset === 0} onClick={() => setOffset((v) => Math.max(0, v - limit))}>←</button><button className="ad-button" aria-label="Следующая страница" disabled={loading || !!error || offset + limit >= page.total} onClick={() => setOffset((v) => v + limit)}>→</button></div></footer>
    </div>
    {editor && <AdminEditor section={section} editor={editor} user={user} onBusy={onBusy} onClose={() => setEditor(null)} onSaved={(message) => { setEditor(null); setNotice(message); refresh(); }} />}
  </section>;
}
