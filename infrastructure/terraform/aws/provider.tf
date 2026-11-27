provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }

  # No access_key/secret_key/profile here and no credentials configured anywhere in this
  # skeleton (Issue #160) -- `terraform validate`/`fmt -check` only perform static
  # configuration checks and never need a real AWS account. `terraform plan`/`apply` must
  # never be run against this file without the user explicitly provisioning real credentials
  # first, which this Task does not do.
}
