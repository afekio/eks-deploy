# main-app — Automated Deployment with Ansible

One command provisions **all** of AWS infrastructure and deploys the full
micro-service application on top of it. Ansible orchestrates the correct order:

```
preflight ─▶ terraform ─▶ kubeconfig ─▶ platform operators ─▶ application (Helm)
```

Everything is driven by a **single centralized variables file**
([`group_vars/all/main.yml`](group_vars/all/main.yml)) that feeds *both* the
Terraform layer and the Helm layer, plus an **encrypted vault**
([`group_vars/all/vault.yml`](group_vars/all/vault.yml)) for every password.

---

## Directory layout

```
ansible/
├── ansible.cfg                     # points at inventory + vault password file
├── inventory/hosts.ini             # runs against localhost (local connection)
├── group_vars/all/
│   ├── main.yml                    # ⭐ ONE centralized vars file (TF + Helm + images)
│   └── vault.yml                   # 🔒 ansible-vault encrypted secrets
├── vault-plaintext.example.yml     # pre-encryption copy of the secrets (git-ignored)
├── site.yml                        # master entrypoint  -> imports deploy.yml
├── deploy.yml                      # full ordered deployment
├── destroy.yml                     # full teardown (needs -e confirm=yes)
├── roles/
│   ├── preflight/                  # verify terraform/helm/kubectl/aws + AWS creds
│   ├── terraform/                  # render tfvars from central vars, apply, read outputs
│   ├── kubeconfig/                 # aws eks update-kubeconfig + wait for API
│   ├── platform/                   # install CloudNativePG + ingress-nginx
│   └── app/                        # render Helm overrides (TF outputs + vault) + helm upgrade
└── README.md
```

## What gets deployed

| Layer         | Component                                                             |
|---------------|----------------------------------------------------------------------|
| Terraform     | VPC, EKS (ARM nodes), S3, SNS (+email subscriptions), EFS, IRSA       |
| Platform      | CloudNativePG operator, ingress-nginx controller                     |
| Application   | frontend, backend, auth micro-services + CloudNativePG database + ingress |

---

## Prerequisites

Installed and on `PATH` (already verified by the `preflight` role):
`terraform`, `helm`, `kubectl`, `aws`, `ansible`.

AWS credentials configured (`aws configure` / env vars / SSO) with permission to
create the resources above.

---

## One-time setup

### 1. Create the vault password file

The vault password is read from `.vault_pass.txt` (git-ignored, referenced in
[`ansible.cfg`](ansible.cfg)). Create it once:

```bash
cd deploy-eks-project/ansible
echo 'your-strong-vault-password' > .vault_pass.txt
chmod 600 .vault_pass.txt
```

### 2. Set your secrets, then (re)encrypt the vault

The secrets live in two forms:

* `vault-plaintext.example.yml` — the **pre-encryption** human-readable copy.
* `group_vars/all/vault.yml` — the **encrypted** file the playbooks actually use.

Edit values and re-encrypt whenever you change a secret:

```bash
# Option A — edit the plaintext reference, then encrypt it into the vault:
vim vault-plaintext.example.yml
ansible-vault encrypt vault-plaintext.example.yml --output group_vars/all/vault.yml

# Option B — edit the encrypted vault in place:
ansible-vault edit group_vars/all/vault.yml

# View the decrypted contents:
ansible-vault view group_vars/all/vault.yml
```

Secrets stored in the vault:

| Key                     | Purpose                                                        |
|-------------------------|----------------------------------------------------------------|
| `vault_db_password`     | PostgreSQL password (app user **and** superuser)               |
| `vault_app_secret_key`  | Flask `SECRET_KEY` / JWT signing key (shared by auth + backend)|

### 3. Review the centralized variables

Open [`group_vars/all/main.yml`](group_vars/all/main.yml) and adjust as needed:
region, cluster name, node sizes, image tags, and the **SNS email list**
(`sns_subscription_emails` — add as many addresses as you want).

---

## Full deployment

```bash
cd deploy-eks-project/ansible
ansible-playbook site.yml
```

That's it. This runs, in order: preflight → terraform apply → kubeconfig →
platform operators → application. At the end it prints the ingress entrypoint
hostname.

> Each SNS email address receives a confirmation link that must be accepted
> before alerts are delivered.

### Useful variations

```bash
# Only (re)deploy the application (skip infra + operators):
ansible-playbook site.yml --tags app

# Infra only (terraform + kubeconfig):
ansible-playbook site.yml --tags infra

# Skip the platform operators (already installed):
ansible-playbook site.yml -e install_platform=false

# Provide the vault password interactively instead of the file:
ansible-playbook site.yml --ask-vault-pass

# Dry run to preview which stages would execute:
ansible-playbook site.yml --list-tasks
```

---

## Teardown

Destroys the Kubernetes workloads/operators **and** the AWS infrastructure.
Requires an explicit confirmation flag:

```bash
ansible-playbook destroy.yml -e confirm=yes
```

---

## How the single source of truth works

* `group_vars/all/main.yml` is rendered by the **terraform** role into
  `../terrform-deploy/ansible.auto.tfvars.json`, which Terraform picks up
  automatically — so the cluster, region, node sizes and SNS emails all come
  from the same file.
* The same variables plus the live **Terraform outputs** (IRSA role ARN, S3
  bucket, SNS topic, EFS id) and the **vault** secrets are rendered by the
  **app** role into a temporary Helm override file (written `0600`, deleted
  immediately after `helm upgrade`) — so no secret is ever left on disk.

Nothing is hand-patched: change a value in one place and re-run.

---

## Security notes

* `.vault_pass.txt` and `vault-plaintext.example.yml` are git-ignored — never
  commit them.
* Rotate `vault_db_password` and `vault_app_secret_key` before any real use.
* The rendered Helm override (with secrets) is created as a `0600` temp file and
  removed on every run.
