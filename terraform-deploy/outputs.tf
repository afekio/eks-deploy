output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "aws_region" {
  description = "AWS region used by this Terraform stack"
  value       = var.aws_region
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for cluster"
  value       = module.eks.cluster_oidc_issuer_url
}

output "s3_bucket_name" {
  description = "S3 bucket name for application"
  value       = module.s3.bucket_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for application notifications"
  value       = module.sns.topic_arn
}

output "irsa_role_arn" {
  description = "IAM role ARN to annotate on Kubernetes service account"
  value       = module.irsa.irsa_role_arn
}

output "efs_csi_irsa_role_arn" {
  description = "IAM role ARN for the EFS CSI controller service account"
  value       = module.irsa.efs_csi_irsa_role_arn
}

output "efs_filesystem_id" {
  description = "EFS filesystem ID to use in StorageClass fileSystemId"
  value       = module.efs.filesystem_id
}

output "efs_storageclass_filesystem_id" {
  description = "Convenience output for kube-deploy/41-storageclass-efs-rwx.yaml fileSystemId"
  value       = module.efs.filesystem_id
}

output "service_account_annotation" {
  description = "Service account annotation key/value for IRSA"
  value       = module.irsa.service_account_annotation
}

output "kubectl_update_kubeconfig_command" {
  description = "Command to add this EKS cluster to your local kubectl kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "kubectl_get_nodes_command" {
  description = "Command to verify kubectl connectivity to the EKS cluster"
  value       = "kubectl get nodes -o wide"
}

output "efs_storageclass_patch_command" {
  description = "Command to patch fileSystemId placeholder in kube-deploy StorageClass"
  value       = "sed -i 's|REPLACE_WITH_EFS_FILESYSTEM_ID|${module.efs.filesystem_id}|g' ../kube-deploy/41-storageclass-efs-rwx.yaml"
}
