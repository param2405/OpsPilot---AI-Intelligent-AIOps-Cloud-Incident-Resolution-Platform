# Dedicated Virtual Private Cloud (VPC)
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "opspilot-vpc-${var.environment}"
  }
}

# Internet Gateway for Public Egress/Ingress
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "opspilot-igw-${var.environment}"
  }
}

# Public Subnets (Hosts ALB and NAT Gateways)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "opspilot-public-${var.availability_zones[count.index]}-${var.environment}"
    Tier = "Public"
  }
}

# Private Application Subnets (Hosts ECS Fargate API and Background Workers)
resource "aws_subnet" "private_app" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "opspilot-private-app-${var.availability_zones[count.index]}-${var.environment}"
    Tier = "PrivateApplication"
  }
}

# Private Isolated Database Subnets (Hosts RDS PostgreSQL and ElastiCache Redis)
resource "aws_subnet" "private_db" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "opspilot-private-db-${var.availability_zones[count.index]}-${var.environment}"
    Tier = "PrivateDatabase"
  }
}

# Elastic IP(s) for NAT Gateway(s)
resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : length(var.availability_zones)
  domain = "vpc"

  tags = {
    Name = "opspilot-nat-eip-${count.index}-${var.environment}"
  }
  depends_on = [aws_internet_gateway.gw]
}

# NAT Gateway(s)
resource "aws_nat_gateway" "nat" {
  count         = var.single_nat_gateway ? 1 : length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "opspilot-nat-gw-${count.index}-${var.environment}"
  }
  depends_on = [aws_internet_gateway.gw]
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = {
    Name = "opspilot-public-rt-${var.environment}"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private Application Route Tables
resource "aws_route_table" "private_app" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.nat[0].id : aws_nat_gateway.nat[count.index].id
  }

  tags = {
    Name = "opspilot-private-app-rt-${var.availability_zones[count.index]}-${var.environment}"
  }
}

resource "aws_route_table_association" "private_app" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app[count.index].id
}

# Private Database Route Table (Completely isolated, no internet or NAT route)
resource "aws_route_table" "private_db" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "opspilot-private-db-rt-${var.environment}"
  }
}

resource "aws_route_table_association" "private_db" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private_db[count.index].id
  route_table_id = aws_route_table.private_db.id
}

# Cost Optimization: Amazon S3 Gateway VPC Endpoint (100% Free, bypasses NAT Gateway transfer costs)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(aws_route_table.private_app[*].id, [aws_route_table.private_db.id])

  tags = {
    Name = "opspilot-s3-gateway-endpoint-${var.environment}"
  }
}

data "aws_region" "current" {}
