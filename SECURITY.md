# Security Guidelines - aMonitoringHub

## 🔐 Security Best Practices

### Environment Variables (REQUIRED)

All sensitive configuration **MUST** be set via environment variables, never hardcoded:

```bash
# Required for production
export FLASK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export GEMINI_API_KEY="your-gemini-api-key"
export LOG_LEVEL="ERROR"
```

### Development Setup

For development, use the `.env` file (never commit this):

1. Copy template: `cp .env.template .env`
2. Fill in your values
3. Run: `./setup.sh` (automated setup)

### Production Deployment

**NEVER use .env files in production**. Set environment variables directly:

```bash
# Example: systemd service file
[Service]
Environment="FLASK_SECRET_KEY=your-production-key"
Environment="GEMINI_API_KEY=your-api-key"
Environment="LOG_LEVEL=ERROR"
```

### API Keys

- **Gemini API**: Required for OCR meter reading
  - Get from: https://ai.google.dev/
  - Rotate regularly
  - Monitor usage for anomalies

### Secret Key Requirements

- **Minimum length**: 32 bytes (64 hex characters)
- **Generation**: Use cryptographically secure random
- **Rotation**: Change quarterly or after any security incident
- **Storage**: Environment variables only, never in code or config files

### Access Control

Currently, the application has **NO authentication**. Recommended for production:

1. Implement API key authentication
2. Add rate limiting
3. Use HTTPS/TLS only
4. Implement IP whitelisting for admin endpoints

### Data Security

- Database contains sensor readings (non-sensitive)
- OCR images are **NOT stored** (privacy-preserving)
- Log files may contain sensor data - rotate and secure them

### Network Security

- Default port: 5000 (development)
- Production: Use reverse proxy (nginx/Apache)
- Enable CORS only for trusted domains
- Use HTTPS in production

### Monitoring

Watch for:
- Unusual API usage patterns
- Failed authentication attempts (when implemented)
- Database size anomalies
- Excessive error rates

### Incident Response

If credentials are compromised:

1. **Immediately rotate** all affected keys
2. Review logs for unauthorized access
3. Update `.gitignore` if secrets were committed
4. Use `git filter-branch` or BFG to remove secrets from history

### Security Checklist

- [ ] Flask secret key set via environment variable
- [ ] Gemini API key set via environment variable
- [ ] .env file NOT committed to git
- [ ] Production uses environment variables (not .env)
- [ ] HTTPS enabled in production
- [ ] Logs secured and rotated
- [ ] Dependencies regularly updated
- [ ] Database backups configured
- [ ] Monitoring/alerting configured

### Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email: [your-security-email]
3. Include: description, steps to reproduce, potential impact

---

*Last Updated: 2025-10-02*
