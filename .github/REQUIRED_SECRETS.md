# Required GitHub Actions Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

## CI/CD

| Secret | Description |
|--------|-------------|
| `VERCEL_TOKEN` | Vercel personal access token |
| `VERCEL_ORG_ID` | Vercel org/team ID (from `vercel link`) |
| `VERCEL_PROJECT_ID` | Vercel project ID (from `vercel link`) |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key (deploy role only) |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |

## How to get Vercel IDs

```bash
npx vercel link   # creates .vercel/project.json with orgId + projectId
```

## AWS deploy role permissions (minimum required)

```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload",
    "ecs:UpdateService",
    "ecs:DescribeServices"
  ],
  "Resource": "*"
}
```
