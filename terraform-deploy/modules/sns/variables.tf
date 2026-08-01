variable "project_name" {
  description = "Project name prefix"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "subscription_emails" {
  description = "List of email addresses to subscribe to the SNS topic"
  type        = list(string)
  default     = []
}