# Environment Variables Configuration

## LocalRecall Repository Environment Variables

This document outlines the environment variables needed for the LocalRecall desktop application and its integration with the web frontend.

## GitHub Repository Secrets

### Required for Release Automation

**GITHUB_TOKEN**
- **Purpose**: Automatically provided by GitHub Actions
- **Usage**: Creating GitHub releases and uploading DMG files
- **Setup**: No manual configuration needed
- **Scope**: Read/write access to repository releases

### Required for Web Frontend Integration

**VERCEL_DEPLOY_HOOK_WEBSITE**
- **Purpose**: Trigger local-recall-front-web deployment when new release is created
- **Usage**: POST webhook to notify website of new LocalRecall releases
- **Setup**: Get from Vercel project settings → Git → Deploy Hooks
- **Format**: `https://api.vercel.com/v1/integrations/deploy/[unique-id]`
- **Example**: `https://api.vercel.com/v1/integrations/deploy/prj_abc123/xyz789`

### Optional for Notifications

**DISCORD_WEBHOOK_URL**
- **Purpose**: Send release notifications to Discord channel
- **Usage**: Notify team when new LocalRecall release is published
- **Setup**: Discord Server Settings → Integrations → Webhooks → Create Webhook
- **Format**: `https://discord.com/api/webhooks/[id]/[token]`

## Setting Up GitHub Secrets

### 1. Navigate to Repository Settings
```
GitHub → gitKnowsMe/LcallRecall → Settings → Secrets and variables → Actions
```

### 2. Add Required Secrets
Click "New repository secret" and add:

```bash
# Required for web integration
Name: VERCEL_DEPLOY_HOOK_WEBSITE
Value: https://api.vercel.com/v1/integrations/deploy/[your-project-id]/[your-hook-id]

# Optional for notifications
Name: DISCORD_WEBHOOK_URL
Value: https://discord.com/api/webhooks/[your-webhook-id]/[your-webhook-token]
```

## Getting Vercel Deploy Hook

### Step 1: Access Vercel Project
1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Select your `local-recall-front-web` project
3. Navigate to **Settings** tab

### Step 2: Create Deploy Hook
1. Go to **Git** section in left sidebar
2. Scroll to **Deploy Hooks** section
3. Click **Create Hook**
4. Configure:
   - **Hook Name**: `LocalRecall Release`
   - **Git Branch**: `main`
   - **Description**: `Triggered by LocalRecall releases`
5. Copy the generated URL

### Step 3: Add to GitHub Secrets
Use the copied URL as the value for `VERCEL_DEPLOY_HOOK_WEBSITE` secret.

## Environment Variables in Development

### Local Development (.env.local)
```bash
# Not needed for local development
# All integration happens through GitHub Actions
```

### Production Environment
```bash
# Automatically set by GitHub Actions
GITHUB_TOKEN=${GITHUB_TOKEN}
VERCEL_DEPLOY_HOOK_WEBSITE=${VERCEL_DEPLOY_HOOK_WEBSITE}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
```

## Integration Flow

### Release Process Environment Usage
1. **Developer triggers release**: `./scripts/release-production.sh patch`
2. **GitHub Actions uses GITHUB_TOKEN**: Create release and upload DMG
3. **GitHub Actions uses VERCEL_DEPLOY_HOOK_WEBSITE**: Notify web frontend
4. **GitHub Actions uses DISCORD_WEBHOOK_URL**: Send team notification

### Webhook Payload Structure
```json
{
  "trigger": "localrecall_release",
  "version": "v1.0.1",
  "download_url": "https://github.com/gitKnowsMe/LcallRecall/releases/download/v1.0.1/LocalRecall-1.0.1-arm64.dmg",
  "release_url": "https://github.com/gitKnowsMe/LcallRecall/releases/tag/v1.0.1",
  "timestamp": "2025-09-16T20:30:00Z"
}
```

## Security Considerations

### Secret Management
- **Never commit secrets** to repository
- **Use GitHub Secrets** for sensitive environment variables
- **Rotate webhooks** if compromised
- **Monitor webhook usage** in Vercel dashboard

### Webhook Security
- Vercel deploy hooks are **secured by unique URLs**
- No additional authentication required for deploy hooks
- Webhook endpoints log activities for monitoring

## Troubleshooting

### Common Issues

**"Vercel deploy hook not configured" Warning**
- Solution: Add `VERCEL_DEPLOY_HOOK_WEBSITE` to GitHub repository secrets

**Webhook Not Triggering Deployment**
- Check: Vercel deploy hook URL is correct
- Check: GitHub secret name matches exactly: `VERCEL_DEPLOY_HOOK_WEBSITE`
- Check: Vercel project is properly connected to GitHub

**Release Notifications Not Sent**
- Check: `DISCORD_WEBHOOK_URL` secret is configured
- Check: Discord webhook URL is valid and active
- Check: GitHub Actions logs for curl errors

### Testing Environment Variables

**Test Deploy Hook (Local)**
```bash
# Replace with your actual deploy hook URL
curl -X POST "https://api.vercel.com/v1/integrations/deploy/[your-id]" \
  -H "Content-Type: application/json" \
  -d '{"trigger":"test"}'
```

**Check GitHub Actions Logs**
1. Go to repository → Actions tab
2. Click on latest release workflow run
3. Check "Trigger Website Deployment" step logs

## Related Documentation

- **Web Frontend Setup**: See `local-recall-front-web/LOCALRECALL_INTEGRATION.md`
- **Release Process**: See `scripts/release-production.sh`
- **GitHub Actions**: See `.github/workflows/release.yml`

---

**Last Updated**: September 16, 2025
**Integration Status**: Phase 2 - Cross-Repository Automation