# ── Lambda: Upload Handler (presigned URL) ────────────────────────────────────

data "archive_file" "lambda_upload" {
  type        = "zip"
  source_file = "${path.module}/../lambda_upload.py"
  output_path = "${path.module}/../lambda_upload.zip"
}

resource "aws_lambda_function" "upload" {
  function_name    = "${var.project_name}-upload"
  filename         = data.archive_file.lambda_upload.output_path
  source_code_hash = data.archive_file.lambda_upload.output_base64sha256
  handler          = "lambda_upload.lambda_handler"
  runtime          = "python3.13"
  role             = aws_iam_role.lambda.arn
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      REGION    = var.aws_region
    }
  }
}

# ── Lambda: Status Checker ────────────────────────────────────────────────────

data "archive_file" "lambda_status" {
  type        = "zip"
  source_file = "${path.module}/../lambda_status.py"
  output_path = "${path.module}/../lambda_status.zip"
}

resource "aws_lambda_function" "status" {
  function_name    = "${var.project_name}-status"
  filename         = data.archive_file.lambda_status.output_path
  source_code_hash = data.archive_file.lambda_status.output_base64sha256
  handler          = "lambda_status.lambda_handler"
  runtime          = "python3.13"
  role             = aws_iam_role.lambda.arn
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET = var.s3_bucket_name
      REGION    = var.aws_region
    }
  }
}

# ── Lambda: S3 Trigger (S3 event → ECS task) ─────────────────────────────────

data "archive_file" "lambda_trigger" {
  type        = "zip"
  source_file = "${path.module}/../lambda_function.py"
  output_path = "${path.module}/../lambda.zip"
}

resource "aws_lambda_function" "trigger" {
  function_name    = "${var.project_name}-trigger"
  filename         = data.archive_file.lambda_trigger.output_path
  source_code_hash = data.archive_file.lambda_trigger.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.13"
  role             = aws_iam_role.lambda.arn
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET       = var.s3_bucket_name
      REGION          = var.aws_region
      ECS_CLUSTER     = aws_ecs_cluster.main.name
      ECS_TASK_DEF    = aws_ecs_task_definition.main.arn
      SUBNET_ID       = data.aws_subnets.default.ids[0]
      SECURITY_GRP_ID = aws_security_group.ecs_tasks.id
    }
  }
}

# Allow S3 to invoke the trigger Lambda
resource "aws_lambda_permission" "s3_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.main.arn
}

# S3 bucket notification → trigger Lambda on new input/ objects
resource "aws_s3_bucket_notification" "trigger" {
  bucket = aws_s3_bucket.main.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "input/"
  }

  depends_on = [aws_lambda_permission.s3_trigger]
}
