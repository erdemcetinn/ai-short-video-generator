# ── Networking ────────────────────────────────────────────────────────────────
# ECS Fargate tasks need to run in a VPC subnet.
# We use the default VPC that every AWS account already has —
# no need to create a custom VPC for this project.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security group: allow outbound internet (to reach AssemblyAI, OpenAI, S3)
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-sg"
  description = "Allow outbound traffic for ECS Fargate tasks"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
