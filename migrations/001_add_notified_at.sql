-- 在既有的 jobhunt.jobs table（E:\Playwright/schema.sql 建立）加一個欄位，
-- 用來記錄哪些高分職缺已經推播過，避免重複通知。
-- 執行方式：psql -d jobhunt -f migrations/001_add_notified_at.sql

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS notified_at TIMESTAMP;
