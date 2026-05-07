-- ─────────────────────────────────────────────────────────────────────────────
-- 共享 MySQL 首次启动初始化（仅在 mysql_data volume 为空时执行）
-- 后续新项目用 infra/scripts/provision-project.sh
-- 上线前把所有 CHANGE_ME_* 替换为强随机密码（openssl rand -hex 16）
-- ─────────────────────────────────────────────────────────────────────────────

-- ── ERP 项目 ────────────────────────────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS `erp_os`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'erp_app'@'%' IDENTIFIED BY 'CHANGE_ME_erp_app_pwd';
GRANT ALL PRIVILEGES ON `erp_os`.* TO 'erp_app'@'%';

-- ── claude_ro：MCP 只读账号（仅授权 erp_os） ──────────────────────────────
CREATE USER IF NOT EXISTS 'claude_ro'@'%' IDENTIFIED BY 'CHANGE_ME_claude_ro_pwd';
GRANT SELECT, SHOW VIEW ON `erp_os`.* TO 'claude_ro'@'%';

FLUSH PRIVILEGES;
