import { useEffect, useState } from "react";
import App from "../App";
import AuthScreen, { authErrorMessage } from "./AuthScreen";
import { getCurrentUser, logoutUser } from "../api/client";

export default function SessionApp() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("loading");
  const [notice, setNotice] = useState("");
  const [logoutBusy, setLogoutBusy] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    let active = true;
    getCurrentUser().then((current) => {
      if (!active) return;
      if (current?.id && current?.email) {
        setUser(current);
        setView("chat");
      } else setView("auth");
    }).catch((error) => {
      if (!active) return;
      if (error.status !== 401) setNotice(authErrorMessage(error));
      setView("auth");
    });
    const expired = () => {
      setUser(null);
      setNotice("Сессия истекла. Войдите снова.");
      setView("auth");
    };
    window.addEventListener("auth:expired", expired);
    return () => {
      active = false;
      window.removeEventListener("auth:expired", expired);
    };
  }, []);

  async function logout() {
    if (logoutBusy) return;
    setLogoutBusy(true);
    setLogoutError("");
    try {
      await logoutUser();
      setUser(null);
      setNotice("");
      setView("auth");
    } catch (error) {
      setLogoutError("Не удалось выйти. Проверьте соединение и попробуйте снова.");
    } finally {
      setLogoutBusy(false);
    }
  }

  if (view === "loading") return (
    <main className="auth-loading" role="status">
      <img src="/logo.png" alt="" />
      <strong>Умный поиск</strong>
      <span>Проверяем вход…</span>
    </main>
  );

  if (view === "auth") return <AuthScreen
    notice={notice}
    onAuthenticated={(current) => { setUser(current); setNotice(""); setLogoutError(""); setView("chat"); }}
    onGuest={() => { setUser(null); setView("chat"); }}
  />;

  return <App
    key={user ? `user-${user.id}` : "guest"}
    user={user}
    onLogin={() => { setNotice(""); setView("auth"); }}
    onLogout={logout}
    logoutBusy={logoutBusy}
    logoutError={logoutError}
  />;
}
