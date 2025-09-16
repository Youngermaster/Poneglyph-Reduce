# AWS S3 Integration for MapReduce Results

This document explains how to use the AWS S3 integration for storing MapReduce job results.

## Overview

The S3 integration provides automatic storage of MapReduce job results to Amazon S3, in addition to the existing local file storage. This enables:

- **Persistent storage** beyond container lifecycles
- **Scalable storage** for large result datasets
- **Access control** via AWS IAM
- **Metadata tracking** with job information
- **Temporary access** via pre-signed URLs

## Setup

### 1. Create S3 Bucket

Create an S3 bucket in your AWS account:

```bash
aws s3 mb s3://your-mapreduce-results-bucket
```

### 2. Configure AWS Credentials

Set up AWS credentials using one of these methods:

#### Option A: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_REGION=us-east-1
```

#### Option B: AWS CLI Configuration

```bash
aws configure
```

#### Option C: IAM Roles (for EC2/ECS deployment)

Use IAM roles with the required S3 permissions.

### 3. Set S3 Configuration

Configure the S3 settings via environment variables:

```bash
export AWS_S3_BUCKET=your-mapreduce-results-bucket
export AWS_S3_BASE_PATH=mapreduce-results/
export AWS_REGION=us-east-1
```

### 4. Enable S3 Storage

To enable S3 storage, uncomment the S3-related code in:

- `src/core/Scheduler.java`: Uncomment the `storeResultInS3(ctx);` call and the method
- `src/store/RedisStore.java`: Uncomment the `storeResultInS3(jobId, output);` call and the method
- Import statements: Uncomment `import utils.S3Utils;` in both files

## Required AWS Permissions

Your AWS credentials need the following S3 permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-mapreduce-results-bucket",
        "arn:aws:s3:::your-mapreduce-results-bucket/*"
      ]
    }
  ]
}
```

## Storage Structure

Results are stored in S3 with the following structure:

```
s3://your-bucket/mapreduce-results/jobs/
├── job-001/
│   ├── 2024-01-15_14-30-45_result.txt
│   └── 2024-01-15_15-22-10_result.txt
├── job-002/
│   └── 2024-01-15_16-45-30_result.txt
└── ...
```

## Metadata

Each stored result includes metadata:

- `job-id`: The MapReduce job identifier
- `timestamp`: When the result was stored
- `content-length`: Size of the result in bytes
- `job-type`: Always "mapreduce"
- `maps-completed`: Number of completed map tasks
- `reduces-completed`: Number of completed reduce tasks
- `final-output-size`: Size of the final output

## Usage Examples

### Basic Usage

```java
// The S3Utils class is automatically used when enabled
S3Utils s3Utils = S3Utils.fromEnvironment();
if (s3Utils != null && s3Utils.isBucketAccessible()) {
    String s3Key = s3Utils.storeJobResult("job-123", "result content");
    System.out.println("Stored at: " + s3Key);
}
```

### With Custom Metadata

```java
Map<String, String> metadata = new HashMap<>();
metadata.put("custom-field", "custom-value");

String s3Key = s3Utils.storeJobResultWithMetadata(
    "job-123",
    "result content",
    metadata
);
```

### Generate Access URLs

```java
// Generate a pre-signed URL valid for 24 hours
String presignedUrl = s3Utils.generatePresignedUrl(s3Key, 24 * 60);
System.out.println("Temporary access URL: " + presignedUrl);
```

## Docker Deployment

For Docker deployment, add the S3 configuration to your `docker-compose.yml`:

```yaml
services:
  master:
    environment:
      - AWS_S3_BUCKET=your-mapreduce-results-bucket
      - AWS_S3_BASE_PATH=mapreduce-results/
      - AWS_REGION=us-east-1
      - AWS_ACCESS_KEY_ID=your-access-key-id
      - AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

## Testing

To test the S3 integration:

1. Set up the configuration as described above
2. Uncomment the S3 storage code in the source files
3. Rebuild and run the application
4. Submit a MapReduce job
5. Check the S3 bucket for the stored results

## Troubleshooting

### Common Issues

1. **Bucket not accessible**: Check bucket name and AWS credentials
2. **Permission denied**: Verify IAM permissions for S3 operations
3. **Region mismatch**: Ensure AWS_REGION matches your bucket's region
4. **Network issues**: Check network connectivity to AWS S3

### Debug Logging

The S3Utils class provides detailed logging for troubleshooting:

- `[S3]`: Successful operations
- `[S3 WARN]`: Configuration warnings
- `[S3 ERROR]`: Error conditions

Check application logs for these messages to diagnose issues.
