from __future__ import annotations

from typing import Any


GITOPS_MANIFEST_SCHEMA = "tryops.gitops_manifests.v1"
DEFAULT_GITOPS_REPO_URL = "https://github.com/tryops/tryops-gitops"


def build_gitops_manifests(
    *,
    deployment_manifest: dict[str, Any],
    repo_url: str = DEFAULT_GITOPS_REPO_URL,
    target_revision: str = "HEAD",
) -> dict[str, Any]:
    """Build Argo CD and Argo Rollouts manifests for a deployment package."""

    candidate_id = str(deployment_manifest["candidate_id"])
    profile = str(deployment_manifest["profile"])
    workload = str(deployment_manifest["model"]["workload"])
    app_name = _dns_name(f"tryops-{workload}-{profile}")
    namespace = "tryops-prod" if profile == "production-demo" else "tryops-staging"
    image = _container_image(deployment_manifest)
    canary_percent = _canary_percent(profile)
    path = f"clusters/{profile}/{candidate_id}"

    files = {
        "application.yaml": _application_yaml(
            app_name=app_name,
            namespace=namespace,
            repo_url=repo_url,
            target_revision=target_revision,
            path=path,
            candidate_id=candidate_id,
        ),
        "rollout.yaml": _rollout_yaml(
            app_name=app_name,
            namespace=namespace,
            image=image,
            candidate_id=candidate_id,
            package_id=str(deployment_manifest["package_id"]),
            model_alias=str(deployment_manifest["model"]["alias"]),
            model_version=str(deployment_manifest["model"]["version"]),
            canary_percent=canary_percent,
        ),
        "services.yaml": _services_yaml(app_name=app_name, namespace=namespace, candidate_id=candidate_id),
        "kustomization.yaml": _kustomization_yaml(),
    }
    return {
        "schema_version": GITOPS_MANIFEST_SCHEMA,
        "profile": profile,
        "candidate_id": candidate_id,
        "application": app_name,
        "namespace": namespace,
        "repo_url": repo_url,
        "target_revision": target_revision,
        "path": path,
        "rollout": {
            "strategy": "canary",
            "canary_percent": canary_percent,
            "stable_service": f"{app_name}-stable",
            "canary_service": f"{app_name}-canary",
        },
        "files": files,
    }


def _application_yaml(
    *,
    app_name: str,
    namespace: str,
    repo_url: str,
    target_revision: str,
    path: str,
    candidate_id: str,
) -> str:
    return "\n".join(
        [
            "apiVersion: argoproj.io/v1alpha1",
            "kind: Application",
            "metadata:",
            f"  name: {app_name}",
            "  namespace: argocd",
            "  labels:",
            "    app.kubernetes.io/part-of: tryops",
            f"    tryops.io/candidate-id: {candidate_id}",
            "spec:",
            "  project: default",
            "  source:",
            f"    repoURL: {repo_url}",
            f"    targetRevision: {target_revision}",
            f"    path: {path}",
            "  destination:",
            "    server: https://kubernetes.default.svc",
            f"    namespace: {namespace}",
            "  syncPolicy:",
            "    automated:",
            "      prune: false",
            "      selfHeal: true",
            "    syncOptions:",
            "      - CreateNamespace=true",
            "",
        ]
    )


def _rollout_yaml(
    *,
    app_name: str,
    namespace: str,
    image: str,
    candidate_id: str,
    package_id: str,
    model_alias: str,
    model_version: str,
    canary_percent: int,
) -> str:
    first_weight = max(1, min(canary_percent, 50))
    return "\n".join(
        [
            "apiVersion: argoproj.io/v1alpha1",
            "kind: Rollout",
            "metadata:",
            f"  name: {app_name}",
            f"  namespace: {namespace}",
            "  labels:",
            "    app.kubernetes.io/part-of: tryops",
            f"    tryops.io/candidate-id: {candidate_id}",
            "  annotations:",
            f"    tryops.io/package-id: {package_id}",
            "spec:",
            "  replicas: 2",
            "  revisionHistoryLimit: 3",
            "  selector:",
            "    matchLabels:",
            f"      app.kubernetes.io/name: {app_name}",
            "  template:",
            "    metadata:",
            "      labels:",
            f"        app.kubernetes.io/name: {app_name}",
            f"        tryops.io/candidate-id: {candidate_id}",
            "    spec:",
            "      containers:",
            "        - name: tryops-api",
            f"          image: {image}",
            "          imagePullPolicy: IfNotPresent",
            "          ports:",
            "            - containerPort: 8000",
            "          env:",
            "            - name: TRYOPS_MODEL_ALIAS",
            f"              value: {model_alias}",
            "            - name: TRYOPS_MODEL_VERSION",
            f"              value: {model_version}",
            "            - name: TRYOPS_CANDIDATE_ID",
            f"              value: {candidate_id}",
            "  strategy:",
            "    canary:",
            f"      stableService: {app_name}-stable",
            f"      canaryService: {app_name}-canary",
            "      maxSurge: 25%",
            "      maxUnavailable: 0",
            "      steps:",
            f"        - setWeight: {first_weight}",
            "        - pause:",
            "            duration: 10m",
            "        - setWeight: 50",
            "        - pause:",
            "            duration: 10m",
            "        - setWeight: 100",
            "",
        ]
    )


def _services_yaml(*, app_name: str, namespace: str, candidate_id: str) -> str:
    service = [
        "apiVersion: v1",
        "kind: Service",
        "metadata:",
        "  name: {name}",
        f"  namespace: {namespace}",
        "  labels:",
        "    app.kubernetes.io/part-of: tryops",
        f"    tryops.io/candidate-id: {candidate_id}",
        "spec:",
        "  ports:",
        "    - name: http",
        "      port: 80",
        "      targetPort: 8000",
        "  selector:",
        f"    app.kubernetes.io/name: {app_name}",
        "",
    ]
    stable = "\n".join(line.format(name=f"{app_name}-stable") for line in service)
    canary = "\n".join(line.format(name=f"{app_name}-canary") for line in service)
    return f"{stable}---\n{canary}"


def _kustomization_yaml() -> str:
    return "\n".join(
        [
            "apiVersion: kustomize.config.k8s.io/v1beta1",
            "kind: Kustomization",
            "resources:",
            "  - application.yaml",
            "  - rollout.yaml",
            "  - services.yaml",
            "",
        ]
    )


def _container_image(deployment_manifest: dict[str, Any]) -> str:
    adapter = _dns_name(str(deployment_manifest["routing"]["adapter"]))
    version = str(deployment_manifest["model"]["version"]).replace("+", "-")
    return f"ghcr.io/tryops/{adapter}:{version}"


def _canary_percent(profile: str) -> int:
    return 10 if profile == "production-demo" else 1


def _dns_name(value: str) -> str:
    normalized = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            normalized.append(char)
            previous_dash = False
        elif not previous_dash:
            normalized.append("-")
            previous_dash = True
    return "".join(normalized).strip("-") or "tryops"
