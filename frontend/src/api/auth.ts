import { apiRequest, setToken } from "./client";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserPublic,
} from "../types/api";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const token = await apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  setToken(token.access_token);
  return token;
}

export function register(details: RegisterRequest): Promise<UserPublic> {
  return apiRequest<UserPublic>("/auth/register", {
    method: "POST",
    body: JSON.stringify(details),
  });
}

export function logout(): void {
  setToken(null);
}
