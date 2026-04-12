output "api_gateway_url" {
  description = "Base URL for the API Gateway (use this in index.html)"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "website_bucket_name" {
  description = "S3 bucket name for website hosting (upload index.html here)"
  value       = aws_s3_bucket.website.id
}

output "website_url" {
  description = "S3 static website URL"
  value       = "http://${aws_s3_bucket.website.bucket}.s3-website-${var.aws_region}.amazonaws.com"
}

output "ecr_repository_url" {
  description = "ECR repository URL (use for docker push)"
  value       = aws_ecr_repository.main.repository_url
}

output "s3_bucket_name" {
  description = "Main S3 bucket for video input/output"
  value       = aws_s3_bucket.main.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}
