variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the cluster"
  type        = string
}

variable "cluster_subnet_ids" {
  description = "Subnet IDs used by the control plane"
  type        = list(string)
}

variable "node_subnet_ids" {
  description = "Subnet IDs used by worker nodes"
  type        = list(string)
}

variable "node_instance_type" {
  description = "EC2 instance type for ARM nodes"
  type        = string
}

variable "node_desired_size" {
  description = "Desired number of nodes"
  type        = number
}

variable "node_min_size" {
  description = "Minimum number of nodes"
  type        = number
}

variable "node_max_size" {
  description = "Maximum number of nodes"
  type        = number
}