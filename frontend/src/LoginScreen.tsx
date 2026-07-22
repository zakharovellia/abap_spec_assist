import { useState } from "react";
import { login } from "./api";
import { FileTextIcon, LockIcon } from "./icons";

interface LoginScreenProps {
  onSuccess: (username: string) => void;
}

export default function LoginScreen({ onSuccess }: LoginScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password || busy) return;
    setBusy(true);
    setError(null);
    try {
      const authed = await login(username.trim(), password);
      onSuccess(authed);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="brand-mark login-mark">
          <FileTextIcon size={22} />
        </div>
        <h1>ТЗ Ассистент</h1>
        <p className="login-sub">Вход по учётной записи LDAP</p>

        <label className="login-field">
          <span>Логин</span>
          <input
            type="text"
            autoComplete="username"
            autoFocus
            value={username}
            disabled={busy}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>

        <label className="login-field">
          <span>Пароль</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            disabled={busy}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && <div className="login-error">{error}</div>}

        <button
          type="submit"
          className="login-submit"
          disabled={busy || !username.trim() || !password}
        >
          <LockIcon size={16} />
          {busy ? "Проверка…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
