use std::{
    collections::HashMap,
    env, fs,
    path::{Path, PathBuf},
    time::{Duration, SystemTime, UNIX_EPOCH},
};

use axum::http::{HeaderMap, Method, StatusCode};
use jsonwebtoken::{
    decode, decode_header,
    jwk::JwkSet,
    Algorithm, DecodingKey, Validation,
};
use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(Clone, Debug, Default)]
pub(crate) struct AuthPreflight {
    registry: ApiKeyRegistry,
    jwt_secret: Option<String>,
    oidc: Option<OidcVerifier>,
}

#[derive(Clone, Debug, Default, Deserialize)]
struct ApiKeyRegistry {
    #[serde(default)]
    keys: Vec<ApiKeyEntry>,
}

#[derive(Clone, Debug, Deserialize)]
struct ApiKeyEntry {
    key_id: String,
    role: String,
    key_hash_sha256: String,
    scopes: Vec<String>,
    #[serde(default = "default_active")]
    active: bool,
}

#[derive(Clone, Debug)]
struct OidcVerifier {
    issuer: Option<String>,
    audience: Option<String>,
    client_id: Option<String>,
    jwks: JwkSet,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct AuthPrincipal {
    pub(crate) key_id: String,
    pub(crate) subject: String,
    pub(crate) email: Option<String>,
    pub(crate) username: Option<String>,
    pub(crate) display_name: Option<String>,
    pub(crate) provider: &'static str,
    pub(crate) role: String,
    pub(crate) scopes: Vec<String>,
}

#[derive(Debug, Clone)]
pub(crate) struct AuthDecision {
    pub(crate) allowed: bool,
    pub(crate) reason: &'static str,
    pub(crate) required_scope: &'static str,
    pub(crate) principal: Option<AuthPrincipal>,
}

#[derive(Debug, Deserialize)]
struct JwtHeader {
    alg: String,
}

#[derive(Debug, Clone, Deserialize)]
struct JwtClaims {
    sub: Option<String>,
    preferred_username: Option<String>,
    email: Option<String>,
    name: Option<String>,
    role: Option<String>,
    scope: Option<String>,
    scopes: Option<Vec<String>>,
    realm_access: Option<KeycloakRealmAccess>,
    resource_access: Option<HashMap<String, KeycloakClientAccess>>,
    exp: Option<u64>,
}

#[derive(Debug, Clone, Deserialize)]
struct KeycloakRealmAccess {
    #[serde(default)]
    roles: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct KeycloakClientAccess {
    #[serde(default)]
    roles: Vec<String>,
}

fn default_active() -> bool {
    true
}

impl AuthPreflight {
    pub(crate) async fn from_env() -> Self {
        let registry_path = env::var("TRYOPS_GATEWAY_API_KEYS_PATH")
            .ok()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("configs/api_keys.json"));
        let registry = load_registry(&registry_path).unwrap_or_else(|error| {
            panic!(
                "load TRYOPS_GATEWAY_API_KEYS_PATH '{}': {error}",
                registry_path.display()
            )
        });
        Self {
            registry,
            jwt_secret: env::var("TRYOPS_GATEWAY_JWT_HS256_SECRET")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty()),
            oidc: load_oidc_verifier_from_env().await,
        }
    }

    #[cfg(test)]
    pub(crate) fn from_registry_path(path: &Path) -> Self {
        Self {
            registry: load_registry(path).expect("load test API-key registry"),
            jwt_secret: None,
            oidc: None,
        }
    }

    #[cfg(test)]
    fn with_jwt_secret(secret: &str) -> Self {
        Self {
            registry: ApiKeyRegistry::default(),
            jwt_secret: Some(secret.to_string()),
            oidc: None,
        }
    }

    pub(crate) fn evaluate(
        &self,
        headers: &HeaderMap,
        query: Option<&str>,
        body: &[u8],
        required_scope: &'static str,
    ) -> AuthDecision {
        match self.credential(headers, query, body) {
            Some(Credential::ApiKey(value)) => self.evaluate_api_key(&value, required_scope),
            Some(Credential::Jwt(value)) => self.evaluate_jwt(&value, required_scope),
            None => AuthDecision::denied(required_scope, "missing_api_key", None),
        }
    }

    fn credential(
        &self,
        headers: &HeaderMap,
        query: Option<&str>,
        body: &[u8],
    ) -> Option<Credential> {
        if let Some(value) = query.and_then(|query| query_param(query, "api_key")) {
            return Some(Credential::ApiKey(percent_decode_component(&value)));
        }
        if let Some(value) = query.and_then(|query| query_param(query, "access_token")) {
            let token = percent_decode_component(&value);
            if looks_like_jwt(&token) {
                return Some(Credential::Jwt(token));
            }
        }
        if let Some(value) = header_string(headers, "x-api-key") {
            return Some(Credential::ApiKey(value));
        }
        if let Some(value) = bearer_token(headers) {
            if looks_like_jwt(&value) {
                return Some(Credential::Jwt(value));
            }
            return Some(Credential::ApiKey(value));
        }
        body_api_key(body).map(Credential::ApiKey)
    }

    fn evaluate_api_key(&self, api_key: &str, required_scope: &'static str) -> AuthDecision {
        let key_hash = sha256_hex(api_key.trim().as_bytes());
        let Some(entry) =
            self.registry.keys.iter().find(|entry| {
                entry.active && entry.key_hash_sha256.eq_ignore_ascii_case(&key_hash)
            })
        else {
            return AuthDecision::denied(required_scope, "invalid_api_key", None);
        };
        let principal = AuthPrincipal {
            key_id: entry.key_id.clone(),
            subject: entry.key_id.clone(),
            email: None,
            username: Some(entry.key_id.clone()),
            display_name: Some(entry.key_id.clone()),
            provider: "api_key",
            role: entry.role.clone(),
            scopes: entry.scopes.clone(),
        };
        authorize_principal(principal, required_scope)
    }

    fn evaluate_jwt(&self, token: &str, required_scope: &'static str) -> AuthDecision {
        let claims = if let Some(oidc) = &self.oidc {
            match verify_rs256_jwt(token, oidc) {
                Some(claims) => claims,
                None => {
                    return AuthDecision::denied(required_scope, "invalid_jwt", None);
                }
            }
        } else if let Some(secret) = self.jwt_secret.as_deref() {
            let Some(claims) = verify_hs256_jwt(token, secret.as_bytes()) else {
                return AuthDecision::denied(required_scope, "invalid_jwt", None);
            };
            claims
        } else {
            return AuthDecision::denied(required_scope, "jwt_not_configured", None);
        };
        if let Some(exp) = claims.exp {
            if exp < unix_now_seconds() {
                return AuthDecision::denied(required_scope, "expired_jwt", None);
            }
        }
        let Some(subject) = jwt_subject(&claims) else {
            return AuthDecision::denied(required_scope, "invalid_jwt", None);
        };
        let roles = jwt_roles(&claims, self.oidc.as_ref().and_then(|oidc| oidc.client_id.as_deref()));
        let scopes = jwt_scopes(&claims, &roles);
        let role = jwt_role(&claims, &roles);
        let principal = AuthPrincipal {
            key_id: subject.clone(),
            subject,
            email: claims.email,
            username: claims.preferred_username,
            display_name: claims.name,
            provider: "keycloak",
            role,
            scopes,
        };
        authorize_principal(principal, required_scope)
    }
}

impl AuthDecision {
    fn denied(
        required_scope: &'static str,
        reason: &'static str,
        principal: Option<AuthPrincipal>,
    ) -> Self {
        Self {
            allowed: false,
            reason,
            required_scope,
            principal,
        }
    }
}

enum Credential {
    ApiKey(String),
    Jwt(String),
}

pub(crate) fn required_scope(method: &Method, proxy_path: &str) -> Option<&'static str> {
    match (method.as_str(), proxy_path) {
        ("GET", "/v1/auth/session") => Some("session:read"),
        ("POST", "/v1/accounts/bootstrap") => Some("session:read"),
        ("POST", "/v1/accounts") => Some("session:read"),
        ("GET", "/v1/accounts") | ("GET", "/v1/profiles/search") => Some("account:read"),
        ("GET", "/v1/account/dashboard")
        | ("GET", "/v1/account/quota")
        | ("GET", "/v1/account/members") => Some("account:read"),
        (_, path) if path.starts_with("/v1/accounts/") => Some("account:read"),
        ("POST", "/v1/llm/generate")
        | ("POST", "/v1/vton/infer")
        | ("POST", "/v1/vton/upload")
        | ("POST", "/v1/vton/jobs") => Some("workload:run"),
        ("GET", "/v1/dashboard")
        | ("GET", "/v1/evaluations/summary")
        | ("GET", "/v1/history")
        | ("GET", "/v1/models")
        | ("GET", "/v1/vton/comparison") => Some("admin:read"),
        ("GET", "/v1/artifacts/file") => Some("account:read"),
        ("GET", path) if path.starts_with("/v1/request/") => Some("admin:read"),
        ("GET", path) if path.starts_with("/v1/lineage/") => Some("lineage:read"),
        ("POST", "/v1/lineage") => Some("lineage:create"),
        ("POST", "/v1/promotion/evaluate") => Some("promotion:evaluate"),
        ("POST", path) if path.starts_with("/v1/models/") && path.ends_with("/promote") => {
            Some("promotion:evaluate")
        }
        _ => None,
    }
}

pub(crate) fn auth_status(reason: &str) -> StatusCode {
    match reason {
        "missing_scope" => StatusCode::FORBIDDEN,
        _ => StatusCode::UNAUTHORIZED,
    }
}

fn authorize_principal(principal: AuthPrincipal, required_scope: &'static str) -> AuthDecision {
    if principal.scopes.iter().any(|scope| scope == required_scope)
        || (required_scope == "account:read"
            && principal.scopes.iter().any(|scope| scope == "admin:read"))
    {
        AuthDecision {
            allowed: true,
            reason: "authorized",
            required_scope,
            principal: Some(principal),
        }
    } else {
        AuthDecision::denied(required_scope, "missing_scope", Some(principal))
    }
}

fn load_registry(path: &Path) -> Result<ApiKeyRegistry, String> {
    let content = fs::read_to_string(path)
        .or_else(|error| {
            if path.is_relative() {
                let fallback = Path::new("../../..").join(path);
                fs::read_to_string(&fallback).map_err(|_| error)
            } else {
                Err(error)
            }
        })
        .map_err(|error| error.to_string())?;
    serde_json::from_str::<ApiKeyRegistry>(&content).map_err(|error| error.to_string())
}

async fn load_oidc_verifier_from_env() -> Option<OidcVerifier> {
    let jwks_url = env::var("TRYOPS_GATEWAY_OIDC_JWKS_URL")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())?;
    let issuer = optional_env("TRYOPS_GATEWAY_OIDC_ISSUER");
    let audience = optional_env("TRYOPS_GATEWAY_OIDC_AUDIENCE");
    let client_id = optional_env("TRYOPS_GATEWAY_OIDC_CLIENT_ID");
    let jwks = fetch_jwks_with_retry(&jwks_url)
        .await
        .unwrap_or_else(|error| panic!("load TRYOPS_GATEWAY_OIDC_JWKS_URL '{jwks_url}': {error}"));
    Some(OidcVerifier {
        issuer,
        audience,
        client_id,
        jwks,
    })
}

async fn fetch_jwks_with_retry(url: &str) -> Result<JwkSet, String> {
    let attempts = env::var("TRYOPS_GATEWAY_OIDC_JWKS_RETRIES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(30);
    let delay_ms = env::var("TRYOPS_GATEWAY_OIDC_JWKS_RETRY_DELAY_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1000);
    let mut last_error = String::new();
    for attempt in 0..attempts {
        match reqwest::get(url).await {
            Ok(response) => match response.error_for_status() {
                Ok(response) => {
                    return response
                        .json::<JwkSet>()
                        .await
                        .map_err(|error| format!("parse JWKS: {error}"));
                }
                Err(error) => last_error = error.to_string(),
            },
            Err(error) => last_error = error.to_string(),
        }
        if attempt + 1 < attempts {
            tokio::time::sleep(Duration::from_millis(delay_ms)).await;
        }
    }
    Err(last_error)
}

fn optional_env(name: &str) -> Option<String> {
    env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn verify_rs256_jwt(token: &str, oidc: &OidcVerifier) -> Option<JwtClaims> {
    let header = match decode_header(token) {
        Ok(header) => header,
        Err(error) => {
            tracing::warn!(error = %error, "oidc_jwt_header_decode_failed");
            return None;
        }
    };
    if header.alg != Algorithm::RS256 {
        tracing::warn!(algorithm = ?header.alg, "oidc_jwt_unexpected_algorithm");
        return None;
    }
    let Some(kid) = header.kid else {
        tracing::warn!("oidc_jwt_missing_kid");
        return None;
    };
    let Some(jwk) = oidc.jwks.find(&kid) else {
        tracing::warn!(kid = %kid, "oidc_jwt_unknown_kid");
        return None;
    };
    let decoding_key = match DecodingKey::from_jwk(jwk) {
        Ok(key) => key,
        Err(error) => {
            tracing::warn!(error = %error, kid = %kid, "oidc_jwk_decode_failed");
            return None;
        }
    };
    let mut validation = Validation::new(Algorithm::RS256);
    if let Some(audience) = &oidc.audience {
        validation.set_audience(&[audience]);
    } else {
        validation.validate_aud = false;
    }
    if let Some(issuer) = &oidc.issuer {
        validation.set_issuer(&[issuer]);
    }
    match decode::<JwtClaims>(token, &decoding_key, &validation) {
        Ok(data) => Some(data.claims),
        Err(error) => {
            tracing::warn!(
                error = %error,
                kid = %kid,
                issuer = ?oidc.issuer,
                audience = ?oidc.audience,
                "oidc_jwt_validation_failed"
            );
            None
        }
    }
}

fn body_api_key(body: &[u8]) -> Option<String> {
    if body.is_empty() {
        return None;
    }
    let value = serde_json::from_slice::<serde_json::Value>(body).ok()?;
    value
        .get("api_key")
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn header_string(headers: &HeaderMap, name: &str) -> Option<String> {
    headers
        .get(name)
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn bearer_token(headers: &HeaderMap) -> Option<String> {
    let value = header_string(headers, "authorization")?;
    value
        .strip_prefix("Bearer ")
        .or_else(|| value.strip_prefix("bearer "))
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn query_param(query: &str, name: &str) -> Option<String> {
    query.split('&').find_map(|pair| {
        let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
        if percent_decode_component(key) == name {
            Some(value.to_string())
        } else {
            None
        }
    })
}

fn percent_decode_component(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            if let (Some(high), Some(low)) =
                (hex_value(bytes[index + 1]), hex_value(bytes[index + 2]))
            {
                decoded.push((high << 4) | low);
                index += 3;
                continue;
            }
        }
        decoded.push(if bytes[index] == b'+' {
            b' '
        } else {
            bytes[index]
        });
        index += 1;
    }
    String::from_utf8_lossy(&decoded).to_string()
}

fn hex_value(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

fn looks_like_jwt(value: &str) -> bool {
    value.split('.').count() == 3
}

fn verify_hs256_jwt(token: &str, secret: &[u8]) -> Option<JwtClaims> {
    let mut parts = token.split('.');
    let header_segment = parts.next()?;
    let claims_segment = parts.next()?;
    let signature_segment = parts.next()?;
    if parts.next().is_some() {
        return None;
    }
    let header = serde_json::from_slice::<JwtHeader>(&base64url_decode(header_segment)?).ok()?;
    if header.alg != "HS256" {
        return None;
    }
    let signing_input = format!("{header_segment}.{claims_segment}");
    let expected = hmac_sha256(secret, signing_input.as_bytes());
    let actual = base64url_decode(signature_segment)?;
    if !constant_time_eq(&expected, &actual) {
        return None;
    }
    serde_json::from_slice::<JwtClaims>(&base64url_decode(claims_segment)?).ok()
}

fn jwt_scopes(claims: &JwtClaims, roles: &[String]) -> Vec<String> {
    let mut scopes = claims.scopes.clone().unwrap_or_default();
    if let Some(scope) = &claims.scope {
        scopes.extend(scope.split_whitespace().map(ToOwned::to_owned));
    }
    scopes.push("session:read".to_string());
    scopes.extend(role_scopes(roles));
    scopes.sort();
    scopes.dedup();
    scopes
}

fn jwt_subject(claims: &JwtClaims) -> Option<String> {
    claims
        .sub
        .clone()
        .filter(|value| !value.trim().is_empty())
        .or_else(|| {
            claims
                .preferred_username
                .as_ref()
                .map(|value| value.trim())
                .filter(|value| !value.is_empty())
                .map(|value| format!("keycloak:username:{value}"))
        })
}

fn jwt_roles(claims: &JwtClaims, client_id: Option<&str>) -> Vec<String> {
    let mut roles = Vec::new();
    if let Some(role) = &claims.role {
        roles.push(role.clone());
    }
    if let Some(realm_access) = &claims.realm_access {
        roles.extend(realm_access.roles.iter().cloned());
    }
    if let (Some(resource_access), Some(client_id)) = (&claims.resource_access, client_id) {
        if let Some(client_access) = resource_access.get(client_id) {
            roles.extend(client_access.roles.iter().cloned());
        }
    }
    roles.sort();
    roles.dedup();
    roles
}

fn jwt_role(claims: &JwtClaims, roles: &[String]) -> String {
    if roles
        .iter()
        .any(|role| matches!(role.as_str(), "tryops_platform_admin" | "platform_admin" | "admin"))
    {
        return "platform_admin".to_string();
    }
    if roles
        .iter()
        .any(|role| matches!(role.as_str(), "tryops_account_owner" | "account_owner"))
    {
        return "account_owner".to_string();
    }
    if roles
        .iter()
        .any(|role| matches!(role.as_str(), "tryops_account_viewer" | "account_viewer" | "viewer"))
    {
        return "account_viewer".to_string();
    }
    claims.role.clone().unwrap_or_else(|| "account_member".to_string())
}

fn role_scopes(roles: &[String]) -> Vec<String> {
    let mut scopes = vec!["account:read".to_string(), "workload:run".to_string()];
    for role in roles {
        match role.as_str() {
            "tryops_platform_admin" | "platform_admin" | "admin" => scopes.extend(
                [
                    "admin:read",
                    "account:write",
                    "lineage:read",
                    "lineage:create",
                    "promotion:evaluate",
                ]
                .into_iter()
                .map(ToOwned::to_owned),
            ),
            "tryops_account_owner" | "account_owner" => scopes.push("account:write".to_string()),
            "tryops_account_viewer" | "account_viewer" | "viewer" => {
                scopes.retain(|scope| scope != "workload:run")
            }
            _ => {}
        }
    }
    scopes
}

fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn hmac_sha256(key: &[u8], message: &[u8]) -> Vec<u8> {
    const BLOCK_SIZE: usize = 64;
    let mut normalized_key = if key.len() > BLOCK_SIZE {
        Sha256::digest(key).to_vec()
    } else {
        key.to_vec()
    };
    normalized_key.resize(BLOCK_SIZE, 0);
    let mut outer_key = [0x5c_u8; BLOCK_SIZE];
    let mut inner_key = [0x36_u8; BLOCK_SIZE];
    for (index, byte) in normalized_key.iter().enumerate() {
        outer_key[index] ^= byte;
        inner_key[index] ^= byte;
    }
    let mut inner = Sha256::new();
    inner.update(inner_key);
    inner.update(message);
    let inner_digest = inner.finalize();
    let mut outer = Sha256::new();
    outer.update(outer_key);
    outer.update(inner_digest);
    outer.finalize().to_vec()
}

fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    left.iter()
        .zip(right.iter())
        .fold(0_u8, |acc, (left, right)| acc | (left ^ right))
        == 0
}

fn base64url_decode(value: &str) -> Option<Vec<u8>> {
    let mut buffer = 0_u32;
    let mut bits = 0_u8;
    let mut output = Vec::with_capacity(value.len() * 3 / 4);
    for byte in value.bytes() {
        if byte == b'=' {
            break;
        }
        let digit = base64url_value(byte)? as u32;
        buffer = (buffer << 6) | digit;
        bits += 6;
        while bits >= 8 {
            bits -= 8;
            output.push(((buffer >> bits) & 0xff) as u8);
        }
    }
    Some(output)
}

fn base64url_value(byte: u8) -> Option<u8> {
    match byte {
        b'A'..=b'Z' => Some(byte - b'A'),
        b'a'..=b'z' => Some(byte - b'a' + 26),
        b'0'..=b'9' => Some(byte - b'0' + 52),
        b'-' => Some(62),
        b'_' => Some(63),
        _ => None,
    }
}

fn unix_now_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use axum::http::{HeaderMap, HeaderValue};

    use super::*;

    fn registry_path() -> PathBuf {
        PathBuf::from("../../../configs/api_keys.json")
    }

    #[test]
    fn api_key_query_authorizes_required_scope_without_exposing_raw_key() {
        let auth = AuthPreflight::from_registry_path(&registry_path());
        let decision = auth.evaluate(
            &HeaderMap::new(),
            Some("api_key=tryops-viewer-demo-key"),
            &[],
            "admin:read",
        );

        assert!(decision.allowed);
        let principal = decision.principal.unwrap();
        assert_eq!(principal.key_id, "viewer-demo");
        assert_eq!(principal.role, "viewer");
        assert!(principal.scopes.contains(&"admin:read".to_string()));
    }

    #[test]
    fn json_body_key_authorizes_promotion_scope() {
        let auth = AuthPreflight::from_registry_path(&registry_path());
        let decision = auth.evaluate(
            &HeaderMap::new(),
            None,
            br#"{"api_key":"tryops-risk-demo-key","candidate":{"id":"demo"}}"#,
            "promotion:evaluate",
        );

        assert!(decision.allowed);
        assert_eq!(decision.principal.unwrap().role, "risk_reviewer");
    }

    #[test]
    fn api_key_missing_scope_is_forbidden() {
        let auth = AuthPreflight::from_registry_path(&registry_path());
        let decision = auth.evaluate(
            &HeaderMap::new(),
            Some("api_key=tryops-viewer-demo-key"),
            &[],
            "promotion:evaluate",
        );

        assert!(!decision.allowed);
        assert_eq!(decision.reason, "missing_scope");
        assert_eq!(auth_status(decision.reason), StatusCode::FORBIDDEN);
    }

    #[test]
    fn bearer_jwt_authorizes_scope_when_hs256_signature_matches() {
        let auth = AuthPreflight::with_jwt_secret("demo-secret");
        let token = test_jwt(
            "demo-secret",
            r#"{"sub":"oidc-user-1","role":"operator","scope":"admin:read promotion:evaluate","exp":4102444800}"#,
        );
        let mut headers = HeaderMap::new();
        headers.insert(
            "authorization",
            HeaderValue::from_str(&format!("Bearer {token}")).unwrap(),
        );

        let decision = auth.evaluate(&headers, None, &[], "promotion:evaluate");

        assert!(decision.allowed);
        let principal = decision.principal.unwrap();
        assert_eq!(principal.key_id, "oidc-user-1");
        assert_eq!(principal.role, "operator");
    }

    #[test]
    fn bearer_jwt_rejects_expired_or_tampered_tokens() {
        let auth = AuthPreflight::with_jwt_secret("demo-secret");
        let expired = test_jwt(
            "demo-secret",
            r#"{"sub":"oidc-user-1","scope":"admin:read","exp":1}"#,
        );
        let tampered = format!("{}x", expired);
        let mut headers = HeaderMap::new();
        headers.insert(
            "authorization",
            HeaderValue::from_str(&format!("Bearer {expired}")).unwrap(),
        );
        assert_eq!(
            auth.evaluate(&headers, None, &[], "admin:read").reason,
            "expired_jwt"
        );
        headers.insert(
            "authorization",
            HeaderValue::from_str(&format!("Bearer {tampered}")).unwrap(),
        );
        assert_eq!(
            auth.evaluate(&headers, None, &[], "admin:read").reason,
            "invalid_jwt"
        );
    }

    #[test]
    fn bearer_jwt_uses_keycloak_username_when_access_token_has_no_sub() {
        let auth = AuthPreflight::with_jwt_secret("demo-secret");
        let token = test_jwt(
            "demo-secret",
            r#"{"preferred_username":"alice","scope":"openid profile email","exp":4102444800}"#,
        );
        let mut headers = HeaderMap::new();
        headers.insert(
            "authorization",
            HeaderValue::from_str(&format!("Bearer {token}")).unwrap(),
        );

        let decision = auth.evaluate(&headers, None, &[], "session:read");

        assert!(decision.allowed);
        assert_eq!(
            decision.principal.unwrap().subject,
            "keycloak:username:alice"
        );
    }

    #[test]
    fn scopes_match_protected_proxy_routes() {
        assert_eq!(
            required_scope(&Method::GET, "/v1/evaluations/summary"),
            Some("admin:read")
        );
        assert_eq!(
            required_scope(&Method::GET, "/v1/auth/session"),
            Some("session:read")
        );
        assert_eq!(
            required_scope(&Method::POST, "/v1/promotion/evaluate"),
            Some("promotion:evaluate")
        );
        assert_eq!(required_scope(&Method::GET, "/v1/health"), None);
        assert_eq!(
            required_scope(&Method::POST, "/v1/llm/generate"),
            Some("workload:run")
        );
    }

    fn test_jwt(secret: &str, claims: &str) -> String {
        let header = base64url_encode(br#"{"alg":"HS256","typ":"JWT"}"#);
        let claims = base64url_encode(claims.as_bytes());
        let signing_input = format!("{header}.{claims}");
        let signature = base64url_encode(&hmac_sha256(secret.as_bytes(), signing_input.as_bytes()));
        format!("{signing_input}.{signature}")
    }

    fn base64url_encode(bytes: &[u8]) -> String {
        const TABLE: &[u8; 64] =
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        let mut output = String::new();
        let mut index = 0;
        while index < bytes.len() {
            let b0 = bytes[index] as u32;
            let b1 = bytes.get(index + 1).copied().unwrap_or(0) as u32;
            let b2 = bytes.get(index + 2).copied().unwrap_or(0) as u32;
            let triple = (b0 << 16) | (b1 << 8) | b2;
            output.push(TABLE[((triple >> 18) & 0x3f) as usize] as char);
            output.push(TABLE[((triple >> 12) & 0x3f) as usize] as char);
            if index + 1 < bytes.len() {
                output.push(TABLE[((triple >> 6) & 0x3f) as usize] as char);
            }
            if index + 2 < bytes.len() {
                output.push(TABLE[(triple & 0x3f) as usize] as char);
            }
            index += 3;
        }
        output
    }
}
