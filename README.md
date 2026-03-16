# 上海两店多渠道客资接入与微信承接中台系统

## 项目概览

**系统定位**：以上海两店为核心的多渠道、多账号、多机器人协同的微信承接中台系统，同时集成了经营管理模块（订单、派工、回访、绩效等）。

### 系统架构

```
【渠道账号层】
抖音-BOP → Bot-DY-BOP
抖音-龙膜 → Bot-DY-LM
小红书-BOP → Bot-XHS-BOP
小红书-龙膜 → Bot-XHS-LM
          ↓
【OpenClaw智能层】
- 真人化聊天、意图识别、提取、推进
          ↓
【业务中台】(FastAPI 统一后端)
- 线索主表、门店轮转、SLA时效、统计报表
- 经营系统：订单、派工、回访、绩效、财务同步
          ↓
【企业微信执行层】
- BOP店群、龙膜店群、通知推送、状态回写
          ↓
【经营分析层】
- 两店加微信效率、首响率、销售效率、微信成功率
```

## 项目结构

```
.
├── docs/                        # 项目文档与规范
│   ├── 01-架构设计.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPEC.md
│   ├── PHASE1_REQUIREMENTS.md
│   └── specs/
│
├── backend/                     # Python FastAPI 统一后端
│   ├── app/
│   │   ├── main.py             # 应用入口
│   │   ├── config.py           # 配置管理
│   │   ├── models/             # ORM 模型 (SQLAlchemy)
│   │   ├── api/                # API 路由
│   │   │   ├── leads.py        # 线索管理
│   │   │   ├── stats.py        # 统计报表
│   │   │   ├── chat.py         # 智能对话
│   │   │   ├── auth.py         # 认证
│   │   │   ├── audit.py        # 操作审计
│   │   │   └── store.py        # 经营系统 (21 端点)
│   │   ├── services/           # 业务逻辑层
│   │   │   └── store_service.py  # 经营系统核心逻辑
│   │   ├── db/                 # 数据库初始化
│   │   ├── utils/              # 工具函数
│   │   └── integrations/       # 外部集成
│   ├── migrations/             # Alembic 迁移目录
│   ├── tests/                  # Pytest 测试
│   ├── requirements.txt
│   └── .env.example
│
├── admin/                      # Vue 3 Admin 管理后台
│   ├── src/
│   │   ├── pages/              # 页面
│   │   ├── router/             # 路由
│   │   ├── stores/             # Pinia 状态管理
│   │   └── utils/              # 工具函数
│   └── package.json

├── store-console/              # 门店控制台静态页面
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── miniprogram/                # 微信小程序（统一入口）
│   ├── pages/                  # 主包页面 (5 个)
│   │   ├── login.*             # 登录
│   │   ├── index.*             # 首页
│   │   ├── leads.*             # 线索列表
│   │   ├── lead-detail.*       # 线索详情
│   │   └── profile.*           # 个人中心
│   ├── subpackages/store/      # 经营子包 (14 个页面)
│   │   └── pages/
│   │       ├── ops-home/       # 经营首页
│   │       ├── order-list/     # 订单列表
│   │       ├── order-detail/   # 订单详情
│   │       ├── order-edit/     # 订单编辑
│   │       ├── order-audit/    # 操作审计
│   │       ├── film-order/     # 贴膜下单
│   │       ├── wash-order/     # 洗车下单
│   │       ├── wash-order-detail/ # 洗车详情
│   │       ├── dispatch-board/ # 贴膜派工看板
│   │       ├── wash-dispatch-board/ # 洗车派工看板
│   │       ├── sales-performance/   # 销售绩效
│   │       ├── followup-reminder/   # 回访提醒
│   │       ├── douyin-leads/   # 抖音线索
│   │       └── product-config/ # 产品配置
│   ├── utils/                  # 工具函数 & 适配层
│   ├── config/                 # 小程序配置
│   └── app.json
│
├── scripts/                    # 运维/迁移脚本
│   ├── migrate_slim_to_lx_center.py  # 数据迁移
│   ├── HEALTH_CHECK.sh
│   ├── BACKUP_DATABASE.sh
│   └── smoke_api.sh

├── .github/workflows/          # CI 流水线
│   └── ci.yml
│
└── .gitignore
```

## 快速开始

### 1. 后端启动

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

- 服务: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 2. Admin 前端启动

```bash
cd admin
npm install
npm run dev
```

- 访问: http://localhost:5173

### 3. 小程序

使用微信开发者工具打开 `miniprogram/` 目录。

## 经营系统 API 端点 (21 个)

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/store/login` | POST | 登录 |
| `/api/v1/store/me` | GET | 当前用户 |
| `/api/v1/store/logout` | POST | 登出 |
| `/api/v1/store/orders` | GET | 订单列表 |
| `/api/v1/store/orders/{id}` | PATCH | 更新订单 |
| `/api/v1/store/orders/import` | POST | 批量导入 |
| `/api/v1/store/leads` | GET | 线索列表 |
| `/api/v1/store/leads/followup-due` | GET | 待跟进线索 |
| `/api/v1/store/leads/update-status` | POST | 更新线索状态 |
| `/api/v1/store/dispatch` | GET | 派工看板 |
| `/api/v1/store/followups` | GET | 回访列表 |
| `/api/v1/store/followups/mark-done` | POST | 标记回访完成 |
| `/api/v1/store/finance/sync-logs` | GET | 财务日志 |
| `/api/v1/store/password/change` | POST | 修改密码 |
| `/api/v1/store/users/reset-password` | POST | 重置密码 |
| `/api/v1/store/health/db` | GET | DB 健康检查 |
| `/api/v1/store/internal/orders` | GET | 内部订单查询 |
| `/api/v1/store/internal/orders/sync` | POST | 订单增量同步 |
| `/api/v1/store/internal/work-orders/sync` | POST | 工单财务同步 |
| `/api/v1/store/internal/leads/push` | POST | 线索推送 |

## 关键业务规则

### 账号与门店硬绑定
- BOP 账号 → BOP 店 (不可穿插)
- 龙膜账号 → 龙膜店 (不可穿插)

### 两店独立轮转
- BOP 店: 3 名销售独立轮转
- 龙膜店: 2 名销售独立轮转

### 1/3/10 分钟 SLA 规则
- **1 分钟**：首响（销售第一次回复）
- **3 分钟**：发起加微信动作
- **10 分钟**：确认加微信结果

## 数据库

PostgreSQL 配置请以 `backend/.env.example` 为准（支持 `DATABASE_URL` 或 `DB_*`）。

```bash
cd backend
docker-compose up -d
```

## 数据迁移

从旧系统 (slim) 迁移数据到新系统 (lx_center)：

```bash
# 先试跑
python3 scripts/migrate_slim_to_lx_center.py --dry-run

# 正式迁移
python3 scripts/migrate_slim_to_lx_center.py
```

## 部署与发布

当前建议以 `backend/README.md` 的环境配置与启动方式为准，结合 `docs/specs/05-release/README.md` 的发布规范执行。
