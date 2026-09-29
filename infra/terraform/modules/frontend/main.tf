# 1. CloudFront Origin Access Control (OAC) for secure, private S3 bucket access
resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "opspilot-oac-${var.environment}"
  description                       = "Origin Access Control for OpsPilot React Frontend S3 Bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 2. S3 Bucket Policy allowing exclusively the CloudFront distribution to read assets
resource "aws_s3_bucket_policy" "frontend" {
  bucket = var.frontend_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipalReadOnly"
        Effect    = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${var.frontend_bucket_arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
          }
        }
      }
    ]
  })
}

# 3. CloudFront Security Response Headers Policy
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name    = "opspilot-security-headers-${var.environment}"
  comment = "Enforces OWASP-recommended security headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
  }
}

# 4. Amazon CloudFront Distribution (Edge Caching & Dynamic API Reverse Proxy)
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "OpsPilot AI Unified Edge Distribution (${var.environment})"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # Cost-effective edge locations

  # Origin 1: S3 Static Website Assets (React SPA)
  origin {
    domain_name              = var.frontend_bucket_domain_name
    origin_id                = "S3-Frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  # Origin 2: Application Load Balancer (FastAPI Dynamic REST API)
  origin {
    domain_name = var.alb_dns_name
    origin_id   = "ALB-FastAPI"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # ALB is in private/public VPC listener
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default Cache Behavior: Static React SPA assets from S3
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-Frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400    # 24 hours
    max_ttl     = 31536000 # 1 year
  }

  # Dynamic API Cache Behavior: Forward all /api/* requests directly to ALB
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "ALB-FastAPI"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # Zero caching for real-time dynamic API interactions
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host", "Accept", "Origin"]

      cookies {
        forward = "all"
      }
    }
  }

  # Single Page Application (SPA) Error Redirection
  # Translates client-side React routes to index.html with HTTP 200
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "opspilot-cloudfront-${var.environment}"
  }
}
