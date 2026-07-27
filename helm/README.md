# main-app — Helm deployment

Helm-based deployment of the full **main-app** stack on EKS. Replaces the old
raw-manifest / Kustomize setup in `../kube-deploy`. One command deploys
everything; each microservice is its own subchart with its own `values.yaml`.

## Structure

```
helm/
├── deploy.sh                     # one-command deploy (platform + app)
├── sync-values-from-tf.sh        # writes values-from-tf.yaml from Terraform outputs
├── platform/                     # cluster prerequisites (installed as separate Helm releases)
│   ├── cnpg-operator-values.yaml     # CloudNativePG operator
│   └── ingress-nginx-values.yaml     # NGINX ingress controller (NLB)
└── main-app/                     # umbrella chart
    ├── Chart.yaml                # declares the 6 subcharts as dependencies
    ├── values.yaml               # global values + component toggles
    ├── templates/
    │   └── namespace.yaml
    └── charts/                   # one subchart per concern
        ├── common/               # ServiceAccount (IRSA), ConfigMap, app Secret
        ├── database/             # CloudNativePG Cluster + secrets + EFS StorageClass
        ├── auth/                 # auth DaemonSet + Service (waits for Postgres)
        ├── backend/              # backend DaemonSet + Service
        ├── frontend/             # frontend Deployment + Service
        └── ingress/              # health / auth-rewrite / main Ingress objects
```

## Prerequisites

- An EKS cluster reachable via `kubectl` (created by the Terraform stack in
  `../terrform-deploy`). This chart does **not** manage Terraform/infrastructure.
- `helm` and `kubectl` in `PATH`. `terraform` + `aws` only needed for the
  optional Terraform value sync.
- EFS CSI driver installed on the cluster (for the CNPG storage class).

## Deploy (one command)

```bash
cd deploy-eks-project/helm
./deploy.sh
```

This will:
1. Read Terraform outputs → `values-from-tf.yaml` (IRSA role, S3/SNS/SQS, EFS id).
2. Install the CloudNativePG operator and NGINX ingress controller.
3. Install the `main-app` umbrella chart into the `main-app` namespace.

Options:

```bash
./deploy.sh --no-tf-sync   # use committed values only, skip Terraform lookup
./deploy.sh --app-only     # skip operators, deploy just the app chart
```

Manual equivalent:

```bash
helm upgrade --install main-app ./main-app \
  --namespace main-app --create-namespace \
  -f ./main-app/values.yaml -f ./values-from-tf.yaml
```

## Configuration

Global, shared values live under `global:` in `main-app/values.yaml` (namespace,
image registry/repository, IRSA role, DB connection, AWS resources). They are
injected into every subchart automatically.

Each subchart exposes its own knobs in its `values.yaml`, e.g.:

| Subchart   | Key knobs                                                             |
|------------|----------------------------------------------------------------------|
| `frontend` | `replicaCount`, `image.tag`, `resources`, `service.port`, probes     |
| `backend`  | `image.tag`, `resources`, `service.port`, probes                     |
| `auth`     | `image.tag`, `waitForPostgres.*`, `resources`, probes                |
| `database` | `cluster.instances`, `cluster.storageSize`, `storageClass.*`, creds  |
| `ingress`  | `host`, per-route paths/rewrites, `services.*`                       |
| `common`   | `secret.secretKey`, ConfigMap URLs                                    |

Override at deploy time, e.g. bump frontend replicas and image tag:

```bash
helm upgrade --install main-app ./main-app -f ./main-app/values.yaml \
  --set frontend.replicaCount=4 --set frontend.image.tag=frontend0.4
```

Disable a component:

```bash
--set ingress.enabled=false
```

## Notes

- `auth` and `backend` run as **DaemonSets**; `frontend` runs as a **Deployment**
  (2 replicas) — matching the previous working deployment.
- The `app-postgres-app` secret (with the ready-to-use `uri`) is created by the
  CloudNativePG operator during bootstrap, so it is intentionally **not**
  templated here. `auth`/`backend` read `DATABASE_URL` from it.
- Secrets in values are placeholders for a homelab/demo. For production, source
  them from an external secret manager (e.g. External Secrets Operator) instead
  of committing them.
