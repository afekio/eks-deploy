#!/usr/bin/env bash
# get_vault_pass.sh

aws secretsmanager get-secret-value \
  --secret-id "prod/ansible/vault-key" \
  --query SecretString \
  --output text