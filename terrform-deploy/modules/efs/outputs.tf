output "filesystem_id" {
  description = "EFS filesystem ID"
  value       = aws_efs_file_system.this.id
}

output "filesystem_arn" {
  description = "EFS filesystem ARN"
  value       = aws_efs_file_system.this.arn
}

output "security_group_id" {
  description = "EFS security group ID"
  value       = aws_security_group.efs.id
}