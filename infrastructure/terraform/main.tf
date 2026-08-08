provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.expected_aws_account_id]

  default_tags {
    tags = {
      Project   = "MamaAir synthetic public data"
      ManagedBy = "Terraform"
      Dataset   = "mamaair-ssa-climate-maternal-wq1"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  public_release_prefix = "releases/${var.dataset_version}"
}

resource "aws_s3_bucket" "public_release" {
  bucket        = var.bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "public_release" {
  bucket = aws_s3_bucket.public_release.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "public_release" {
  bucket = aws_s3_bucket.public_release.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "public_release" {
  bucket = aws_s3_bucket.public_release.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "public_release" {
  bucket = aws_s3_bucket.public_release.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = !var.public_dataset_access_enabled
  restrict_public_buckets = !var.public_dataset_access_enabled
}

data "aws_iam_policy_document" "public_release" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.public_release.arn,
      "${aws_s3_bucket.public_release.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  dynamic "statement" {
    for_each = var.public_dataset_access_enabled ? [1] : []
    content {
      sid    = "AllowAnonymousListOfCuratedReleaseOnly"
      effect = "Allow"

      principals {
        type        = "*"
        identifiers = ["*"]
      }

      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.public_release.arn]

      condition {
        test     = "StringLike"
        variable = "s3:prefix"
        values   = ["${local.public_release_prefix}/*"]
      }
    }
  }

  dynamic "statement" {
    for_each = var.public_dataset_access_enabled ? [1] : []
    content {
      sid    = "AllowAnonymousReadOfCuratedReleaseOnly"
      effect = "Allow"

      principals {
        type        = "*"
        identifiers = ["*"]
      }

      actions   = ["s3:GetObject"]
      resources = ["${aws_s3_bucket.public_release.arn}/${local.public_release_prefix}/*"]
    }
  }
}

resource "aws_s3_bucket_policy" "public_release" {
  bucket = aws_s3_bucket.public_release.id
  policy = data.aws_iam_policy_document.public_release.json

  depends_on = [aws_s3_bucket_public_access_block.public_release]
}

resource "aws_kinesis_stream" "synthetic_replay" {
  name             = var.kinesis_stream_name
  retention_period = 24
  encryption_type  = "KMS"
  kms_key_id       = "alias/aws/kinesis"

  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
}

data "aws_iam_policy_document" "producer" {
  statement {
    sid       = "WriteMamaAirReplayOnly"
    effect    = "Allow"
    actions   = ["kinesis:PutRecords"]
    resources = [aws_kinesis_stream.synthetic_replay.arn]
  }
}

resource "aws_iam_policy" "producer" {
  name        = "${var.kinesis_stream_name}-producer"
  description = "Least-privilege PutRecords access for the MamaAir synthetic replay producer."
  policy      = data.aws_iam_policy_document.producer.json
}

data "aws_iam_policy_document" "smoke_test_operator" {
  statement {
    sid    = "VerifyMamaAirReplayOnly"
    effect = "Allow"
    actions = [
      "kinesis:DescribeStreamSummary",
      "kinesis:GetRecords",
      "kinesis:GetShardIterator",
      "kinesis:ListShards",
      "kinesis:PutRecords",
    ]
    resources = [aws_kinesis_stream.synthetic_replay.arn]
  }
}

resource "aws_iam_policy" "smoke_test_operator" {
  name        = "${var.kinesis_stream_name}-smoke-test"
  description = "Least-privilege publish/read-back access for the authorized MamaAir Kinesis smoke test."
  policy      = data.aws_iam_policy_document.smoke_test_operator.json
}
