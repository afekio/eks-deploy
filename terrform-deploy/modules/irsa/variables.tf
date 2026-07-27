variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL from EKS cluster"
  type        = string
}

variable "service_account_namespace" {
  description = "Kubernetes namespace"
  type        = string
}

variable "service_account_name" {
  description = "Kubernetes service account name"
  type        = string
}

variable "efs_csi_service_account_namespace" {
  description = "Namespace for EFS CSI controller service account"
  type        = string
}

variable "efs_csi_service_account_name" {
  description = "Service account name for EFS CSI controller"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN"
  type        = string
}

variable "sns_topic_arn" {
  description = "SNS topic ARN"
  type        = string
}