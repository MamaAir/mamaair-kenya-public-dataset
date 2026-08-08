variable "aws_region" {
  description = "Authorized AWS Region for the public bucket and Kinesis stream."
  type        = string

  validation {
    condition     = can(regex("^(af|ap|ca|eu|il|me|mx|sa|us)(-gov)?-[a-z0-9-]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be an AWS Region identifier such as eu-west-1."
  }
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name selected by the authorized operator."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "bucket_name must be a valid 3-63 character S3 bucket name without dots so the HTTPS URL remains certificate-safe."
  }
}

variable "dataset_version" {
  description = "Immutable public release version used under releases/<version>/."
  type        = string
  default     = "v1"

  validation {
    condition     = can(regex("^v[1-9][0-9]*$", var.dataset_version))
    error_message = "dataset_version must use the form v1, v2, and so on."
  }
}

variable "kinesis_stream_name" {
  description = "Name selected for the synthetic replay stream."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]{1,128}$", var.kinesis_stream_name))
    error_message = "kinesis_stream_name must be 1-128 valid Kinesis name characters."
  }
}

variable "expected_aws_account_id" {
  description = "Explicitly authorized 12-digit AWS account ID. Never guess this value."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_aws_account_id))
    error_message = "expected_aws_account_id must contain exactly 12 digits."
  }
}

variable "public_dataset_access_enabled" {
  description = "Allow anonymous GetObject only under releases/<dataset_version>/. Account-level S3 controls are not changed."
  type        = bool
  default     = false
}
