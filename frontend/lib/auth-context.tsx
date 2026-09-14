"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { getProfile, login, logout, register } from "@/services/auth-service";
import type { User } from "@/types/auth";

type AuthContextValue = {
  user: User | null;
  busy: boolean;
  initialLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: Record<string, string>) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (user: User | null) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  // Session rehydration on mount
  useEffect(() => {
    let mounted = true;
    const hasSessionCookie = document.cookie.includes("csrftoken=");
    if (!hasSessionCookie) {
      setInitialLoading(false);
      return () => {
        mounted = false;
      };
    }
    getProfile()
      .then(({ data }) => {
        if (mounted) setUser(data);
      })
      .catch(() => {
        if (mounted) setUser(null);
      })
      .finally(() => {
        if (mounted) setInitialLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function refreshUser() {
    try {
      const { data } = await getProfile();
      setUser(data);
    } catch {
      setUser(null);
    }
  }

  async function signIn(email: string, password: string) {
    setBusy(true);
    try {
      setUser(await login(email, password));
    } finally {
      setBusy(false);
    }
  }

  async function signUp(payload: Record<string, string>) {
    setBusy(true);
    try {
      await register(payload);
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    try {
      await logout();
      setUser(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthContext.Provider
      value={{ user, busy, initialLoading, signIn, signUp, signOut, refreshUser, setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}

export async function loadCurrentUser() {
  const response = await getProfile();
  return response.data;
}
