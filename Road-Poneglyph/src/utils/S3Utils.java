package utils;

import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Utility class for storing Map-Reduce results in AWS S3.
 * Provides methods to upload job results and manage S3 operations.
 */
public class S3Utils {

    private final S3Client s3Client;
    private final String bucketName;
    private final String basePath;

    /**
     * Constructor for S3Utils
     *
     * @param bucketName The S3 bucket name where results will be stored
     * @param region     AWS region for the bucket
     * @param basePath   Base path prefix for all stored objects (e.g., "mapreduce-results/")
     */
    public S3Utils(String bucketName, Region region, String basePath) {
        this.bucketName = bucketName;
        this.basePath = basePath.endsWith("/") ? basePath : basePath + "/";

        this.s3Client = S3Client.builder()
                .region(region)
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }

    /**
     * Constructor with default region (US_EAST_1)
     *
     * @param bucketName The S3 bucket name where results will be stored
     * @param basePath   Base path prefix for all stored objects
     */
    public S3Utils(String bucketName, String basePath) {
        this(bucketName, Region.US_EAST_1, basePath);
    }

    /**
     * Store Map-Reduce job result in S3
     *
     * @param jobId  The job identifier
     * @param result The final result content to store
     * @return The S3 object key where the result was stored
     * @throws S3Exception if upload fails
     */
    public String storeJobResult(String jobId, String result) throws S3Exception {
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss"));
        String objectKey = basePath + "jobs/" + jobId + "/" + timestamp + "_result.txt";

        try {
            PutObjectRequest putRequest = PutObjectRequest.builder()
                    .bucket(bucketName)
                    .key(objectKey)
                    .contentType("text/plain")
                    .metadata(java.util.Map.of(
                            "job-id", jobId,
                            "timestamp", timestamp,
                            "content-length", String.valueOf(result.length())
                    ))
                    .build();

            RequestBody requestBody = RequestBody.fromString(result, StandardCharsets.UTF_8);

            PutObjectResponse response = s3Client.putObject(putRequest, requestBody);

            System.out.println("[S3] Successfully stored job result: s3://" + bucketName + "/" + objectKey);
            System.out.println("[S3] ETag: " + response.eTag());

            return objectKey;

        } catch (S3Exception e) {
            System.err.println("[S3 ERROR] Failed to store job result for " + jobId + ": " + e.getMessage());
            throw e;
        }
    }

    /**
     * Store Map-Reduce job result with additional metadata
     *
     * @param jobId    The job identifier
     * @param result   The final result content to store
     * @param metadata Additional metadata to store with the object
     * @return The S3 object key where the result was stored
     * @throws S3Exception if upload fails
     */
    public String storeJobResultWithMetadata(String jobId, String result, java.util.Map<String, String> metadata) throws S3Exception {
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss"));
        String objectKey = basePath + "jobs/" + jobId + "/" + timestamp + "_result.txt";

        try {
            // Merge default metadata with provided metadata
            java.util.Map<String, String> fullMetadata = new java.util.HashMap<>();
            fullMetadata.put("job-id", jobId);
            fullMetadata.put("timestamp", timestamp);
            fullMetadata.put("content-length", String.valueOf(result.length()));
            fullMetadata.putAll(metadata);

            PutObjectRequest putRequest = PutObjectRequest.builder()
                    .bucket(bucketName)
                    .key(objectKey)
                    .contentType("text/plain")
                    .metadata(fullMetadata)
                    .build();

            RequestBody requestBody = RequestBody.fromString(result, StandardCharsets.UTF_8);

            PutObjectResponse response = s3Client.putObject(putRequest, requestBody);

            System.out.println("[S3] Successfully stored job result with metadata: s3://" + bucketName + "/" + objectKey);
            System.out.println("[S3] ETag: " + response.eTag());

            return objectKey;

        } catch (S3Exception e) {
            System.err.println("[S3 ERROR] Failed to store job result for " + jobId + ": " + e.getMessage());
            throw e;
        }
    }

    /**
     * Check if a bucket exists and is accessible
     *
     * @return true if bucket exists and is accessible, false otherwise
     */
    public boolean isBucketAccessible() {
        try {
            HeadBucketRequest headBucketRequest = HeadBucketRequest.builder()
                    .bucket(bucketName)
                    .build();

            s3Client.headBucket(headBucketRequest);
            return true;

        } catch (S3Exception e) {
            System.err.println("[S3 WARN] Bucket " + bucketName + " is not accessible: " + e.getMessage());
            return false;
        }
    }

    /**
     * List all stored results for a specific job
     *
     * @param jobId The job identifier
     * @return List of S3 object keys for the job results
     */
    public java.util.List<String> listJobResults(String jobId) {
        String prefix = basePath + "jobs/" + jobId + "/";

        try {
            ListObjectsV2Request listRequest = ListObjectsV2Request.builder()
                    .bucket(bucketName)
                    .prefix(prefix)
                    .build();

            ListObjectsV2Response listResponse = s3Client.listObjectsV2(listRequest);

            return listResponse.contents().stream()
                    .map(S3Object::key)
                    .collect(java.util.stream.Collectors.toList());

        } catch (S3Exception e) {
            System.err.println("[S3 ERROR] Failed to list results for job " + jobId + ": " + e.getMessage());
            return java.util.Collections.emptyList();
        }
    }

    /**
     * Get the public URL for a stored result (if bucket allows public access)
     *
     * @param objectKey The S3 object key
     * @return The public URL string
     */
    public String getPublicUrl(String objectKey) {
        return String.format("https://%s.s3.%s.amazonaws.com/%s",
                bucketName, s3Client.serviceClientConfiguration().region().id(), objectKey);
    }

    /**
     * Generate a pre-signed URL for temporary access to a result
     *
     * @param objectKey       The S3 object key
     * @param durationMinutes Duration in minutes for URL validity
     * @return The pre-signed URL string
     */
    public String generatePresignedUrl(String objectKey, int durationMinutes) {
        try {
            // Create an S3Presigner using the default region and credentials
            software.amazon.awssdk.services.s3.presigner.S3Presigner presigner =
                    software.amazon.awssdk.services.s3.presigner.S3Presigner.create();

            // Create a GetObjectRequest to be pre-signed
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(bucketName)
                    .key(objectKey)
                    .build();

            // Create a GetObjectPresignRequest to specify the signature duration
            software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest presignRequest =
                    software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest.builder()
                            .signatureDuration(java.time.Duration.ofMinutes(durationMinutes))
                            .getObjectRequest(getObjectRequest)
                            .build();

            // Generate the presigned request
            software.amazon.awssdk.services.s3.presigner.model.PresignedGetObjectRequest presignedRequest =
                    presigner.presignGetObject(presignRequest);

            // Close the presigner to free resources
            presigner.close();

            return presignedRequest.url().toString();

        } catch (Exception e) {
            System.err.println("[S3 ERROR] Failed to generate presigned URL for " + objectKey + ": " + e.getMessage());
            return null;
        }
    }

    /**
     * Close the S3 client and release resources
     */
    public void close() {
        if (s3Client != null) {
            s3Client.close();
        }
    }

    /**
     * Create a configured S3Utils instance from environment variables
     * Expected environment variables:
     * - AWS_S3_BUCKET: The S3 bucket name
     * - AWS_S3_BASE_PATH: Base path for storing results (optional, defaults to "mapreduce-results/")
     * - AWS_REGION: AWS region (optional, defaults to us-east-1)
     *
     * @return Configured S3Utils instance or null if required environment variables are missing
     */
    public static S3Utils fromEnvironment() {
        String bucketName = System.getenv("AWS_S3_BUCKET");
        if (bucketName == null || bucketName.trim().isEmpty()) {
            System.err.println("[S3 WARN] AWS_S3_BUCKET environment variable not set. S3 storage disabled.");
            return null;
        }

        String basePath = System.getenv("AWS_S3_BASE_PATH");
        if (basePath == null || basePath.trim().isEmpty()) {
            basePath = "mapreduce-results/";
        }

        String regionStr = System.getenv("AWS_REGION");
        Region region = Region.US_EAST_1; // default
        if (regionStr != null && !regionStr.trim().isEmpty()) {
            try {
                region = Region.of(regionStr);
            } catch (Exception e) {
                System.err.println("[S3 WARN] Invalid AWS_REGION: " + regionStr + ". Using default: us-east-1");
            }
        }

        return new S3Utils(bucketName, region, basePath);
    }
}
