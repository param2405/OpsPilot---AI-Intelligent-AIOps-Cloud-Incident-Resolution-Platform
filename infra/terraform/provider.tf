provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "OpsPilot-AI"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "https://github.com/param2405/OpsPilot"
    }
  }
}

# Secondary provider for CloudFront ACM certificates (which must reside in us-east-1)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "OpsPilot-AI"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
