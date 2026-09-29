variable "environment" {
  type = string
}

variable "kms_key_id" {
  type = string
}

variable "db_username" {
  type    = string
  default = "opspilot"
}

variable "db_name" {
  type    = string
  default = "opspilot"
}
