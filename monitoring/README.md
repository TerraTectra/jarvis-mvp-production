# Monitoring Setup for Jarvis MVP

This directory contains the configuration for monitoring the Jarvis MVP application using Prometheus and Grafana.

## Components

1. **Prometheus** - Metrics collection and alerting
   - URL: http://localhost:9090
   - Configuration: `prometheus/prometheus.yml`
   - Alerting rules: `prometheus/alerts.yml`

2. **Grafana** - Visualization and dashboards
   - URL: http://localhost:3000
   - Default credentials: admin/admin (change this in production!)
   - Provisioning: `grafana/provisioning/`

3. **Node Exporter** - System metrics
   - Exposes system metrics on port 9100

## Getting Started

1. **Start the monitoring stack**:
   ```bash
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

2. **Access the dashboards**:
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090
   - Node Exporter: http://localhost:9100/metrics

## Setting Up GitHub Secrets

Run the setup script to configure the required GitHub secrets:

```powershell
# Make sure you have GitHub CLI (gh) installed and authenticated
.\scripts\setup-github-secrets.ps1
```

## Testing Alerts

To test Telegram alerts:

```powershell
.\scripts\send-telegram-alert.ps1 -Token "YOUR_BOT_TOKEN" -ChatId "YOUR_CHAT_ID" -Message "Test alert" -Level "info"
```

## Production Considerations

1. **Security**:
   - Change default credentials
   - Enable authentication
   - Use HTTPS
   - Restrict access to monitoring endpoints

2. **Persistence**:
   - Configure persistent volumes for Prometheus and Grafana data
   - Set up regular backups

3. **Scaling**:
   - Consider using Prometheus federation for multiple instances
   - Set up alert manager for better alert handling
