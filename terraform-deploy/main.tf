data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  public_subnet_az  = data.aws_availability_zones.available.names[0]
  private_subnet_az = try(data.aws_availability_zones.available.names[1], data.aws_availability_zones.available.names[0])
}

module "vpc" {
  source = "./modules/vpc"

  project_name        = var.project_name
  cluster_name        = var.cluster_name
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidr  = var.public_subnet_cidr
  private_subnet_cidr = var.private_subnet_cidr
  public_subnet_az    = local.public_subnet_az
  private_subnet_az   = local.private_subnet_az
}

module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

module "sns" {
  source = "./modules/sns"

  project_name        = var.project_name
  environment         = var.environment
  subscription_emails = var.sns_subscription_emails
}

module "efs" {
  source = "./modules/efs"

  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  vpc_cidr     = var.vpc_cidr
  subnet_ids   = [module.vpc.public_subnet_id, module.vpc.private_subnet_id]
}

module "eks" {
  source = "./modules/eks"

  project_name       = var.project_name
  cluster_name       = var.cluster_name
  kubernetes_version = var.kubernetes_version
  vpc_id             = module.vpc.vpc_id
  cluster_subnet_ids = [module.vpc.public_subnet_id, module.vpc.private_subnet_id]

  # No NAT is used, so nodes run in the public subnet for outbound internet access via IGW.
  node_subnet_ids    = [module.vpc.public_subnet_id]
  node_instance_type = var.node_instance_type
  node_desired_size  = var.node_desired_size
  node_min_size      = var.node_min_size
  node_max_size      = var.node_max_size
}

module "irsa" {
  source = "./modules/irsa"

  project_name                      = var.project_name
  cluster_oidc_issuer_url           = module.eks.cluster_oidc_issuer_url
  service_account_namespace         = var.service_account_namespace
  service_account_name              = var.service_account_name
  efs_csi_service_account_namespace = var.efs_csi_service_account_namespace
  efs_csi_service_account_name      = var.efs_csi_service_account_name
  s3_bucket_arn                     = module.s3.bucket_arn
  sns_topic_arn                     = module.sns.topic_arn
}

resource "aws_eks_addon" "efs_csi_driver" {
  count = var.enable_efs_csi_addon ? 1 : 0

  cluster_name                = module.eks.cluster_name
  addon_name                  = "aws-efs-csi-driver"
  service_account_role_arn    = module.irsa.efs_csi_irsa_role_arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}
