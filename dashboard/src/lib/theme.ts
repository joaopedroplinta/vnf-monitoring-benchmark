import { useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";
const KEY = "vnf-theme";

const prefersDark = () => matchMedia("(prefers-color-scheme: dark)").matches;

function read(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* armazenamento indisponível */
  }
  return "system";
}

/** Tema claro, escuro ou do sistema, salvo no navegador. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(read);
  const [systemDark, setSystemDark] = useState(prefersDark);
  const dark = mode === "dark" || (mode === "system" && systemDark);

  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const choose = (m: ThemeMode) => {
    setMode(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* sem persistência */
    }
  };

  return { mode, setMode: choose, dark };
}
