output "authenticated_account_id" {
  description = "Account in which Terraform resolved resources."
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region containing the public release bucket and replay stream."
  value       = var.aws_region
}

output "bucket_name" {
  value = aws_s3_bucket.public_release.id
}

output "bucket_arn" {
  value = aws_s3_bucket.public_release.arn
}

output "public_release_prefix" {
  value = "${local.public_release_prefix}/"
}

output "release_base_url" {
  value = "https://${aws_s3_bucket.public_release.id}.s3.${var.aws_region}.amazonaws.com/${local.public_release_prefix}/"
}

output "sample_records_url" {
  value = "https://${aws_s3_bucket.public_release.id}.s3.${var.aws_region}.amazonaws.com/${local.public_release_prefix}/sample_records.json"
}

output "schema_url" {
  value = "https://${aws_s3_bucket.public_release.id}.s3.${var.aws_region}.amazonaws.com/${local.public_release_prefix}/schema.json"
}

output "documentation_url" {
  value = "https://${aws_s3_bucket.public_release.id}.s3.${var.aws_region}.amazonaws.com/${local.public_release_prefix}/README.md"
}

output "stream_name" {
  value = aws_kinesis_stream.synthetic_replay.name
}

output "stream_arn" {
  value = aws_kinesis_stream.synthetic_replay.arn
}

output "producer_policy_arn" {
  value = aws_iam_policy.producer.arn
}

output "smoke_test_policy_arn" {
  value = aws_iam_policy.smoke_test_operator.arn
}
