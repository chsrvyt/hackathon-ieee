import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, onUnauthorized } from "../api/client";
import { keys } from "../api/hooks";
import type { Role, User } from "../api/types";
import { isNative, setToken } from "../native";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

/**
 * Drop every cached query except the session itself. (QueryClient.clear() would also detach the
 * session observer, leaving this provider unaware of the new user until a full reload.)
 */
function resetCache(qc: QueryClient, user: User | null) {
  qc.cancelQueries({ predicate: (q) => q.queryKey[0] !== keys.me[0] });
  qc.removeQueries({ predicate: (q) => q.queryKey[0] !== keys.me[0] });
  qc.setQueryData(keys.me, user);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return (await api<{ user: User | null }>("/auth/session", { silent401: true })).user;
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.code === "NO_SERVER")) return null;
        throw err;
      }
    },
    staleTime: Infinity,
    retry: 1,
  });

  useEffect(
    () =>
      onUnauthorized(() => {
        // Session expired mid-use: drop all cached data and fall back to the login screen.
        if (isNative()) setToken(null);
        resetCache(qc, null);
      }),
    [qc],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const native = isNative();
      const res = await api<{ user: User; token?: string }>("/auth/login", {
        json: { email, password },
        silent401: true,
        headers: native ? { "X-AttendAI-Client": "mobile" } : undefined,
      });
      if (native && res.token) setToken(res.token);
      resetCache(qc, res.user);
      return res.user;
    },
    [qc],
  );

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", silent401: true });
    } finally {
      if (isNative()) setToken(null);
      resetCache(qc, null);
    }
  }, [qc]);

  const value = useMemo(
    () => ({ user: me.data ?? null, loading: me.isPending, login, logout }),
    [me.data, me.isPending, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export const ROLE_LABEL: Record<Role, string> = {
  STUDENT: "Student",
  MENTOR: "Mentor",
  ADMIN: "Admin / HOD",
  EXAM_CELL: "Exam Cell",
};

export function homePath(role: Role): string {
  return role === "STUDENT" ? "/me" : "/dashboard";
}
