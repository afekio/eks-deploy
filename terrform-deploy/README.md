# terrform-deploy

Production-style Terraform layout for deploying EKS with ARM worker nodes, IRSA permissions, VPC networking, S3, and SNS.

## What this deploys

- VPC with:
  - 1 public subnet
  - 1 private subnet
  - Internet Gateway
  - Public route table with `0.0.0.0/0` to IGW
  - No NAT Gateway
- EKS cluster
- Managed ARM node group with 2 nodes (`t4g.small` by default)
- S3 bucket for application data
- SNS topic for app notifications
- IRSA role for one Kubernetes service account with:
  - S3 read/write permissions
  - SNS publish permissions

## Structure

- `main.tf`: wires all modules
- `variables.tf`: root variables
- `outputs.tf`: root outputs
- `modules/vpc`: VPC, subnets, IGW, route tables
- `modules/eks`: EKS cluster and ARM node group
- `modules/irsa`: OIDC provider and IAM role/policy for service account
- `modules/s3`: S3 bucket
- `modules/sns`: SNS topic

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Configure kubectl after apply

```bash
aws eks update-kubeconfig --region <aws_region> --name <eks_cluster_name>
```

## Annotate service account for IRSA

Use the output `service_account_annotation` to annotate your Kubernetes service account.

Example:

```bash
kubectl annotate serviceaccount app-irsa-sa -n default eks.amazonaws.com/role-arn=<irsa_role_arn>
```

## Note about no NAT

With no NAT Gateway, worker nodes are placed in the public subnet so they can reach required AWS endpoints over the Internet Gateway.
