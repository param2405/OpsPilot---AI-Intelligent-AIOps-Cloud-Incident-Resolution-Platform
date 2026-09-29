output "db_instance_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "db_instance_address" {
  value = aws_db_instance.postgres.address
}

output "db_instance_port" {
  value = aws_db_instance.postgres.port
}

output "db_instance_name" {
  value = aws_db_instance.postgres.db_name
}

output "db_instance_id" {
  value = aws_db_instance.postgres.id
}
