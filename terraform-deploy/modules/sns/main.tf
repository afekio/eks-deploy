resource "aws_sns_topic" "this" {
  name = "${var.project_name}-${var.environment}-topic"

  tags = {
    Name = "${var.project_name}-${var.environment}-topic"
  }
}

# One email subscription per address in var.subscription_emails.
# Each subscriber must confirm the emailed link before alerts are delivered.
resource "aws_sns_topic_subscription" "email" {
  for_each = toset(var.subscription_emails)

  topic_arn = aws_sns_topic.this.arn
  protocol  = "email"
  endpoint  = each.value
}