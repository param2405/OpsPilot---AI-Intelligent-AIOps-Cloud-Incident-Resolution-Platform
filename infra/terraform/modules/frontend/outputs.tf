output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "cloudfront_distribution_arn" {
  value = aws_cloudfront_distribution.main.arn
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.main.domain_name
}
