import boto3
import os
from botocore.exceptions import ClientError

# S3 configuration from environment variables
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("AWS_S3_BUCKET")
S3_REGION = os.getenv("AWS_S3_REGION", "eu-west-1")

# Create S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)


def upload_photo_to_s3(file_content: bytes, filename: str) -> str:
    """
    Upload photo to S3 bucket.
    Returns: S3 URL of the uploaded file
    """
    try:
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=f"photos/{filename}",
            Body=file_content,
            ContentType="image/jpeg"
        )

        # Return S3 URL
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/photos/{filename}"
        return s3_url
    except ClientError as e:
        print(f"[S3] Upload hatası: {e}")
        return None


def delete_photo_from_s3(filename: str) -> bool:
    """Delete photo from S3 bucket."""
    try:
        s3_client.delete_object(
            Bucket=S3_BUCKET,
            Key=f"photos/{filename}"
        )
        return True
    except ClientError as e:
        print(f"[S3] Delete hatası: {e}")
        return False
