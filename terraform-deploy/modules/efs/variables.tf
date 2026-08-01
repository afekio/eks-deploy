variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for EFS security group"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR allowed to mount EFS"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs where EFS mount targets are created"
  type        = list(string)
}