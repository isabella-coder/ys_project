#!/bin/bash
# 一键配置 HTTPS (Let's Encrypt) for weilantiemo.cn
# 用法：SSH 登录服务器后运行
#   sudo bash setup_https.sh

set -e

DOMAIN="weilantiemo.cn"
EMAIL="admin@${DOMAIN}"

echo "=== 1/4 安装 certbot ==="
if ! command -v certbot &>/dev/null; then
    apt-get update -qq
    apt-get install -y certbot python3-certbot-nginx
    echo "✓ certbot 已安装"
else
    echo "✓ certbot 已存在"
fi

echo ""
echo "=== 2/4 更新 Nginx 配置 ==="
# 确保 server_name 设置为域名（certbot 需要匹配）
NGINX_CONF="/etc/nginx/sites-enabled/default"
if [ ! -f "$NGINX_CONF" ]; then
    NGINX_CONF="/etc/nginx/conf.d/default.conf"
fi

# 备份
cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%Y%m%d%H%M%S)"

# 将 server_name _; 替换为域名
sed -i "s/server_name _;/server_name ${DOMAIN};/" "$NGINX_CONF"
echo "✓ server_name 已设为 ${DOMAIN}"

# 测试 Nginx 配置
nginx -t
echo "✓ Nginx 配置测试通过"
systemctl reload nginx

echo ""
echo "=== 3/4 申请 SSL 证书 ==="
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --redirect
echo "✓ SSL 证书已申请并配置"

echo ""
echo "=== 4/4 验证 ==="
# 测试自动续期
certbot renew --dry-run
echo "✓ 自动续期测试通过"

echo ""
echo "============================"
echo "✅ HTTPS 配置完成！"
echo "   https://${DOMAIN}"
echo "   证书将自动续期"
echo "============================"
