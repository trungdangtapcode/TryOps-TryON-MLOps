use std::{env, fs, sync::Arc};

use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::TcpStream,
    sync::Mutex,
};
use tokio_postgres::{Client, NoTls};

use crate::quota::{
    current_period_key, dimension_limit, usage_dimensions, user_hash, QuotaCheckRequest,
    QuotaDecision, QuotaDimensionCheck,
};

const POSTGRES_DSN_ENV: &str = "TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN";
const POSTGRES_DSN_FILE_ENV: &str = "TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE";
const VALKEY_ADDR_ENV: &str = "TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR";
const VALKEY_PREFIX_ENV: &str = "TRYOPS_GATEWAY_QUOTA_VALKEY_PREFIX";
const VALKEY_TTL_ENV: &str = "TRYOPS_GATEWAY_QUOTA_VALKEY_TTL_SECONDS";
const DEFAULT_VALKEY_TTL_SECONDS: u64 = 172_800;

#[derive(Clone)]
pub(crate) struct QuotaDurableStore {
    postgres: Option<PostgresQuotaStore>,
    valkey: Option<ValkeyQuotaStore>,
}

#[derive(Clone)]
struct PostgresQuotaStore {
    client: Arc<Mutex<Client>>,
}

#[derive(Clone)]
struct ValkeyQuotaStore {
    address: String,
    prefix: String,
    ttl_seconds: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct QuotaUsageDelta {
    period: String,
    user_hash: String,
    plan: String,
    workload: String,
    dimension: String,
    increment: u64,
}

impl QuotaDurableStore {
    pub(crate) async fn from_env() -> Result<Option<Self>, String> {
        let mut errors = Vec::new();
        let postgres = match postgres_dsn_from_env()? {
            Some(dsn) => match PostgresQuotaStore::connect(&dsn).await {
                Ok(store) => Some(store),
                Err(error) => {
                    errors.push(error);
                    None
                }
            },
            None => None,
        };
        let valkey = optional_env(VALKEY_ADDR_ENV).map(ValkeyQuotaStore::from_address);
        if postgres.is_none() && valkey.is_none() {
            if errors.is_empty() {
                return Ok(None);
            }
            return Err(errors.join("; "));
        }
        if !errors.is_empty() {
            tracing::warn!(
                errors = ?errors,
                "durable quota adapter startup degraded"
            );
        }
        Ok(Some(Self { postgres, valkey }))
    }

    pub(crate) fn adapter_names(&self) -> Vec<&'static str> {
        let mut names = Vec::new();
        if self.postgres.is_some() {
            names.push("postgres");
        }
        if self.valkey.is_some() {
            names.push("valkey");
        }
        names
    }

    pub(crate) async fn check_and_record_postgres(
        &self,
        request: QuotaCheckRequest,
    ) -> Result<Option<QuotaDecision>, String> {
        let Some(postgres) = &self.postgres else {
            return Ok(None);
        };
        postgres.check_and_record(request).await.map(Some)
    }

    pub(crate) async fn record_allowed_decision(
        &self,
        decision: &QuotaDecision,
    ) -> Result<(), String> {
        let deltas = usage_deltas(decision);
        if deltas.is_empty() {
            return Ok(());
        }

        let mut errors = Vec::new();
        if let Some(postgres) = &self.postgres {
            if let Err(error) = postgres.record_deltas(&deltas).await {
                errors.push(error);
            }
        }
        if let Some(valkey) = &self.valkey {
            if let Err(error) = valkey.record_deltas(&deltas).await {
                errors.push(error);
            }
        }
        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors.join("; "))
        }
    }

    pub(crate) async fn record_valkey_allowed_decision(
        &self,
        decision: &QuotaDecision,
    ) -> Result<(), String> {
        let Some(valkey) = &self.valkey else {
            return Ok(());
        };
        let deltas = usage_deltas(decision);
        if deltas.is_empty() {
            return Ok(());
        }
        valkey.record_deltas(&deltas).await
    }
}

impl PostgresQuotaStore {
    async fn connect(dsn: &str) -> Result<Self, String> {
        let (client, connection) = tokio_postgres::connect(dsn, NoTls)
            .await
            .map_err(|error| format!("connect quota Postgres ledger: {error:?}"))?;
        tokio::spawn(async move {
            if let Err(error) = connection.await {
                tracing::error!("quota Postgres connection failed: {error}");
            }
        });
        let store = Self {
            client: Arc::new(Mutex::new(client)),
        };
        store.initialize().await?;
        Ok(store)
    }

    async fn initialize(&self) -> Result<(), String> {
        self.client
            .lock()
            .await
            .batch_execute(
                "
                CREATE TABLE IF NOT EXISTS tryops_quota_usage (
                    period TEXT NOT NULL,
                    user_hash TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    workload TEXT NOT NULL,
                    used BIGINT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (period, user_hash, dimension)
                );
                ",
            )
            .await
            .map_err(|error| format!("initialize quota Postgres ledger: {error:?}"))
    }

    async fn record_deltas(&self, deltas: &[QuotaUsageDelta]) -> Result<(), String> {
        let client = self.client.lock().await;
        for delta in deltas {
            let increment = i64::try_from(delta.increment)
                .map_err(|_| format!("quota increment overflows i64: {}", delta.increment))?;
            client
                .execute(
                    "
                    INSERT INTO tryops_quota_usage
                        (period, user_hash, dimension, plan, workload, used, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (period, user_hash, dimension)
                    DO UPDATE SET
                        plan = EXCLUDED.plan,
                        workload = EXCLUDED.workload,
                        used = tryops_quota_usage.used + EXCLUDED.used,
                        updated_at = NOW();
                    ",
                    &[
                        &delta.period,
                        &delta.user_hash,
                        &delta.dimension,
                        &delta.plan,
                        &delta.workload,
                        &increment,
                    ],
                )
                .await
                .map_err(|error| {
                    format!(
                        "upsert quota usage {}:{}:{}: {error:?}",
                        delta.period, delta.user_hash, delta.dimension
                    )
                })?;
        }
        Ok(())
    }

    async fn check_and_record(&self, request: QuotaCheckRequest) -> Result<QuotaDecision, String> {
        let mut dimensions = usage_dimensions(&request)?
            .into_iter()
            .map(|(dimension, increment)| {
                let limit = dimension_limit(&request.plan, dimension)
                    .ok_or_else(|| format!("unsupported quota dimension '{dimension}'"))?;
                Ok((dimension, increment, limit))
            })
            .collect::<Result<Vec<_>, String>>()?;
        dimensions.sort_by(|left, right| left.0.cmp(right.0));

        let period = request.period.clone().unwrap_or_else(current_period_key);
        let user_hash = user_hash(&request.user_id);
        let mut client = self.client.lock().await;
        let transaction = client
            .transaction()
            .await
            .map_err(|error| format!("start quota Postgres admission transaction: {error:?}"))?;

        let mut checks = Vec::with_capacity(dimensions.len());
        for (dimension, increment, limit) in dimensions {
            let increment_i64 = i64::try_from(increment)
                .map_err(|_| format!("quota increment overflows i64: {increment}"))?;
            let limit_i64 =
                i64::try_from(limit).map_err(|_| format!("quota limit overflows i64: {limit}"))?;
            transaction
                .execute(
                    "
                    INSERT INTO tryops_quota_usage
                        (period, user_hash, dimension, plan, workload, used, updated_at)
                    VALUES ($1, $2, $3, $4, $5, 0, NOW())
                    ON CONFLICT (period, user_hash, dimension) DO NOTHING;
                    ",
                    &[
                        &period,
                        &user_hash,
                        &dimension,
                        &request.plan,
                        &request.workload,
                    ],
                )
                .await
                .map_err(|error| {
                    format!(
                        "initialize quota admission row {period}:{user_hash}:{dimension}: {error:?}"
                    )
                })?;
            let row = transaction
                .query_one(
                    "
                    SELECT used
                    FROM tryops_quota_usage
                    WHERE period = $1 AND user_hash = $2 AND dimension = $3
                    FOR UPDATE;
                    ",
                    &[&period, &user_hash, &dimension],
                )
                .await
                .map_err(|error| {
                    format!("lock quota admission row {period}:{user_hash}:{dimension}: {error:?}")
                })?;
            let used_i64: i64 = row.get(0);
            if used_i64 < 0 {
                return Err(format!(
                    "quota admission row {period}:{user_hash}:{dimension} has negative usage {used_i64}"
                ));
            }
            let used = u64::try_from(used_i64)
                .map_err(|_| format!("quota usage overflows u64: {used_i64}"))?;
            let remaining_before = limit.saturating_sub(used);
            let allowed = used_i64.saturating_add(increment_i64) <= limit_i64;
            checks.push(QuotaDimensionCheck {
                dimension: dimension.to_string(),
                limit,
                used,
                increment,
                remaining_before,
                allowed,
                used_after: used,
                remaining_after: remaining_before,
            });
        }

        let allowed = checks.iter().all(|check| check.allowed);
        if allowed {
            for check in &mut checks {
                if check.increment == 0 {
                    continue;
                }
                let increment = i64::try_from(check.increment)
                    .map_err(|_| format!("quota increment overflows i64: {}", check.increment))?;
                let row = transaction
                    .query_one(
                        "
                        UPDATE tryops_quota_usage
                        SET
                            plan = $4,
                            workload = $5,
                            used = used + $6,
                            updated_at = NOW()
                        WHERE period = $1 AND user_hash = $2 AND dimension = $3
                        RETURNING used;
                        ",
                        &[
                            &period,
                            &user_hash,
                            &check.dimension,
                            &request.plan,
                            &request.workload,
                            &increment,
                        ],
                    )
                    .await
                    .map_err(|error| {
                        format!(
                            "update quota admission row {}:{}:{}: {error:?}",
                            period, user_hash, check.dimension
                        )
                    })?;
                let used_after_i64: i64 = row.get(0);
                if used_after_i64 < 0 {
                    return Err(format!(
                        "quota admission row {}:{}:{} returned negative usage {}",
                        period, user_hash, check.dimension, used_after_i64
                    ));
                }
                let used_after = u64::try_from(used_after_i64)
                    .map_err(|_| format!("quota usage overflows u64: {used_after_i64}"))?;
                check.used_after = used_after;
                check.remaining_after = check.limit.saturating_sub(used_after);
            }
            transaction.commit().await.map_err(|error| {
                format!("commit quota Postgres admission transaction: {error:?}")
            })?;
        } else {
            transaction.rollback().await.map_err(|error| {
                format!("rollback quota Postgres admission transaction: {error:?}")
            })?;
        }

        Ok(QuotaDecision::new(
            allowed,
            period,
            user_hash,
            request.plan,
            request.workload,
            checks,
        ))
    }
}

impl ValkeyQuotaStore {
    fn from_address(address: String) -> Self {
        Self {
            address,
            prefix: optional_env(VALKEY_PREFIX_ENV).unwrap_or_else(|| "tryops".to_string()),
            ttl_seconds: env::var(VALKEY_TTL_ENV)
                .ok()
                .and_then(|value| value.parse::<u64>().ok())
                .unwrap_or(DEFAULT_VALKEY_TTL_SECONDS),
        }
    }

    async fn record_deltas(&self, deltas: &[QuotaUsageDelta]) -> Result<(), String> {
        let mut stream = TcpStream::connect(&self.address)
            .await
            .map_err(|error| format!("connect quota Valkey ledger {}: {error}", self.address))?;
        for delta in deltas {
            let key = valkey_key(&self.prefix, delta);
            send_valkey_command(
                &mut stream,
                &[
                    "INCRBY".to_string(),
                    key.clone(),
                    delta.increment.to_string(),
                ],
            )
            .await?;
            send_valkey_command(
                &mut stream,
                &["EXPIRE".to_string(), key, self.ttl_seconds.to_string()],
            )
            .await?;
        }
        Ok(())
    }
}

fn usage_deltas(decision: &QuotaDecision) -> Vec<QuotaUsageDelta> {
    if !decision.allowed {
        return Vec::new();
    }
    decision
        .checks
        .iter()
        .filter(|check| check.increment > 0)
        .map(|check| QuotaUsageDelta {
            period: decision.period.clone(),
            user_hash: decision.user_hash.clone(),
            plan: decision.plan.clone(),
            workload: decision.workload.clone(),
            dimension: check.dimension.clone(),
            increment: check.increment,
        })
        .collect()
}

fn valkey_key(prefix: &str, delta: &QuotaUsageDelta) -> String {
    format!(
        "{prefix}:quota:{}:{}:{}",
        delta.period, delta.user_hash, delta.dimension
    )
}

fn valkey_command(parts: &[String]) -> Vec<u8> {
    let mut body = format!("*{}\r\n", parts.len()).into_bytes();
    for part in parts {
        body.extend_from_slice(format!("${}\r\n", part.len()).as_bytes());
        body.extend_from_slice(part.as_bytes());
        body.extend_from_slice(b"\r\n");
    }
    body
}

async fn send_valkey_command(stream: &mut TcpStream, parts: &[String]) -> Result<(), String> {
    stream
        .write_all(&valkey_command(parts))
        .await
        .map_err(|error| format!("write Valkey command {}: {error}", parts[0]))?;
    read_valkey_reply(stream)
        .await
        .map_err(|error| format!("read Valkey reply {}: {error}", parts[0]))
}

async fn read_valkey_reply(stream: &mut TcpStream) -> Result<(), String> {
    let mut prefix = [0_u8; 1];
    stream
        .read_exact(&mut prefix)
        .await
        .map_err(|error| error.to_string())?;
    match prefix[0] {
        b'+' | b':' => {
            let _ = read_valkey_line(stream).await?;
            Ok(())
        }
        b'-' => {
            let line = read_valkey_line(stream).await?;
            Err(String::from_utf8_lossy(&line).to_string())
        }
        b'$' => {
            let line = read_valkey_line(stream).await?;
            let length = String::from_utf8_lossy(&line)
                .parse::<usize>()
                .map_err(|error| error.to_string())?;
            let mut bytes = vec![0_u8; length + 2];
            stream
                .read_exact(&mut bytes)
                .await
                .map_err(|error| error.to_string())?;
            Ok(())
        }
        value => Err(format!("unsupported Valkey reply prefix {}", value as char)),
    }
}

async fn read_valkey_line(stream: &mut TcpStream) -> Result<Vec<u8>, String> {
    let mut line = Vec::new();
    loop {
        let mut byte = [0_u8; 1];
        stream
            .read_exact(&mut byte)
            .await
            .map_err(|error| error.to_string())?;
        line.push(byte[0]);
        if line.ends_with(b"\r\n") {
            line.truncate(line.len().saturating_sub(2));
            return Ok(line);
        }
    }
}

fn optional_env(name: &str) -> Option<String> {
    env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn postgres_dsn_from_env() -> Result<Option<String>, String> {
    if let Some(dsn) = optional_env(POSTGRES_DSN_ENV) {
        return Ok(Some(dsn));
    }
    let Some(path) = optional_env(POSTGRES_DSN_FILE_ENV) else {
        return Ok(None);
    };
    read_secret_file(&path, POSTGRES_DSN_FILE_ENV).map(Some)
}

fn read_secret_file(path: &str, env_name: &str) -> Result<String, String> {
    let value = fs::read_to_string(path)
        .map_err(|error| format!("read {env_name} secret file '{path}': {error}"))?
        .trim()
        .to_string();
    if value.is_empty() {
        return Err(format!("{env_name} secret file '{path}' is empty"));
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use crate::quota::{QuotaCheckRequest, QuotaLedger};

    use super::*;

    fn sample_decision() -> QuotaDecision {
        let mut ledger = QuotaLedger::default();
        let request = serde_json::from_str::<QuotaCheckRequest>(
            r#"{
                "user_id": "enterprise-user",
                "plan": "free",
                "workload": "llm",
                "request_units": 1,
                "estimated_tokens": 300,
                "period": "2026-06-11"
            }"#,
        )
        .unwrap();
        ledger.check_and_record(request).unwrap()
    }

    #[test]
    fn decision_turns_into_durable_usage_deltas() {
        let deltas = usage_deltas(&sample_decision());

        assert_eq!(deltas.len(), 2);
        assert_eq!(deltas[0].period, "2026-06-11");
        assert_eq!(deltas[0].user_hash, "9cd0ffa8da8b17c4");
        assert_eq!(deltas[0].plan, "free");
        assert_eq!(deltas[0].workload, "llm");
        assert!(deltas
            .iter()
            .any(|delta| delta.dimension == "llm_requests_per_day"));
        assert!(deltas
            .iter()
            .any(|delta| delta.dimension == "llm_tokens_per_day"));
    }

    #[test]
    fn valkey_command_uses_resp_wire_format() {
        let command = valkey_command(&[
            "INCRBY".to_string(),
            "tryops:quota:2026-06-11:abc:llm_tokens_per_day".to_string(),
            "300".to_string(),
        ]);

        assert_eq!(
            String::from_utf8(command).unwrap(),
            "*3\r\n$6\r\nINCRBY\r\n$46\r\ntryops:quota:2026-06-11:abc:llm_tokens_per_day\r\n$3\r\n300\r\n",
        );
    }

    #[test]
    fn valkey_key_is_stable_and_scoped() {
        let delta = usage_deltas(&sample_decision())
            .into_iter()
            .find(|delta| delta.dimension == "llm_tokens_per_day")
            .unwrap();

        assert_eq!(
            valkey_key("tryops-prod", &delta),
            "tryops-prod:quota:2026-06-11:9cd0ffa8da8b17c4:llm_tokens_per_day"
        );
    }

    #[test]
    fn reads_postgres_dsn_secret_file() {
        let path =
            std::env::temp_dir().join(format!("tryops-gateway-dsn-{}.txt", std::process::id()));
        std::fs::write(
            &path,
            "host=postgres port=5432 user=tryops password=secret dbname=tryops\n",
        )
        .unwrap();

        let dsn = read_secret_file(path.to_str().unwrap(), POSTGRES_DSN_FILE_ENV).unwrap();
        let _ = std::fs::remove_file(path);

        assert_eq!(
            dsn,
            "host=postgres port=5432 user=tryops password=secret dbname=tryops"
        );
    }
}
