variable "environment" {
  type = string
}

variable "database_subnet_ids" {
  type = list(string)
}

variable "rds_security_group_id" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  type    = number
  default = 100
}

variable "multi_az" {
  type    = bool
  default = false
}

variable "backup_retention_period" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "db_username" {
  type    = string
  default = "opspilot"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "db_name" {
  type    = string
  default = "opspilot"
}
