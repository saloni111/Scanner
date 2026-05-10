# Deploying to AWS

This is a quick reference for shipping the scanner to AWS. The setup is the
classic "Fargate + RDS" pattern.

## What you'll create

| Resource | Purpose |
|---|---|
| ECR repo `code-security-scanner` | Stores the Docker image |
| RDS PostgreSQL 15+ instance | Application + pgvector database |
| ECS cluster (Fargate) | Runs the API |
| Application Load Balancer | Public TLS endpoint -> port 8000 |
| Secrets Manager entries | `DATABASE_URL`, `OPENAI_API_KEY`, `GITHUB_TOKEN` |
| CloudWatch log group `/ecs/code-security-scanner` | App logs |

## 1. Build & push the image

```bash
aws ecr create-repository --repository-name code-security-scanner
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

docker build -t code-security-scanner .
docker tag  code-security-scanner:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/code-security-scanner:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/code-security-scanner:latest
```

## 2. Set up the database

Spin up an RDS PostgreSQL instance (any size; `db.t4g.micro` is plenty for
a demo). After it boots, enable the `vector` extension once:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Store the connection string in Secrets Manager under
`scanner/database-url`, e.g.
`postgresql+psycopg2://scanner:PASSWORD@scanner.xxxx.us-east-1.rds.amazonaws.com:5432/scanner`.

## 3. Run migrations

You can either run a one-off ECS task or apply locally pointed at RDS:

```bash
DATABASE_URL='postgresql+psycopg2://...' alembic upgrade head
DATABASE_URL='postgresql+psycopg2://...' python -m app.rag.cve_loader --seed
```

## 4. Register the task definition

Edit `task-definition.json` and replace every `ACCOUNT_ID` placeholder, then:

```bash
aws ecs register-task-definition --cli-input-json file://deploy/aws/task-definition.json
```

## 5. Create the service

```bash
aws ecs create-service \
  --cluster scanner \
  --service-name scanner-api \
  --task-definition code-security-scanner \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-...,subnet-...],securityGroups=[sg-...],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=scanner-api,containerPort=8000"
```

Point your domain at the ALB and you're live. The container's
`HEALTHCHECK` and the `/health` endpoint give the load balancer something
to probe.

## Updating

```bash
docker build -t code-security-scanner . && \
docker push  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/code-security-scanner:latest && \
aws ecs update-service --cluster scanner --service scanner-api --force-new-deployment
```
