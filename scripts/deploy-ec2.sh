#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Deployment script for EC2
# Run this on your EC2 instance after uploading the project

set -e  # Exit on error

echo "🚀 Starting Campaign Optimization Agent deployment..."

# Update system
echo "📦 Updating system packages..."
sudo yum update -y || sudo apt update -y

# Install Node.js 18
echo "📦 Installing Node.js 18..."
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 18
nvm use 18

# Install PM2
echo "📦 Installing PM2..."
npm install -g pm2

# Install Nginx
echo "📦 Installing Nginx..."
sudo yum install nginx -y 2>/dev/null || sudo apt install nginx -y

# Build backend
echo "🏗️ Building backend..."
cd ~/campaign-optimization/api-server
npm install
npm run build

# Build frontend
echo "🏗️ Building frontend..."
cd ~/campaign-optimization/ui
npm install
npm run build

# Start backend with PM2
echo "🚀 Starting backend API..."
cd ~/campaign-optimization/api-server
pm2 stop api-server 2>/dev/null || true
pm2 start dist/server.js --name api-server
pm2 save
pm2 startup

# Configure Nginx
echo "⚙️ Configuring Nginx..."
sudo tee /etc/nginx/conf.d/campaign-opt.conf > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    # Frontend (React)
    location / {
        root $HOME/campaign-optimization/ui/dist;
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
EOF

# Test Nginx config
echo "✅ Testing Nginx configuration..."
sudo nginx -t

# Restart Nginx
echo "🔄 Restarting Nginx..."
sudo systemctl restart nginx
sudo systemctl enable nginx

# Get public IP
# Use IMDSv2 with session token
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Application URLs:"
echo "   Frontend: http://$PUBLIC_IP"
echo "   API Health: http://$PUBLIC_IP/health"
echo ""
echo "🔍 Useful commands:"
echo "   pm2 status              # Check backend status"
echo "   pm2 logs api-server     # View backend logs"
echo "   sudo systemctl status nginx  # Check Nginx status"
echo "   sudo tail -f /var/log/nginx/access.log  # View access logs"
echo ""
