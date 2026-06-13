import type { AuthConfig } from "./types";

const TOKEN_STORAGE = "tryops.oidc.token";
const STATE_STORAGE = "tryops.oidc.state";
const VERIFIER_STORAGE = "tryops.oidc.verifier";

export interface OidcTokenState {
  accessToken: string;
  idToken?: string;
  refreshToken?: string;
  expiresAt: number;
  refreshExpiresAt?: number;
}

interface TokenResponse {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  expires_in?: number;
  refresh_expires_in?: number;
}

export function loadStoredOidcToken(): OidcTokenState | undefined {
  try {
    const raw = localStorage.getItem(TOKEN_STORAGE);
    if (!raw) {
      return undefined;
    }
    const parsed = JSON.parse(raw) as OidcTokenState;
    if (!parsed.accessToken) {
      clearStoredOidcToken();
      return undefined;
    }
    if (parsed.expiresAt <= Date.now() + 30_000 && !canRefresh(parsed)) {
      clearStoredOidcToken();
      return undefined;
    }
    return parsed;
  } catch {
    clearStoredOidcToken();
    return undefined;
  }
}

export function clearStoredOidcToken(): void {
  localStorage.removeItem(TOKEN_STORAGE);
  sessionStorage.removeItem(STATE_STORAGE);
  sessionStorage.removeItem(VERIFIER_STORAGE);
}

export async function completeOidcRedirect(config: AuthConfig): Promise<OidcTokenState | undefined> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const state = params.get("state");
  const error = params.get("error");
  if (error) {
    cleanLocation();
    throw new Error(params.get("error_description") || error);
  }
  if (!code) {
    return refreshOidcToken(config, loadStoredOidcToken());
  }
  if (!state || state !== sessionStorage.getItem(STATE_STORAGE)) {
    cleanLocation();
    throw new Error("OIDC state mismatch");
  }
  const verifier = sessionStorage.getItem(VERIFIER_STORAGE);
  if (!verifier) {
    cleanLocation();
    throw new Error("OIDC verifier missing");
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.client_id,
    code,
    code_verifier: verifier,
    redirect_uri: redirectUri()
  });
  const response = await fetch(config.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });
  if (!response.ok) {
    cleanLocation();
    throw new Error(`OIDC token exchange failed: ${response.status}`);
  }
  const stateToStore = storeTokenResponse(await response.json() as TokenResponse);
  sessionStorage.removeItem(STATE_STORAGE);
  sessionStorage.removeItem(VERIFIER_STORAGE);
  cleanLocation();
  return stateToStore;
}

export async function refreshOidcToken(
  config: AuthConfig,
  token: OidcTokenState | undefined = loadStoredOidcToken()
): Promise<OidcTokenState | undefined> {
  if (!token) {
    return undefined;
  }
  if (token.expiresAt > Date.now() + 60_000) {
    return token;
  }
  if (!canRefresh(token)) {
    clearStoredOidcToken();
    return undefined;
  }

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: config.client_id,
    refresh_token: token.refreshToken ?? ""
  });
  const response = await fetch(config.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });
  if (!response.ok) {
    clearStoredOidcToken();
    return undefined;
  }
  return storeTokenResponse(await response.json() as TokenResponse, token);
}

export async function beginOidcLogin(config: AuthConfig, mode: "login" | "register"): Promise<void> {
  const verifier = randomUrlSafe(64);
  const state = randomUrlSafe(32);
  const challenge = await sha256Base64Url(verifier);
  sessionStorage.setItem(STATE_STORAGE, state);
  sessionStorage.setItem(VERIFIER_STORAGE, verifier);

  const endpoint = mode === "register" ? config.registration_endpoint : config.authorization_endpoint;
  const url = new URL(endpoint);
  url.searchParams.set("client_id", config.client_id);
  url.searchParams.set("redirect_uri", redirectUri());
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", config.scopes || "openid profile email");
  url.searchParams.set("state", state);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  window.location.assign(url.toString());
}

export function beginOidcLogout(config: AuthConfig, token?: OidcTokenState): void {
  clearStoredOidcToken();
  const url = new URL(config.logout_endpoint);
  url.searchParams.set("client_id", config.client_id);
  url.searchParams.set("post_logout_redirect_uri", redirectUri());
  if (token?.idToken) {
    url.searchParams.set("id_token_hint", token.idToken);
  }
  window.location.assign(url.toString());
}

function redirectUri(): string {
  return `${window.location.origin}${window.location.pathname}`;
}

function cleanLocation(): void {
  window.history.replaceState({}, document.title, redirectUri());
}

function randomUrlSafe(length: number): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function sha256Base64Url(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return base64Url(new Uint8Array(digest));
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function storeTokenResponse(token: TokenResponse, previous?: OidcTokenState): OidcTokenState {
  const now = Date.now();
  const stateToStore: OidcTokenState = {
    accessToken: token.access_token,
    idToken: token.id_token ?? previous?.idToken,
    refreshToken: token.refresh_token ?? previous?.refreshToken,
    expiresAt: now + Math.max(1, token.expires_in ?? 300) * 1000,
    refreshExpiresAt: token.refresh_expires_in
      ? now + Math.max(1, token.refresh_expires_in) * 1000
      : previous?.refreshExpiresAt
  };
  localStorage.setItem(TOKEN_STORAGE, JSON.stringify(stateToStore));
  return stateToStore;
}

function canRefresh(token: OidcTokenState): boolean {
  return Boolean(
    token.refreshToken
    && (!token.refreshExpiresAt || token.refreshExpiresAt > Date.now() + 30_000)
  );
}
