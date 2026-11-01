import { useEffect, useState } from "react";
import { adminRequest } from "../../api/client";
import { Icon } from "../Icons";
import { ROLE_LABELS } from "../AuthScreen";
import AdminEditor from "./AdminEditor";
import "./admin.css";

export const SECTIONS = {
  documents: { title: "База знаний", singular: "Документ", icon: "file", description: "Знания, на которые опираются ответы вашего помощника.", create: "Новый документ" },
  users: { title: "Пользователи", singular: "Пользователь", icon: "users", description: "Команда, учётные записи и роли доступа.", create: "Добавить пользователя" },
  conversations: { title: "Диалоги", singular: "Диалог", icon: "chat", description: "История вопросов и ответов — чтобы понимать, как помогает система.", create: "Создать диалог" },
  escalations: { title: "Эскалации", singular: "Эскалация", icon: "alert", description: "Обращения, которым потребовалась помощь специалиста.", create: "Создать обращение" },
};
export const DELIVERY = { pending: "Ожидает отправки", sent: "Уведомление отправлено", failed: "Ошибка отправки" };
export const dateLabel = (value) => value ? new Date(value).toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" }) : "—";
export function errorLabel(error) {
  if (error.status === 403) return "Доступ запрещён. Проверьте роль аккаунта и разрешённый адрес сайта.";
  if (error.status === 409) return "Операция невозможна: запись уже существует или связана с другими данными. Документы из старых ответов и собственный аккаунт удалить нельзя.";
  if ([502, 504].includes(error.status)) return "Сервер не ответил вовремя или источник недоступен. Обновите список перед повтором: операция могла завершиться.";
  if (error.status === 413) return "Документ слишком большой для сервера. Проверьте лимит загрузки Nginx.";
  if (error.status === 422) return "Проверьте заполнение полей, формат ссылки, ID диалога и длину пароля (8–72 байта).";
  return error.payload?.message || (typeof error.payload?.detail === "string" ? error.payload.detail : null) || error.userMessage || "Не удалось выполнить операцию.";
}
export function Badge({ value, children }) { return <span className={`ad-badge ad-badge--${value}`}>{children}</span>; }
export function SafeLink({ url }) {
  if (!/^https?:\/\//i.test(url || "")) return <span>Источник не указан</span>;
  return <a href={url} target="_blank" rel="noopener noreferrer">Открыть источник ↗</a>;
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
      <div className="ad-brand"><img src="/logo.png" alt="" /><div><strong>Умный поиск</strong><span>Панель управления</span></div></div>
      <div className="ad-nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <nav aria-label="Разделы администрирования">{Object.entries(SECTIONS).map(([key, item]) => <button key={key} disabled={busy} aria-current={section === key ? "page" : undefined} className={section === key ? "is-active" : ""} onClick={() => setSection(key)}><Icon name={item.icon} /><span>{item.title}</span><span className="ad-nav-arrow">›</span></button>)}</nav>
      <div className="ad-sidebar-bottom"><div className="ad-profile"><span className="ad-avatar">{user.email[0].toUpperCase()}</span><div><strong title={user.email}>{user.email}</strong><small>Администратор</small></div></div><button className="ad-back" disabled={busy} onClick={onBack}>← Вернуться к поиску</button><button className="ad-logout" disabled={busy || logoutBusy} onClick={onLogout}>{logoutBusy ? "Выходим…" : "Выйти из аккаунта"}</button>{logoutError && <p role="alert">{logoutError}</p>}</div>
    </aside>
    <main className="ad-main"><header className="ad-topbar"><span>Администрирование <span>/</span> <strong>{SECTIONS[section].title}</strong></span><span className="ad-workspace-tag">SetRetail10</span></header><Resource key={section} section={section} user={user} onBusy={setBusy} /></main>
  </div>;
}

function Resource({ section, user, onBusy }) {
  const info = SECTIONS[section];
  const [page, setPage] = useState({ items: [], total: 0 });
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [editor, setEditor] = useState(null);
  const [notice, setNotice] = useState("");
  const limit = 25;
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setLoading(true); setError("");
    adminRequest(`${section}?limit=${limit}&offset=${offset}`, { signal: controller.signal }).then((data) => {
      if (!active) return;
      if (offset > 0 && offset >= data.total) { setOffset(Math.max(0, Math.floor((data.total - 1) / limit) * limit)); return; }
      setPage(data);
    }).catch((e) => { if (active) setError(errorLabel(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [section, offset, revision]);
  const rows = page.items.filter((row) => [row.title, row.email, row.question, String(row.id)].some((v) => v?.toLowerCase().includes(query.toLowerCase())) && (!filter || (row.status || row.role || row.source_type) === filter));
  const filters = section === "users" ? ROLE_LABELS : section === "escalations" ? DELIVERY : section === "documents" ? { confluence: "Confluence", manual: "Ручные документы" } : null;
  const refresh = () => setRevision((v) => v + 1);
  return <section className="ad-content">
    <div className="ad-heading"><div><div className="ad-eyebrow">ЦЕНТР УПРАВЛЕНИЯ</div><h1>{info.title}</h1><p>{info.description}</p></div><div className="ad-heading-actions">{section === "documents" && <button className="ad-button" onClick={() => { setNotice(""); setEditor({ mode: "import" }); }}>Импорт по ссылке ↗</button>}<button className="ad-button ad-primary" onClick={() => { setNotice(""); setEditor({ mode: "create" }); }}>＋ {info.create}</button></div></div>
    <div className="ad-overview"><div><span className="ad-overview-icon"><Icon name={info.icon} size={24} /></span><div><span>Всего записей</span><strong>{loading || error ? "—" : page.total.toLocaleString("ru-RU")}</strong></div></div><p>{section === "documents" ? "Обновляйте знания здесь. Поиск получит новую версию после успешного индексирования." : section === "escalations" ? "Статус показывает доставку уведомления, а не решение проблемы клиента." : section === "users" ? "Изменение роли начнёт действовать после нового входа пользователя." : "Откройте диалог, чтобы прочитать переписку и посмотреть результат ответа."}</p></div>
    {notice && <div className="ad-notice" role="status">✓ {notice}<button aria-label="Закрыть уведомление" onClick={() => setNotice("")}>×</button></div>}
    <div className="ad-card"><div className="ad-tools"><label className="ad-search"><span aria-hidden="true">⌕</span><input aria-label="Поиск на текущей странице" placeholder="Поиск на этой странице…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>{filters && <select aria-label="Фильтр текущей страницы" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">Все {section === "users" ? "роли" : section === "escalations" ? "статусы" : "источники"}</option>{Object.entries(filters).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}<button className="ad-button" disabled={loading} onClick={refresh}>↻ Обновить</button></div>
      {loading ? <div className="ad-empty" role="status"><span className="ad-spinner" />Загружаем записи…</div> : error ? <div className="ad-empty"><p role="alert">{error}</p><button className="ad-button" onClick={refresh}>Повторить</button></div> : rows.length === 0 ? <div className="ad-empty"><Icon name={info.icon} size={36} /><h3>{page.total ? "Ничего не найдено на этой странице" : "Здесь пока нет записей"}</h3><p>{page.total ? "Измените фильтры или перейдите на другую страницу." : "Добавьте первую запись с помощью кнопки выше."}</p></div> : <div className="ad-table-scroll"><table className="ad-table"><thead><tr><th>{section === "users" ? "Пользователь" : section === "escalations" ? "Обращение" : "Название"}</th><th>{section === "users" ? "Роль" : section === "escalations" ? "Доставка уведомления" : section === "documents" ? "Источник" : "Идентификатор"}</th><th>{section === "users" ? "ID" : "Дата"}</th><th><span className="ad-sr">Действия</span></th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><button className="ad-record" onClick={() => setEditor({ mode: "edit", row })}><span className="ad-record-icon"><Icon name={info.icon} /></span><span><strong>{row.title || row.email || row.question}</strong><small>{section === "documents" ? (row.source_url || "Документ") : section === "escalations" ? row.reason : section === "users" ? (row.id === user.id ? "Это вы" : `Учётная запись #${row.id}`) : `Диалог · ${String(row.id).slice(0, 8)}`}</small></span></button></td><td>{section === "users" ? <Badge value={row.role}>{ROLE_LABELS[row.role] || row.role}</Badge> : section === "escalations" ? <Badge value={row.status}>{DELIVERY[row.status] || row.status}</Badge> : section === "documents" ? <Badge value={row.source_type}>{row.source_type === "confluence" ? "Confluence" : row.source_type === "manual" ? "Вручную" : row.source_type}</Badge> : <code>{String(row.id).slice(0, 8)}</code>}</td><td className="ad-date">{section === "users" ? `#${row.id}` : dateLabel(row.updated_at || row.created_at)}</td><td><button className="ad-row-open" aria-label={`Открыть: ${row.title || row.email || row.question}`} onClick={() => setEditor({ mode: "edit", row })}>↗</button></td></tr>)}</tbody></table></div>}
      <footer className="ad-pagination"><span>{!loading && !error ? `Показано ${rows.length} · ${page.total ? offset + 1 : 0}–${Math.min(offset + limit, page.total)} из ${page.total}` : "Список записей"}</span><div><button className="ad-button" aria-label="Предыдущая страница" disabled={loading || offset === 0} onClick={() => setOffset((v) => Math.max(0, v - limit))}>←</button><span>Стр. {Math.floor(offset / limit) + 1}</span><button className="ad-button" aria-label="Следующая страница" disabled={loading || !!error || offset + limit >= page.total} onClick={() => setOffset((v) => v + limit)}>→</button></div></footer>
    </div>
    {editor && <AdminEditor section={section} editor={editor} user={user} onBusy={onBusy} onClose={() => setEditor(null)} onSaved={(message) => { setEditor(null); setNotice(message); refresh(); }} />}
  </section>;
}
