"""Authentication service for frontend."""

import { baseAPI } from "./base";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

const AUTH_KEY = "auth_token";

export const authService = {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const formData = new URLSearchParams();
    formData.append("username", credentials.username);
    formData.append("password", credentials.password);

    const response = await fetch(`${baseAPI}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();
    this.saveToken(data.access_token);
    return data;
  },

  async register(info: RegisterRequest): Promise<User> {
    const response = await fetch(`${baseAPI}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(info),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }

    return response.json();
  },

  async getMe(): Promise<User | null> {
    const token = this.getToken();
    if (!token) return null;

    const response = await fetch(`${baseAPI}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      this.clearToken();
      return null;
    }

    return response.json();
  },

  getToken(): string | null {
    return localStorage.getItem(AUTH_KEY);
  },

  saveToken(token: string): void {
    localStorage.setItem(AUTH_KEY, token);
  },

  clearToken(): void {
    localStorage.removeItem(AUTH_KEY);
  },

  isAuthenticated(): boolean {
    return !!this.getToken();
  },
};