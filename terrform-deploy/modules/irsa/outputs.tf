output "irsa_role_arn" {
  description = "IAM role ARN for Kubernetes service account"
  value       = aws_iam_role.this.arn
}

output "service_account_annotation" {
  description = "Service account annotation map for IRSA"
  value = {
    "eks.amazonaws.com/role-arn" = aws_iam_role.this.arn
  }
}

output "efs_csi_irsa_role_arn" {
  description = "IAM role ARN for EFS CSI controller"
  value       = aws_iam_role.efs_csi.arn
}