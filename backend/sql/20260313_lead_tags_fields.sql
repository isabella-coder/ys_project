-- 2026-03-13: 线索表新增标签和拆分字段
-- customer_phone / customer_wechat: 拆开存储（之前只有一个 customer_contact）
-- film_brand: AI提取的贴膜品牌
-- tags: JSON 标签数组，销售可编辑

ALTER TABLE lead ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE lead ADD COLUMN IF NOT EXISTS customer_wechat VARCHAR(50);
ALTER TABLE lead ADD COLUMN IF NOT EXISTS film_brand VARCHAR(100);
ALTER TABLE lead ADD COLUMN IF NOT EXISTS tags TEXT;

-- 从 customer_contact 回填 phone / wechat
UPDATE lead SET customer_phone = customer_contact
  WHERE customer_contact IS NOT NULL
    AND customer_contact ~ '^1[3-9][0-9]{9}$'
    AND customer_phone IS NULL;

UPDATE lead SET customer_wechat = customer_contact
  WHERE customer_contact IS NOT NULL
    AND customer_contact !~ '^1[3-9][0-9]{9}$'
    AND customer_wechat IS NULL;
