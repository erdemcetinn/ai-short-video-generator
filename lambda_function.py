import boto3
import urllib.parse
import os

ECS_CLUSTER = os.environ["ECS_CLUSTER"]
TASK_DEFINITION = os.environ["ECS_TASK_DEF"]
CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "ai-shorts")
SUBNETS = [os.environ["SUBNET_ID"]]
SECURITY_GROUPS = [os.environ["SECURITY_GRP_ID"]]
S3_BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ.get("REGION", "us-east-1")


def lambda_handler(event, context):
    s3_event = event["Records"][0]["s3"]
    bucket = s3_event["bucket"]["name"]
    key = urllib.parse.unquote_plus(s3_event["object"]["key"])

    # Only process files uploaded to input/
    if not key.startswith("input/"):
        print(f"Skipping: {key}")
        return

    # Read prompt from S3 object metadata
    s3_client = boto3.client("s3")
    response = s3_client.head_object(Bucket=bucket, Key=key)
    prompt = response.get("Metadata", {}).get("prompt", "")

    s3_video_url = f"s3://{bucket}/{key}"
    s3_output = f"s3://{bucket}/output/"

    # Start ECS task
    ecs_client = boto3.client("ecs", region_name=REGION)

    command = [
        "python", "main.py",
        "--video", s3_video_url,
        "--s3-output", s3_output,
        "--auto-approve"
    ]
    if prompt:
        command += ["--prompt", prompt]

    response = ecs_client.run_task(
        cluster=ECS_CLUSTER,
        taskDefinition=TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": SUBNETS,
                "securityGroups": SECURITY_GROUPS,
                "assignPublicIp": "ENABLED"
            }
        },
        overrides={
            "containerOverrides": [{
                "name": CONTAINER_NAME,
                "command": command,
                "environment": [
                    {"name": "S3_BUCKET", "value": S3_BUCKET}
                ]
            }]
        }
    )

    task_arn = response["tasks"][0]["taskArn"] if response["tasks"] else "unknown"
    print(f"ECS task started: {task_arn}")
    print(f"Video: {s3_video_url}")
    print(f"Prompt: {prompt or '(none, AI will select)'}")

    return {"taskArn": task_arn}
