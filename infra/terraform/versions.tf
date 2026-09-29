terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # In production, configure an S3 remote backend with DynamoDB locking:
  # backend "s3" {
  #   bucket         = "opspilot-terraform-state"
  #   key            = "state/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "opspilot-terraform-locks"
  #   encrypt        = true
  # }
}
