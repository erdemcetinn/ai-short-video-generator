import boto3
import json
import os
import uuid

S3_BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ["REGION"]


def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS"
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        body = json.loads(event["body"])
        filename = body.get("filename", "video.mp4")
        prompt = body.get("prompt", "")

        key = f"input/{uuid.uuid4()}_{filename}"

        s3_client = boto3.client("s3", region_name=REGION)
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": key,
                "ContentType": "video/mp4",
                "Metadata": {"prompt": prompt} if prompt else {}
            },
            ExpiresIn=300
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "upload_url": presigned_url,
                "key": key
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }
