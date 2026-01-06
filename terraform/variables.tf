variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "vocal-extractor"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units"
  type        = number
  default     = 1024  # 1 vCPU
}

variable "task_memory" {
  description = "Fargate task memory (MiB)"
  type        = number
  default     = 4096  # 4 GB
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 1
}

variable "health_check_path" {
  description = "Health check path"
  type        = string
  default     = "/health"
}
