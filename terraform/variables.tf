variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for all resources (e.g. 'ai-shorts-john'). Must be globally unique — used as S3 bucket name prefix."
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 bucket name for video input/output. Must be globally unique across all AWS accounts."
  type        = string
}

variable "ecr_repo_name" {
  description = "ECR repository name"
  type        = string
  default     = "ai-shorts"
}

variable "container_image" {
  description = "Full ECR image URI (including tag). Update this after each docker push."
  type        = string
  # Example: "123456789.dkr.ecr.us-east-1.amazonaws.com/ai-shorts:latest"
  # Set via: terraform apply -var="container_image=<uri>"
  default     = ""
}
