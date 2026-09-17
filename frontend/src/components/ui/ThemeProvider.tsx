import { createContext, useContext, useEffect, useState } from "react"
import { api } from "../../api"

export type Theme = "light" | "dark"

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "light",
  setTheme: () => {},
  toggleTheme: () => {},
})

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const stored = localStorage.getItem("poly-taste-theme") as Theme | null
    if (stored === "light" || stored === "dark") return stored
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  })

  // Reconcile with server-side preference on mount
  useEffect(() => {
    let isMounted = true
    api.preferences.get()
      .then((res) => {
        if (isMounted && res.theme && (res.theme === "light" || res.theme === "dark")) {
          setThemeState(res.theme)
          localStorage.setItem("poly-taste-theme", res.theme)
        }
      })
      .catch(() => {
        // Unauthenticated or network error — keep local theme
      })
    return () => { isMounted = false }
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (theme === "dark") {
      root.classList.add("dark")
    } else {
      root.classList.remove("dark")
    }
    localStorage.setItem("poly-taste-theme", theme)
  }, [theme])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem("poly-taste-theme", newTheme)
    // Fire-and-forget sync to backend
    api.preferences.update(newTheme).catch(() => {})
  }

  const toggleTheme = () => setTheme(theme === "light" ? "dark" : "light")

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
