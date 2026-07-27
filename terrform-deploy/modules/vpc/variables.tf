variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name for subnet tags"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "public_subnet_cidr" {
  description = "Public subnet CIDR block"
  type        = string
}

variable "private_subnet_cidr" {
  description = "Private subnet CIDR block"
  type        = string
}

variable "public_subnet_az" {
  description = "Availability Zone for public subnet"
  type        = string
}

variable "private_subnet_az" {
  description = "Availability Zone for private subnet"
  type        = string
}