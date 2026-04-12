import boto3
import json
import os

S3_BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ["REGION"]


def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, OPTIONS"
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        # input key: input/abc123_video.mp4
        # output key: output/abc123_video_short.mp4
        params = event.get("queryStringParameters") or {}
        input_key = params.get("key", "")

        if not input_key:
            raise ValueError("Missing 'key' query parameter")

        # Derive expected output filename from input key
        filename = input_key.split("/")[-1]       # abc123_video.mp4
        name = filename.rsplit(".", 1)[0]          # abc123_video
        output_key = f"output/{name}_short.mp4"

        s3_client = boto3.client("s3", region_name=REGION)

        s3_client = boto3.client("s3", region_name=REGION)

        try:
            s3_client.head_object(Bucket=S3_BUCKET, Key=output_key)
        except Exception:
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps({"status": "processing"})
            }

        # File exists — generate presigned download URL
        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": output_key},
            ExpiresIn=3600
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "status": "done",
                "download_url": download_url
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }
