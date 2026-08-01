resource "aws_security_group" "efs" {
  name        = "${var.project_name}-${var.environment}-efs-sg"
  description = "Allow NFS from VPC to EFS"
  vpc_id      = var.vpc_id

  ingress {
    description = "NFS from VPC"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-efs-sg"
  }
}

resource "aws_efs_file_system" "this" {
  creation_token = "${var.project_name}-${var.environment}-efs"
  encrypted      = true

  throughput_mode  = "bursting"
  performance_mode = "generalPurpose"

  tags = {
    Name = "${var.project_name}-${var.environment}-efs"
  }
}

locals {
  # Use deterministic keys so for_each can be planned even when subnet IDs are unknown until apply.
  mount_target_subnets = {
    for idx, subnet_id in var.subnet_ids : tostring(idx) => subnet_id
  }
}

resource "aws_efs_mount_target" "this" {
  for_each = local.mount_target_subnets

  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}