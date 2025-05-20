# Jarvis MVP Runbook

## Deployment Guide

### Environments

1. **Staging (develop branch)**
   - URL: `https://staging.yourdomain.com`
   - Database: `staging_db`
   - Auto-deployed on push to `develop` branch

2. **Production (main branch)**
   - URL: `https://yourdomain.com`
   - Database: `production_db`
   - Deployed manually after staging verification

### Deployment Process

#### Staging Deployment
1. Push changes to `develop` branch
2. CI/CD pipeline automatically:
   - Runs tests
   - Deploys to staging
   - Runs smoke tests

#### Production Deployment
1. Create PR from `develop` to `main`
2. After PR is merged:
   - CI/CD pipeline runs tests
   - Manual approval required
   - Deploys to production
   - Runs smoke tests

### Manual Deployment

```bash
# Deploy to staging
git checkout develop
git pull
# Make changes and commit
git push

# Deploy to production (after PR merge)
git checkout main
git pull
# Trigger manual deployment via GitHub Actions UI
```

## Failure Scenarios & Recovery

### 1. Deployment Failure

**Symptoms:**
- GitHub Actions workflow fails
- Application not accessible
- Error in logs

**Recovery Steps:**
1. Check GitHub Actions logs
2. Rollback to previous version:
   ```bash
   git revert <bad-commit>
   git push
   ```
3. If rollback not possible, redeploy previous working version

### 2. Database Issues

**Symptoms:**
- Database connection errors
- Data inconsistency
- Migration failures

**Recovery Steps:**
1. Check database logs
2. If migration failed:
   ```bash
   # Rollback last migration
   alembic downgrade -1
   ```
3. Restore from backup if needed

### 3. Performance Issues

**Symptoms:**
- Slow response times
- Timeout errors
- High server load

**Recovery Steps:**
1. Check monitoring dashboards
2. Scale up resources if needed
3. Check for long-running queries
4. Restart services if necessary

## Monitoring & Alerts

### Status Pages
- GitHub Actions: https://github.com/TerraTectra/jarvis-mvp-production/actions
- Application Health: `/health` endpoint
- Database: Cloud provider dashboard

### Alerts
- Failed deployments via Telegram
- Error rate > 1%
- Response time > 1s (p95)
- Server CPU > 80% for 5 minutes

## Rollback Procedure

1. **Code Rollback**
   ```bash
   git revert <bad-commit>
   git push
   ```

2. **Database Rollback**
   ```bash
   # List migrations
   alembic history
   
   # Rollback to specific migration
   alembic downgrade <revision>
   ```

3. **Infrastructure Rollback**
   - Revert Terraform changes if applicable
   - Rollback Docker images

## Emergency Contacts

- DevOps: devops@yourcompany.com
- On-call Engineer: +1234567890
- Management: management@yourcompany.com
