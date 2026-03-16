-- 销售表新增 wx_openid 字段（微信小程序订阅消息推送用）
ALTER TABLE sales ADD COLUMN IF NOT EXISTS wx_openid VARCHAR(100);
COMMENT ON COLUMN sales.wx_openid IS '微信小程序 openid，用于订阅消息推送';
