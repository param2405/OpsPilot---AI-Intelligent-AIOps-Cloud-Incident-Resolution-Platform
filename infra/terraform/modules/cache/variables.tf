variable "environment" {
  type = string
}

variable "database_subnet_ids" {
  type = list(string)
}

variable "redis_security_group_id" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "num_cache_nodes" {
  type    = number
  default = 1
}

variable "redis_auth_token" {
  type      = string
  sensitive = true
}
