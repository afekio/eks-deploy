variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as a naming prefix"
  type        = string
  default     = "main-app"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "sns_subscription_emails" {
  description = "Email addresses to subscribe to the SNS topic (each must confirm via email). Add as many as you like."
  type        = list(string)
  default     = []
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.60.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.60.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for the private subnet"
  type        = string
  default     = "10.60.2.0/24"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "main-app-eks-arm"
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.30"
}

variable "node_instance_type" {
  description = "ARM instance type for worker nodes"
  type        = string
  default     = "t4g.small"
}

variable "node_desired_size" {
  description = "Desired number of nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of nodes"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of nodes"
  type        = number
  default     = 2
}

variable "service_account_namespace" {
  description = "Kubernetes namespace for IRSA service account"
  type        = string
  default     = "default"
}

variable "service_account_name" {
  description = "Kubernetes service account name for IRSA"
  type        = string
  default     = "app-irsa-sa"
}

variable "efs_csi_service_account_namespace" {
  description = "Namespace for EFS CSI controller service account"
  type        = string
  default     = "kube-system"
}

variable "efs_csi_service_account_name" {
  description = "Service account name for EFS CSI controller"
  type        = string
  default     = "efs-csi-controller-sa"
}

variable "enable_efs_csi_addon" {
  description = "Install AWS EFS CSI driver as an EKS addon"
  type        = bool
  default     = true
}
