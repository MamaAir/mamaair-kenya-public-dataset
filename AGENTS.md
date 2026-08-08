# AWS Development Guidelines

- Prefer the AWS CLI or SDK for AWS interactions. Use infrastructure-as-code (Terraform or CloudFormation)
  for all infrastructure provisioning.
- When uncertain about specific AWS details (API parameters, permissions, limits, error codes), verify
  against the official AWS documentation.
- Follow AWS Well-Architected Framework principles when designing and deploying infrastructure.
- Use hyphens in AWS resource names and descriptions, not em dashes.
- Keep secrets out of source code. Use AWS Secrets Manager or environment variables for credential
  management. Never commit credentials to version control.
