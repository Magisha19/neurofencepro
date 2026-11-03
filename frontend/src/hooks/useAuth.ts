import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { login, logout, register } from "../api/auth";
import { getToken, subscribeToToken } from "../api/client";
import type { LoginRequest, RegisterRequest } from "../types/api";

export function useAuth() {
  const [token, setCurrentToken] = useState<string | null>(getToken);
  const loginMutation = useMutation({ mutationFn: login });
  const registerMutation = useMutation({ mutationFn: register });

  useEffect(() => subscribeToToken(setCurrentToken), []);

  return {
    token,
    login: (credentials: LoginRequest) => loginMutation.mutateAsync(credentials),
    register: (details: RegisterRequest) => registerMutation.mutateAsync(details),
    logout,
    isPending: loginMutation.isPending || registerMutation.isPending,
    error: loginMutation.error ?? registerMutation.error,
    resetError: () => {
      loginMutation.reset();
      registerMutation.reset();
    },
  };
}
