# Orchestration Skeleton

Date: 2026-06-11

TryOps now has a local orchestration skeleton for the enterprise promotion workflow. The target
orchestrator is Kubeflow Pipelines, while the current implementation remains dependency-free so it
can run in CI and local smoke checks before Kubernetes is available.

## Evidence Command

Run:

```bash
make orchestration-sample
```

Artifacts:

```text
artifacts/eval/orchestration/tryops_pipeline_dag.json
artifacts/eval/orchestration/tryops_pipeline.kfp.yaml
artifacts/eval/orchestration/orchestration_report.json
```

## DAG Shape

The skeleton models the product promotion path as seven ordered steps:

1. Validate the dataset manifest.
2. Evaluate the VTON baseline.
3. Benchmark the LLM baseline.
4. Generate supply-chain evidence.
5. Generate governance risk mapping.
6. Evaluate promotion policy.
7. Package deployment release artifacts.

Promotion depends on VTON evaluation, LLM benchmark, supply-chain evidence, and governance mapping.
Deployment packaging depends on a passed promotion step.

## Validation

`src/tryops/orchestration.py` validates:

- duplicate step IDs
- missing dependencies
- dependency cycles
- commandless steps
- terminal deployment step
- deterministic topological order

The generated report uses schema `tryops.orchestration_report.v1` and records the Kubeflow research
sources that guided the skeleton.

## Kubeflow Path

The repository emits a Kubeflow-style manifest at:

```text
artifacts/eval/orchestration/tryops_pipeline.kfp.yaml
```

`pipelines/kubeflow/tryops_pipeline.py` is the bridge file for a future Kubeflow SDK implementation.
The next production step is to replace command strings with containerized Kubeflow components and
compile/upload the pipeline into a live Kubeflow Pipelines backend.

Relevant open-source references:

- Kubeflow Pipelines overview: https://www.kubeflow.org/docs/components/pipelines/overview/
- Compile a pipeline: https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/compile-a-pipeline/
- Components: https://www.kubeflow.org/docs/components/pipelines/user-guides/components/

## Residual Risk

This closes the orchestration-framework skeleton requirement. It is not a live KFP deployment yet:
there is no Kubernetes cluster, KFP API upload, container image build, or artifact lineage store wired
to the orchestrator in this local workspace.
