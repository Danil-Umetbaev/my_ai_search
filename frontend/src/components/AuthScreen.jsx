import { useRef, useState } from "react";
import { loginUser, registerUser, getCurrentUser } from "../api/client";

export const ROLE_LABELS = {
  kassir: "Кассир",
  it: "IT-специалист",
  admin: "Администратор",
};

export function authErrorMessage(error) {
  if (error.status === 401 || error.code === "USER_NOT_FOUND") return "Неверный email или пароль.";
  if (error.status === 409) return "Этот email уже зарегистрирован. Попробуйте войти.";
  if (error.status === 403) return "Вход с этого адреса сайта не разрешён. Обратитесь к администратору.";
  if (error.status === 422) return "Проверьте email и пароль: от 8 символов, не больше 72 байт.";
  if (error.status === 404) return "Сервис авторизации пока недоступен. Попробуйте позже.";
  return error.userMessage || "Не удалось войти. Попробуйте ещё раз.";
}

export default function AuthScreen({ onAuthenticated, onGuest, notice = "" }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [role, setRole] = useState("kassir");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const submitting = useRef(false);
  const registering = mode === "register";

  function changeMode(next) {
    setMode(next);
    setPassword("");
    setConfirmation("");
    setVisible(false);
    setError("");
    setSuccess("");
  }

  async function submit(event) {
    event.preventDefault();
    if (submitting.current) return;
    setError("");
    setSuccess("");
    if ([...password].length < 8 || new TextEncoder().encode(password).length > 72) {
      setError("Пароль должен содержать от 8 символов и занимать не больше 72 байт.");
      return;
    }
    if (registering && password !== confirmation) {
      setError("Пароли не совпадают.");
      return;
    }
    submitting.current = true;
    setBusy(true);
    try {
      if (registering) {
        await registerUser(email.trim(), password, role);
        changeMode("login");
        setSuccess("Аккаунт создан. Войдите с вашим email и паролем.");
      } else {
        await loginUser(email.trim(), password);
        const user = await getCurrentUser();
        if (!user?.id || !user?.email) throw new Error("Пользователь не найден");
        onAuthenticated(user);
      }
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-layout">
        <section className="auth-intro" aria-label="О сервисе">
          <a className="auth-brand" href="/" onClick={(event) => { event.preventDefault(); if (!busy) onGuest(); }}>
            <img src="/logo.png" alt="" />
            <span>Умный поиск<small>База знаний SetRetail10</small></span>
          </a>
          <div className="auth-intro__body">
            <span className="auth-eyebrow">ЗНАНИЯ РЯДОМ</span>
            <h1>Меньше поисков.<br />Больше ясности.</h1>
            <p>Задайте вопрос о SetRetail10 — найдите ответ и проверьте его по источнику.</p>
            <div className="auth-example">
              <span>Например</span>
              <p>Как выполнить возврат по номеру чека?</p>
              <div><span aria-hidden="true">✦</span> Ответы с опорой на документацию</div>
            </div>
          </div>
          <a className="auth-knowledge" href="https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/overview" target="_blank" rel="noreferrer">Открыть базу знаний ↗</a>
        </section>

        <section className="auth-card" aria-labelledby="auth-title">
          <div className="auth-switch" role="group" aria-label="Вход или регистрация">
            <button type="button" aria-pressed={!registering} disabled={busy} onClick={() => changeMode("login")}>Вход</button>
            <button type="button" aria-pressed={registering} disabled={busy} onClick={() => changeMode("register")}>Регистрация</button>
          </div>
          <h2 id="auth-title">{registering ? "Создайте аккаунт" : "Рады видеть вас"}</h2>
          <p className="auth-card__subtitle">{registering ? "Укажите email, пароль и вашу роль." : "Войдите, чтобы продолжить работу."}</p>
          {notice && !success && <p className="auth-notice" role="status">{notice}</p>}
          {success && <p className="auth-success" role="status">{success}</p>}
          <form onSubmit={submit} aria-busy={busy}>
            <fieldset disabled={busy}>
              <label htmlFor="auth-email">Email</label>
              <input id="auth-email" name="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.ru" />
              <label htmlFor="auth-password">Пароль</label>
              <div className="auth-password">
                <input id="auth-password" name="password" type={visible ? "text" : "password"} autoComplete={registering ? "new-password" : "current-password"} required maxLength={72} value={password} onChange={(e) => setPassword(e.target.value)} aria-describedby="auth-password-hint" />
                <button type="button" aria-label={visible ? "Скрыть пароль" : "Показать пароль"} aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? "Скрыть" : "Показать"}</button>
              </div>
              <small id="auth-password-hint" className="auth-hint">От 8 символов, не больше 72 байт</small>
              {registering && <>
                <label htmlFor="auth-confirm">Повторите пароль</label>
                <input id="auth-confirm" name="password-confirmation" type={visible ? "text" : "password"} autoComplete="new-password" required maxLength={72} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />
                <label htmlFor="auth-role">Ваша роль</label>
                <select id="auth-role" name="role" value={role} onChange={(e) => setRole(e.target.value)}>
                  {Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </>}
              {error && <p className="auth-error" role="alert">{error}</p>}
              <button className="auth-submit" type="submit">{busy ? "Подождите…" : registering ? "Создать аккаунт" : "Войти"}<span aria-hidden="true">→</span></button>
            </fieldset>
          </form>
          <div className="auth-divider"><span>или</span></div>
          <button className="auth-guest" type="button" disabled={busy} onClick={onGuest}>Продолжить без входа →</button>
        </section>
      </div>
    </main>
  );
}
