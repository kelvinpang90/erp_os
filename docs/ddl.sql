-- ============================================================================
-- ERP OS — Database DDL Draft
-- Target: MySQL 8.0 / InnoDB / utf8mb4
--
-- 遵守 CLAUDE.md 架构约定：
--   A1 金额 DECIMAL(18, 4)
--   A2 所有业务表预留 organization_id
--   A3 软删除 deleted_at
--   A4 文档号 Redis 生成 + 本表留底
--   A5 时间 UTC TIMESTAMP / 业务日期独立 DATE
--   A6 状态字段 ENUM
--   B3 乐观锁 version 字段
--   C1 订单/发票/付款多对多
--   C2 部分收货/发货独立表
--   C3 金额含税/不含税字段明确命名
--   C4 汇率快照每张单据存
--   C5 批号 / 效期 / 序列号字段预留
--   E2 外键必加索引 + (org_id, status, created_at) 复合索引
--
-- 命名约定：
--   表名：snake_case 复数
--   字段：snake_case
--   枚举值：UPPER_CASE
--   外键：<table>_id
--   索引：ix_<table>_<columns>
--   复合唯一：uq_<table>_<columns>
--
-- 阅读指南：按节阅读
--   § 1 基础设施（组织/用户/权限/仓库）
--   § 2 主数据（币种/税率/UOM/品牌/品类/MSIC）
--   § 3 SKU 与别名
--   § 4 业务伙伴（供应商/客户）
--   § 5 采购流程（PO / GoodsReceipt）
--   § 6 销售流程（SO / DeliveryOrder）
--   § 7 发票与付款（Invoice / CreditNote / Payment / Allocation）
--   § 8 库存（Stock / Movement / Transfer / Adjustment）
--   § 9 运行时支撑（DocumentSequence / Notification / AuditLog / AiCallLog / UploadedFile / LoginAttempt）
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- § 1 基础设施：组织 / 用户 / 权限 / 仓库
-- ============================================================================

-- 1.1 organizations：单租户 Demo 只 seed 一条 id=1，但字段保留完整多租户扩展能力
CREATE TABLE `organizations` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code`                  VARCHAR(32) NOT NULL COMMENT '组织短代码，如 DEMO',
  `name`                  VARCHAR(200) NOT NULL COMMENT '组织名，如 Demo Malaysia Sdn Bhd',
  `registration_no`       VARCHAR(64) NULL COMMENT 'SSM 注册号 (Business Reg No)',
  `tin`                   VARCHAR(16) NULL COMMENT 'Tax Identification Number (TIN)',
  `sst_registration_no`   VARCHAR(32) NULL COMMENT 'SST 注册号（若有）',
  `msic_code`             VARCHAR(8) NULL COMMENT '主营业务 MSIC 行业码',
  `default_currency`      CHAR(3) NOT NULL DEFAULT 'MYR',
  `address_line1`         VARCHAR(200) NULL,
  `address_line2`         VARCHAR(200) NULL,
  `city`                  VARCHAR(80) NULL,
  `state`                 VARCHAR(80) NULL,
  `postcode`              VARCHAR(16) NULL,
  `country`               CHAR(2) NOT NULL DEFAULT 'MY',
  `phone`                 VARCHAR(32) NULL,
  `email`                 VARCHAR(120) NULL,
  `ai_master_enabled`     BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'AI 功能组织级总闸',
  `ai_features`           JSON NULL COMMENT '{"ocr_invoice":true,"einvoice_precheck":true,"dashboard_summary":true}',
  `settings`              JSON NULL COMMENT '其他组织级配置（主题、语言默认等）',
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_organizations_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.2 users
CREATE TABLE `users` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `email`                 VARCHAR(120) NOT NULL,
  `password_hash`         VARCHAR(200) NOT NULL COMMENT 'bcrypt, cost=12',
  `full_name`             VARCHAR(120) NOT NULL,
  `avatar_url`            VARCHAR(512) NULL,
  `phone`                 VARCHAR(32) NULL,
  `locale`                VARCHAR(8) NOT NULL DEFAULT 'en-US' COMMENT 'en-US | zh-CN',
  `theme`                 VARCHAR(8) NOT NULL DEFAULT 'light' COMMENT 'light | dark',
  `default_warehouse_id`  INT UNSIGNED NULL,
  `last_login_at`         TIMESTAMP NULL,
  `last_login_ip`         VARCHAR(45) NULL,
  `locked_until`          TIMESTAMP NULL COMMENT '登录失败锁定到期时间',
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_org_email` (`organization_id`, `email`),
  KEY `ix_users_org_active` (`organization_id`, `is_active`, `deleted_at`),
  CONSTRAINT `fk_users_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.3 roles
CREATE TABLE `roles` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(32) NOT NULL COMMENT 'ADMIN | MANAGER | SALES | PURCHASER',
  `name`                  VARCHAR(80) NOT NULL,
  `description`           VARCHAR(200) NULL,
  `default_home`          VARCHAR(64) NOT NULL DEFAULT '/app/dashboard',
  `is_system`             BOOLEAN NOT NULL DEFAULT FALSE COMMENT '系统内置角色不可删',
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_roles_org_code` (`organization_id`, `code`),
  CONSTRAINT `fk_roles_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.4 permissions：模块级 + 动作级
CREATE TABLE `permissions` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code`                  VARCHAR(64) NOT NULL COMMENT 'sku.view | po.create | po.cancel | po.view_cost ...',
  `module`                VARCHAR(32) NOT NULL COMMENT 'sku | po | so | invoice | ...',
  `action`                VARCHAR(32) NOT NULL COMMENT 'view | create | update | delete | cancel | view_cost',
  `description`           VARCHAR(200) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_permissions_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.5 role_permissions (M:N)
CREATE TABLE `role_permissions` (
  `role_id`               INT UNSIGNED NOT NULL,
  `permission_id`         INT UNSIGNED NOT NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`role_id`, `permission_id`),
  KEY `ix_role_permissions_perm` (`permission_id`),
  CONSTRAINT `fk_rp_role` FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rp_perm` FOREIGN KEY (`permission_id`) REFERENCES `permissions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.6 user_roles (M:N)
CREATE TABLE `user_roles` (
  `user_id`               INT UNSIGNED NOT NULL,
  `role_id`               INT UNSIGNED NOT NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `role_id`),
  KEY `ix_user_roles_role` (`role_id`),
  CONSTRAINT `fk_ur_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ur_role` FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 1.7 warehouses
CREATE TABLE `warehouses` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(32) NOT NULL COMMENT 'KL-MAIN | PG-01 | JB-01',
  `name`                  VARCHAR(120) NOT NULL,
  `type`                  ENUM('MAIN','BRANCH','TRANSIT','QUARANTINE') NOT NULL DEFAULT 'BRANCH',
  `address_line1`         VARCHAR(200) NULL,
  `address_line2`         VARCHAR(200) NULL,
  `city`                  VARCHAR(80) NULL,
  `state`                 VARCHAR(80) NULL,
  `postcode`              VARCHAR(16) NULL,
  `country`               CHAR(2) NOT NULL DEFAULT 'MY',
  `phone`                 VARCHAR(32) NULL,
  `manager_user_id`       INT UNSIGNED NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_warehouses_org_code` (`organization_id`, `code`),
  KEY `ix_warehouses_org_active` (`organization_id`, `is_active`, `deleted_at`),
  CONSTRAINT `fk_warehouses_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_warehouses_manager` FOREIGN KEY (`manager_user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 2 主数据：币种 / 汇率 / 税率 / UOM / 品牌 / 品类 / MSIC
-- ============================================================================

-- 2.1 currencies
CREATE TABLE `currencies` (
  `code`                  CHAR(3) NOT NULL COMMENT 'ISO 4217: MYR | USD | SGD | CNY',
  `name`                  VARCHAR(64) NOT NULL,
  `symbol`                VARCHAR(8) NOT NULL,
  `decimal_places`        TINYINT UNSIGNED NOT NULL DEFAULT 2,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.2 exchange_rates：Admin 手动维护；每张单据创建时 snapshot 到 C4 字段
CREATE TABLE `exchange_rates` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `from_currency`         CHAR(3) NOT NULL,
  `to_currency`           CHAR(3) NOT NULL COMMENT '通常等于 org.default_currency',
  `rate`                  DECIMAL(18, 8) NOT NULL COMMENT '1 from = rate * to',
  `effective_from`        DATE NOT NULL,
  `effective_to`          DATE NULL COMMENT 'NULL = 当前有效',
  `source`                VARCHAR(32) NOT NULL DEFAULT 'MANUAL' COMMENT 'MANUAL | BNM | OANDA',
  `created_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_exchange_rates_lookup` (`organization_id`, `from_currency`, `to_currency`, `effective_from`),
  CONSTRAINT `fk_exchange_rates_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_exchange_rates_from` FOREIGN KEY (`from_currency`) REFERENCES `currencies`(`code`),
  CONSTRAINT `fk_exchange_rates_to` FOREIGN KEY (`to_currency`) REFERENCES `currencies`(`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.3 tax_rates：马来 SST 三档
CREATE TABLE `tax_rates` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(16) NOT NULL COMMENT 'SST-10 | SST-6 | EXEMPT',
  `name`                  VARCHAR(80) NOT NULL,
  `rate`                  DECIMAL(5, 2) NOT NULL COMMENT '百分比，如 10.00 / 6.00 / 0.00',
  `tax_type`              ENUM('SALES_TAX','SERVICE_TAX','EXEMPT') NOT NULL,
  `is_default`            BOOLEAN NOT NULL DEFAULT FALSE,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tax_rates_org_code` (`organization_id`, `code`),
  CONSTRAINT `fk_tax_rates_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.4 uoms：Unit of Measure
CREATE TABLE `uoms` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(16) NOT NULL COMMENT 'PCS | BOX | KG | L | PKT',
  `name`                  VARCHAR(64) NOT NULL,
  `name_zh`               VARCHAR(64) NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_uoms_org_code` (`organization_id`, `code`),
  CONSTRAINT `fk_uoms_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.5 brands
CREATE TABLE `brands` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(32) NOT NULL,
  `name`                  VARCHAR(120) NOT NULL,
  `logo_url`              VARCHAR(512) NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_brands_org_code` (`organization_id`, `code`),
  CONSTRAINT `fk_brands_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.6 categories：树形结构，parent_id 自引用
CREATE TABLE `categories` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `parent_id`             INT UNSIGNED NULL,
  `code`                  VARCHAR(32) NOT NULL,
  `name`                  VARCHAR(120) NOT NULL,
  `name_zh`               VARCHAR(120) NULL,
  `path`                  VARCHAR(512) NULL COMMENT '冗余路径：Food/Snacks/Chips，便于搜索',
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_categories_org_code` (`organization_id`, `code`),
  KEY `ix_categories_parent` (`parent_id`),
  CONSTRAINT `fk_categories_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_categories_parent` FOREIGN KEY (`parent_id`) REFERENCES `categories`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2.7 msic_codes：MSIC 2008 马来西亚行业分类码（系统级，non-org）
CREATE TABLE `msic_codes` (
  `code`                  VARCHAR(8) NOT NULL COMMENT '5 位数 MSIC code',
  `name`                  VARCHAR(200) NOT NULL,
  `description`           VARCHAR(500) NULL,
  `category`              VARCHAR(80) NULL,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 3 SKU 与别名
-- ============================================================================

-- 3.1 skus
CREATE TABLE `skus` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(64) NOT NULL COMMENT '内部 SKU code',
  `barcode`               VARCHAR(64) NULL COMMENT 'EAN-13 / UPC',
  `name`                  VARCHAR(200) NOT NULL COMMENT '主名（英文）',
  `name_zh`               VARCHAR(200) NULL,
  `description`           TEXT NULL,
  `brand_id`              INT UNSIGNED NULL,
  `category_id`           INT UNSIGNED NULL,
  `base_uom_id`           INT UNSIGNED NOT NULL COMMENT '基础计量单位',
  `tax_rate_id`           INT UNSIGNED NOT NULL COMMENT 'SST 档位',
  `msic_code`             VARCHAR(8) NULL COMMENT 'e-Invoice 要求',
  -- 价格（含税 / 不含税分别存，C3）
  `unit_price_excl_tax`   DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '单价（不含税）',
  `unit_price_incl_tax`   DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '单价（含税），冗余便于展示',
  `price_tax_inclusive`   BOOLEAN NOT NULL DEFAULT FALSE COMMENT '录入时是含税价还是不含税价',
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  -- 成本
  `costing_method`        ENUM('WEIGHTED_AVERAGE','FIFO','SPECIFIC') NOT NULL DEFAULT 'WEIGHTED_AVERAGE',
  `last_cost`             DECIMAL(18, 4) NULL COMMENT '最近一次入库成本（便于显示）',
  -- 库存控制
  `safety_stock`          DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '安全库存（预警阈值）',
  `reorder_point`         DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '补货点',
  `reorder_qty`           DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '建议补货量',
  -- 批次 / 效期 / 序列号预留（C5）
  `track_batch`           BOOLEAN NOT NULL DEFAULT FALSE,
  `track_expiry`          BOOLEAN NOT NULL DEFAULT FALSE,
  `track_serial`          BOOLEAN NOT NULL DEFAULT FALSE,
  `shelf_life_days`       INT UNSIGNED NULL COMMENT '保质期天数',
  -- 其他
  `image_url`             VARCHAR(512) NULL,
  `weight_kg`             DECIMAL(12, 4) NULL,
  `aliases`               JSON NULL COMMENT '多语言别名 {"ms":"...","zh":"..."}',
  `metadata`              JSON NULL COMMENT '行业化扩展字段预留',
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '乐观锁',
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_skus_org_code` (`organization_id`, `code`),
  KEY `ix_skus_org_active` (`organization_id`, `is_active`, `deleted_at`),
  KEY `ix_skus_org_brand` (`organization_id`, `brand_id`),
  KEY `ix_skus_org_category` (`organization_id`, `category_id`),
  KEY `ix_skus_barcode` (`barcode`),
  CONSTRAINT `fk_skus_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_skus_brand` FOREIGN KEY (`brand_id`) REFERENCES `brands`(`id`),
  CONSTRAINT `fk_skus_category` FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`),
  CONSTRAINT `fk_skus_uom` FOREIGN KEY (`base_uom_id`) REFERENCES `uoms`(`id`),
  CONSTRAINT `fk_skus_tax` FOREIGN KEY (`tax_rate_id`) REFERENCES `tax_rates`(`id`),
  CONSTRAINT `fk_skus_msic` FOREIGN KEY (`msic_code`) REFERENCES `msic_codes`(`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 4 业务伙伴：供应商 / 客户
-- ============================================================================

-- 4.1 suppliers
CREATE TABLE `suppliers` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(32) NOT NULL,
  `name`                  VARCHAR(200) NOT NULL COMMENT '如 Tan Chong Trading Sdn Bhd',
  `name_zh`               VARCHAR(200) NULL,
  `registration_no`       VARCHAR(64) NULL,
  `tin`                   VARCHAR(16) NULL,
  `sst_registration_no`   VARCHAR(32) NULL,
  `msic_code`             VARCHAR(8) NULL,
  `contact_person`        VARCHAR(120) NULL,
  `email`                 VARCHAR(120) NULL,
  `phone`                 VARCHAR(32) NULL,
  `address_line1`         VARCHAR(200) NULL,
  `address_line2`         VARCHAR(200) NULL,
  `city`                  VARCHAR(80) NULL,
  `state`                 VARCHAR(80) NULL,
  `postcode`              VARCHAR(16) NULL,
  `country`               CHAR(2) NOT NULL DEFAULT 'MY',
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `payment_terms_days`    INT NOT NULL DEFAULT 30 COMMENT '付款账期天数',
  `credit_limit`          DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `notes`                 TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_suppliers_org_code` (`organization_id`, `code`),
  KEY `ix_suppliers_org_active` (`organization_id`, `is_active`, `deleted_at`),
  CONSTRAINT `fk_suppliers_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 4.2 customers
CREATE TABLE `customers` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `code`                  VARCHAR(32) NOT NULL,
  `name`                  VARCHAR(200) NOT NULL,
  `name_zh`               VARCHAR(200) NULL,
  `customer_type`         ENUM('B2B','B2C') NOT NULL DEFAULT 'B2B',
  `registration_no`       VARCHAR(64) NULL,
  `tin`                   VARCHAR(16) NULL COMMENT 'B2C 个人 TIN 或 NRIC（e-Invoice 必填）',
  `sst_registration_no`   VARCHAR(32) NULL,
  `msic_code`             VARCHAR(8) NULL,
  `contact_person`        VARCHAR(120) NULL,
  `email`                 VARCHAR(120) NULL,
  `phone`                 VARCHAR(32) NULL,
  `address_line1`         VARCHAR(200) NULL,
  `address_line2`         VARCHAR(200) NULL,
  `city`                  VARCHAR(80) NULL,
  `state`                 VARCHAR(80) NULL,
  `postcode`              VARCHAR(16) NULL,
  `country`               CHAR(2) NOT NULL DEFAULT 'MY',
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `payment_terms_days`    INT NOT NULL DEFAULT 30,
  `credit_limit`          DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `notes`                 TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_customers_org_code` (`organization_id`, `code`),
  KEY `ix_customers_org_active` (`organization_id`, `is_active`, `deleted_at`),
  KEY `ix_customers_org_type` (`organization_id`, `customer_type`),
  CONSTRAINT `fk_customers_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 5 采购流程：PO / GoodsReceipt
-- ============================================================================

-- 5.1 purchase_orders
CREATE TABLE `purchase_orders` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'PO-2026-00042',
  `status`                ENUM('DRAFT','CONFIRMED','PARTIAL_RECEIVED','FULLY_RECEIVED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `supplier_id`           INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL COMMENT '收货目的仓',
  `business_date`         DATE NOT NULL COMMENT '业务日期（下单日）',
  `expected_date`         DATE NULL COMMENT '预计到货日',
  -- 金额（多币种 C4）
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `exchange_rate`         DECIMAL(18, 8) NOT NULL DEFAULT 1 COMMENT 'snapshot on create',
  `subtotal_excl_tax`     DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `shipping_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `total_incl_tax`        DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `base_currency_amount`  DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT 'total_incl_tax × exchange_rate',
  -- 其他
  `payment_terms_days`    INT NOT NULL DEFAULT 30,
  `remarks`               TEXT NULL,
  `cancel_reason`         VARCHAR(500) NULL,
  `confirmed_at`          TIMESTAMP NULL,
  `cancelled_at`          TIMESTAMP NULL,
  -- OCR 来源标记
  `source`                ENUM('MANUAL','OCR','IMPORT','API') NOT NULL DEFAULT 'MANUAL',
  `source_file_id`        INT UNSIGNED NULL COMMENT '来自 OCR 时的原始文件',
  -- 元数据
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_po_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_po_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_po_supplier` (`supplier_id`),
  KEY `ix_po_warehouse` (`warehouse_id`),
  CONSTRAINT `fk_po_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_po_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers`(`id`),
  CONSTRAINT `fk_po_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 5.2 purchase_order_lines
CREATE TABLE `purchase_order_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `purchase_order_id`     INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `description`           VARCHAR(500) NULL COMMENT '覆盖 SKU 名（可自定义）',
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_ordered`           DECIMAL(18, 4) NOT NULL,
  `qty_received`          DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '累计已收，由 GoodsReceipt 回写',
  `unit_price_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `tax_rate_id`           INT UNSIGNED NOT NULL,
  `tax_rate_percent`      DECIMAL(5, 2) NOT NULL COMMENT 'snapshot，防税率变动',
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_percent`      DECIMAL(5, 2) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `line_total_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `line_total_incl_tax`   DECIMAL(18, 4) NOT NULL,
  -- 批次/效期字段（C5）
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pol_po_lineno` (`purchase_order_id`, `line_no`),
  KEY `ix_pol_sku` (`sku_id`),
  CONSTRAINT `fk_pol_po` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_pol_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_pol_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`),
  CONSTRAINT `fk_pol_tax` FOREIGN KEY (`tax_rate_id`) REFERENCES `tax_rates`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 5.3 goods_receipts：收货单，一张 PO 对应多张 GR（C2 部分收货）
CREATE TABLE `goods_receipts` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'GR-2026-00011',
  `purchase_order_id`     INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL,
  `receipt_date`          DATE NOT NULL,
  `delivery_note_no`      VARCHAR(64) NULL COMMENT '供应商送货单号',
  `received_by`           INT UNSIGNED NULL,
  `remarks`               TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_gr_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_gr_po` (`purchase_order_id`),
  KEY `ix_gr_org_date` (`organization_id`, `receipt_date`),
  CONSTRAINT `fk_gr_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_gr_po` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders`(`id`),
  CONSTRAINT `fk_gr_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 5.4 goods_receipt_lines
CREATE TABLE `goods_receipt_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `goods_receipt_id`      INT UNSIGNED NOT NULL,
  `purchase_order_line_id` INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_received`          DECIMAL(18, 4) NOT NULL,
  `unit_cost`             DECIMAL(18, 4) NOT NULL COMMENT '入库时单位成本（PO line price 扣折扣）',
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `remarks`               VARCHAR(500) NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_grl_gr` (`goods_receipt_id`),
  KEY `ix_grl_pol` (`purchase_order_line_id`),
  KEY `ix_grl_sku` (`sku_id`),
  CONSTRAINT `fk_grl_gr` FOREIGN KEY (`goods_receipt_id`) REFERENCES `goods_receipts`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_grl_pol` FOREIGN KEY (`purchase_order_line_id`) REFERENCES `purchase_order_lines`(`id`),
  CONSTRAINT `fk_grl_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_grl_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 6 销售流程：SO / DeliveryOrder
-- ============================================================================

-- 6.1 sales_orders
CREATE TABLE `sales_orders` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'SO-2026-00042',
  `status`                ENUM('DRAFT','CONFIRMED','PARTIAL_SHIPPED','FULLY_SHIPPED','INVOICED','PAID','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `customer_id`           INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL COMMENT '发货源仓',
  `business_date`         DATE NOT NULL,
  `expected_ship_date`    DATE NULL,
  -- 金额（多币种 C4）
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `exchange_rate`         DECIMAL(18, 8) NOT NULL DEFAULT 1,
  `subtotal_excl_tax`     DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `shipping_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `total_incl_tax`        DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `base_currency_amount`  DECIMAL(18, 4) NOT NULL DEFAULT 0,
  -- 其他
  `payment_terms_days`    INT NOT NULL DEFAULT 30,
  `shipping_address`      VARCHAR(500) NULL,
  `remarks`               TEXT NULL,
  `cancel_reason`         VARCHAR(500) NULL,
  `confirmed_at`          TIMESTAMP NULL,
  `fully_shipped_at`      TIMESTAMP NULL,
  `cancelled_at`          TIMESTAMP NULL,
  -- 元数据
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_so_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_so_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_so_customer` (`customer_id`),
  KEY `ix_so_warehouse` (`warehouse_id`),
  CONSTRAINT `fk_so_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_so_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`),
  CONSTRAINT `fk_so_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 6.2 sales_order_lines
CREATE TABLE `sales_order_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `sales_order_id`        INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `description`           VARCHAR(500) NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_ordered`           DECIMAL(18, 4) NOT NULL,
  `qty_shipped`           DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `qty_invoiced`          DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `unit_price_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `tax_rate_id`           INT UNSIGNED NOT NULL,
  `tax_rate_percent`      DECIMAL(5, 2) NOT NULL,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_percent`      DECIMAL(5, 2) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `line_total_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `line_total_incl_tax`   DECIMAL(18, 4) NOT NULL,
  -- 成本快照（C4 退货成本回填需要）
  `snapshot_avg_cost`     DECIMAL(18, 4) NULL COMMENT '发货时的 avg_cost，用于退货成本回填',
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `serial_no`             VARCHAR(128) NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sol_so_lineno` (`sales_order_id`, `line_no`),
  KEY `ix_sol_sku` (`sku_id`),
  CONSTRAINT `fk_sol_so` FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sol_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_sol_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`),
  CONSTRAINT `fk_sol_tax` FOREIGN KEY (`tax_rate_id`) REFERENCES `tax_rates`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 6.3 delivery_orders：发货单，一张 SO 对应多张 DO（C2）
CREATE TABLE `delivery_orders` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'DO-2026-00008',
  `sales_order_id`        INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL,
  `delivery_date`         DATE NOT NULL,
  `shipping_method`       VARCHAR(64) NULL COMMENT 'Pos Laju / J&T / Self-pickup',
  `tracking_no`           VARCHAR(64) NULL,
  `delivered_by`          INT UNSIGNED NULL,
  `remarks`               TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_do_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_do_so` (`sales_order_id`),
  KEY `ix_do_org_date` (`organization_id`, `delivery_date`),
  CONSTRAINT `fk_do_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_do_so` FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders`(`id`),
  CONSTRAINT `fk_do_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 6.4 delivery_order_lines
CREATE TABLE `delivery_order_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `delivery_order_id`     INT UNSIGNED NOT NULL,
  `sales_order_line_id`   INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_shipped`           DECIMAL(18, 4) NOT NULL,
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `serial_no`             VARCHAR(128) NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_dol_do` (`delivery_order_id`),
  KEY `ix_dol_sol` (`sales_order_line_id`),
  CONSTRAINT `fk_dol_do` FOREIGN KEY (`delivery_order_id`) REFERENCES `delivery_orders`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_dol_sol` FOREIGN KEY (`sales_order_line_id`) REFERENCES `sales_order_lines`(`id`),
  CONSTRAINT `fk_dol_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_dol_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 7 发票与付款：Invoice / CreditNote / Payment / Allocation
--     C1 订单↔发票↔付款多对多通过 allocation 表实现
-- ============================================================================

-- 7.1 invoices (e-Invoice)
CREATE TABLE `invoices` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'INV-2026-00101',
  `invoice_type`          ENUM('INVOICE','SELF_BILLED','CONSOLIDATED') NOT NULL DEFAULT 'INVOICE',
  `status`                ENUM('DRAFT','SUBMITTED','VALIDATED','FINAL','REJECTED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `sales_order_id`        INT UNSIGNED NULL COMMENT 'Consolidated 型为 NULL',
  `customer_id`           INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NULL,
  `business_date`         DATE NOT NULL,
  `due_date`              DATE NULL,
  -- 金额
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `exchange_rate`         DECIMAL(18, 8) NOT NULL DEFAULT 1,
  `subtotal_excl_tax`     DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `total_incl_tax`        DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `base_currency_amount`  DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `paid_amount`           DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '累计已付，由 payment_allocations 回写',
  -- LHDN MyInvois 相关
  `uin`                   VARCHAR(64) NULL COMMENT 'MyInvois Unique Identifier Number',
  `qr_code_url`           VARCHAR(512) NULL,
  `submitted_at`          TIMESTAMP NULL,
  `validated_at`          TIMESTAMP NULL COMMENT 'LHDN Validated 时间，用于 72h 计算',
  `finalized_at`          TIMESTAMP NULL COMMENT '超过 72h 观察期',
  `rejected_at`           TIMESTAMP NULL,
  `rejected_by`           ENUM('LHDN','BUYER') NULL,
  `rejection_reason`      VARCHAR(1000) NULL,
  `rejection_attachment_id` INT UNSIGNED NULL,
  -- 预校验结果
  `precheck_result`       JSON NULL COMMENT 'AI 预校验输出：{passed, hard_errors, soft_warnings}',
  `precheck_at`           TIMESTAMP NULL,
  -- 其他
  `remarks`               TEXT NULL,
  `pdf_file_id`           INT UNSIGNED NULL,
  -- 元数据
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_inv_org_document_no` (`organization_id`, `document_no`),
  UNIQUE KEY `uq_inv_uin` (`uin`),
  KEY `ix_inv_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_inv_so` (`sales_order_id`),
  KEY `ix_inv_customer` (`customer_id`),
  KEY `ix_inv_validated_at` (`status`, `validated_at`) COMMENT '72h 扫描用',
  CONSTRAINT `fk_inv_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_inv_so` FOREIGN KEY (`sales_order_id`) REFERENCES `sales_orders`(`id`),
  CONSTRAINT `fk_inv_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 7.2 invoice_lines
CREATE TABLE `invoice_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `invoice_id`            INT UNSIGNED NOT NULL,
  `sales_order_line_id`   INT UNSIGNED NULL COMMENT 'Consolidated 可为 NULL',
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `description`           VARCHAR(500) NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty`                   DECIMAL(18, 4) NOT NULL,
  `unit_price_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `tax_rate_id`           INT UNSIGNED NOT NULL,
  `tax_rate_percent`      DECIMAL(5, 2) NOT NULL,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `discount_amount`       DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `line_total_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `line_total_incl_tax`   DECIMAL(18, 4) NOT NULL,
  `msic_code`             VARCHAR(8) NULL COMMENT '发票行 MSIC',
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_invl_inv_lineno` (`invoice_id`, `line_no`),
  KEY `ix_invl_sol` (`sales_order_line_id`),
  KEY `ix_invl_sku` (`sku_id`),
  CONSTRAINT `fk_invl_inv` FOREIGN KEY (`invoice_id`) REFERENCES `invoices`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_invl_sol` FOREIGN KEY (`sales_order_line_id`) REFERENCES `sales_order_lines`(`id`),
  CONSTRAINT `fk_invl_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_invl_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`),
  CONSTRAINT `fk_invl_tax` FOREIGN KEY (`tax_rate_id`) REFERENCES `tax_rates`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 7.3 credit_notes
CREATE TABLE `credit_notes` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'CN-2026-00003',
  `status`                ENUM('DRAFT','SUBMITTED','VALIDATED','FINAL','REJECTED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `invoice_id`            INT UNSIGNED NOT NULL COMMENT '原发票',
  `customer_id`           INT UNSIGNED NOT NULL,
  `business_date`         DATE NOT NULL,
  `reason`                ENUM('RETURN','DISCOUNT_ADJUSTMENT','PRICE_CORRECTION','WRITE_OFF','OTHER') NOT NULL,
  `reason_description`    VARCHAR(500) NULL,
  -- 金额
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `exchange_rate`         DECIMAL(18, 8) NOT NULL DEFAULT 1,
  `subtotal_excl_tax`     DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `total_incl_tax`        DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `base_currency_amount`  DECIMAL(18, 4) NOT NULL DEFAULT 0,
  -- MyInvois
  `uin`                   VARCHAR(64) NULL,
  `qr_code_url`           VARCHAR(512) NULL,
  `submitted_at`          TIMESTAMP NULL,
  `validated_at`          TIMESTAMP NULL,
  `finalized_at`          TIMESTAMP NULL,
  `rejected_at`           TIMESTAMP NULL,
  `rejection_reason`      VARCHAR(1000) NULL,
  `remarks`               TEXT NULL,
  `pdf_file_id`           INT UNSIGNED NULL,
  -- 元数据
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cn_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_cn_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_cn_invoice` (`invoice_id`),
  KEY `ix_cn_customer` (`customer_id`),
  CONSTRAINT `fk_cn_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_cn_invoice` FOREIGN KEY (`invoice_id`) REFERENCES `invoices`(`id`),
  CONSTRAINT `fk_cn_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 7.4 credit_note_lines
CREATE TABLE `credit_note_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `credit_note_id`        INT UNSIGNED NOT NULL,
  `invoice_line_id`       INT UNSIGNED NOT NULL COMMENT '对应的原发票行',
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `description`           VARCHAR(500) NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty`                   DECIMAL(18, 4) NOT NULL COMMENT '退回数量',
  `unit_price_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `tax_rate_percent`      DECIMAL(5, 2) NOT NULL,
  `tax_amount`            DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `line_total_excl_tax`   DECIMAL(18, 4) NOT NULL,
  `line_total_incl_tax`   DECIMAL(18, 4) NOT NULL,
  `snapshot_avg_cost`     DECIMAL(18, 4) NULL COMMENT '从 SO line snapshot 继承，用于入库成本回填',
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cnl_cn_lineno` (`credit_note_id`, `line_no`),
  KEY `ix_cnl_invl` (`invoice_line_id`),
  CONSTRAINT `fk_cnl_cn` FOREIGN KEY (`credit_note_id`) REFERENCES `credit_notes`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cnl_invl` FOREIGN KEY (`invoice_line_id`) REFERENCES `invoice_lines`(`id`),
  CONSTRAINT `fk_cnl_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_cnl_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 7.5 payments（独立表，一笔付款可冲多张发票）
CREATE TABLE `payments` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'PAY-2026-00021',
  `direction`             ENUM('INBOUND','OUTBOUND') NOT NULL COMMENT 'INBOUND: 收客户款 | OUTBOUND: 付供应商',
  `customer_id`           INT UNSIGNED NULL,
  `supplier_id`           INT UNSIGNED NULL,
  `business_date`         DATE NOT NULL,
  `method`                ENUM('CASH','BANK_TRANSFER','FPX','DUITNOW','CREDIT_CARD','CHEQUE','OTHER') NOT NULL,
  `reference_no`          VARCHAR(64) NULL COMMENT '银行单号 / 支票号',
  `currency`              CHAR(3) NOT NULL DEFAULT 'MYR',
  `exchange_rate`         DECIMAL(18, 8) NOT NULL DEFAULT 1,
  `amount`                DECIMAL(18, 4) NOT NULL,
  `base_currency_amount`  DECIMAL(18, 4) NOT NULL,
  `allocated_amount`      DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `unallocated_amount`    DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `remarks`               TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pay_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_pay_customer` (`customer_id`),
  KEY `ix_pay_supplier` (`supplier_id`),
  KEY `ix_pay_org_date` (`organization_id`, `business_date`),
  CONSTRAINT `fk_pay_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_pay_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`),
  CONSTRAINT `fk_pay_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 7.6 payment_allocations（C1 核心：一笔 payment 可以分配给多张 invoice，一张 invoice 可接收多笔付款）
CREATE TABLE `payment_allocations` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `payment_id`            INT UNSIGNED NOT NULL,
  `invoice_id`            INT UNSIGNED NULL COMMENT 'INBOUND 冲销售发票',
  `purchase_order_id`     INT UNSIGNED NULL COMMENT 'OUTBOUND 冲采购单（简化：不单独建 bill 表）',
  `credit_note_id`        INT UNSIGNED NULL COMMENT '退款冲 CN',
  `allocated_amount`      DECIMAL(18, 4) NOT NULL,
  `allocated_at`          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by`            INT UNSIGNED NULL,
  PRIMARY KEY (`id`),
  KEY `ix_palloc_payment` (`payment_id`),
  KEY `ix_palloc_invoice` (`invoice_id`),
  KEY `ix_palloc_po` (`purchase_order_id`),
  KEY `ix_palloc_cn` (`credit_note_id`),
  CONSTRAINT `fk_palloc_payment` FOREIGN KEY (`payment_id`) REFERENCES `payments`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_palloc_invoice` FOREIGN KEY (`invoice_id`) REFERENCES `invoices`(`id`),
  CONSTRAINT `fk_palloc_po` FOREIGN KEY (`purchase_order_id`) REFERENCES `purchase_orders`(`id`),
  CONSTRAINT `fk_palloc_cn` FOREIGN KEY (`credit_note_id`) REFERENCES `credit_notes`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 8 库存：当前状态 / 流水 / 调拨 / 调整
-- ============================================================================

-- 8.1 stocks：当前 SKU × Warehouse 库存状态（6 维）
CREATE TABLE `stocks` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL,
  -- 6 维
  `on_hand`               DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '实物在库',
  `reserved`              DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '已下单锁定',
  `quality_hold`          DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '质检 / 损坏待处理',
  `available`             DECIMAL(18, 4) AS (`on_hand` - `reserved` - `quality_hold`) VIRTUAL COMMENT '可用量（计算列）',
  `incoming`              DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '已下 PO 未到货',
  `in_transit`            DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT '调拨在途',
  -- 成本（加权平均）
  `avg_cost`              DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `last_cost`             DECIMAL(18, 4) NULL,
  -- 初始值（用于 Demo reset 恢复）
  `initial_on_hand`       DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT 'Demo reset 时恢复到此值',
  `initial_avg_cost`      DECIMAL(18, 4) NOT NULL DEFAULT 0,
  -- 时间
  `last_movement_at`      TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_stocks_sku_warehouse` (`sku_id`, `warehouse_id`),
  KEY `ix_stocks_org` (`organization_id`),
  KEY `ix_stocks_warehouse` (`warehouse_id`),
  CONSTRAINT `fk_stocks_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_stocks_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_stocks_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8.2 stock_movements：所有库存变动流水（不可删除）
CREATE TABLE `stock_movements` (
  `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `warehouse_id`          INT UNSIGNED NOT NULL,
  `movement_type`         ENUM(
    'PURCHASE_IN',      -- PO 收货
    'PURCHASE_RETURN',  -- 退供应商
    'SALES_OUT',        -- SO 发货
    'SALES_RETURN',     -- 客户退货
    'TRANSFER_OUT',     -- 调拨出
    'TRANSFER_IN',      -- 调拨入
    'ADJUSTMENT_IN',    -- 盘盈
    'ADJUSTMENT_OUT',   -- 盘亏
    'RESERVE',          -- SO 确认锁定
    'UNRESERVE',        -- SO 取消释放
    'QUALITY_HOLD',     -- 质检锁
    'QUALITY_RELEASE'   -- 质检放行
  ) NOT NULL,
  `quantity`              DECIMAL(18, 4) NOT NULL COMMENT '正负表示方向',
  `unit_cost`             DECIMAL(18, 4) NULL COMMENT '变动时单位成本',
  `avg_cost_after`        DECIMAL(18, 4) NULL COMMENT '变动后 avg_cost（审计）',
  -- 来源追溯
  `source_document_type`  ENUM('PO','SO','GR','DO','CN','TRANSFER','ADJUSTMENT','OPENING','DEMO_RESET') NOT NULL,
  `source_document_id`    INT UNSIGNED NOT NULL,
  `source_line_id`        INT UNSIGNED NULL,
  -- 批次/效期/序列号
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `serial_no`             VARCHAR(128) NULL,
  -- 其他
  `notes`                 VARCHAR(500) NULL,
  `actor_user_id`         INT UNSIGNED NULL,
  `occurred_at`           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_sm_sku_warehouse` (`sku_id`, `warehouse_id`, `occurred_at`),
  KEY `ix_sm_org_type_date` (`organization_id`, `movement_type`, `occurred_at`),
  KEY `ix_sm_source` (`source_document_type`, `source_document_id`),
  CONSTRAINT `fk_sm_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_sm_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_sm_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8.3 stock_transfers：调拨单
CREATE TABLE `stock_transfers` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'TR-2026-00005',
  `status`                ENUM('DRAFT','CONFIRMED','IN_TRANSIT','RECEIVED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `from_warehouse_id`     INT UNSIGNED NOT NULL,
  `to_warehouse_id`       INT UNSIGNED NOT NULL,
  `business_date`         DATE NOT NULL,
  `expected_arrival_date` DATE NULL,
  `actual_arrival_date`   DATE NULL,
  `remarks`               TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `updated_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tr_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_tr_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_tr_from_wh` (`from_warehouse_id`),
  KEY `ix_tr_to_wh` (`to_warehouse_id`),
  CONSTRAINT `fk_tr_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_tr_from_wh` FOREIGN KEY (`from_warehouse_id`) REFERENCES `warehouses`(`id`),
  CONSTRAINT `fk_tr_to_wh` FOREIGN KEY (`to_warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8.4 stock_transfer_lines
CREATE TABLE `stock_transfer_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `stock_transfer_id`     INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_sent`              DECIMAL(18, 4) NOT NULL,
  `qty_received`          DECIMAL(18, 4) NOT NULL DEFAULT 0,
  `unit_cost_snapshot`    DECIMAL(18, 4) NULL COMMENT 'From 仓发货时 avg_cost',
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_trl_tr_lineno` (`stock_transfer_id`, `line_no`),
  KEY `ix_trl_sku` (`sku_id`),
  CONSTRAINT `fk_trl_tr` FOREIGN KEY (`stock_transfer_id`) REFERENCES `stock_transfers`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_trl_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_trl_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8.5 stock_adjustments：盘点 / 调整差异单
CREATE TABLE `stock_adjustments` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `document_no`           VARCHAR(32) NOT NULL COMMENT 'ADJ-2026-00002',
  `status`                ENUM('DRAFT','CONFIRMED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
  `warehouse_id`          INT UNSIGNED NOT NULL,
  `business_date`         DATE NOT NULL,
  `reason`                ENUM('PHYSICAL_COUNT','DAMAGE','THEFT','CORRECTION','EXPIRY','OTHER') NOT NULL,
  `reason_description`    VARCHAR(500) NULL,
  `approved_by`           INT UNSIGNED NULL,
  `approved_at`           TIMESTAMP NULL,
  `remarks`               TEXT NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `version`               INT UNSIGNED NOT NULL DEFAULT 0,
  `created_by`            INT UNSIGNED NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_adj_org_document_no` (`organization_id`, `document_no`),
  KEY `ix_adj_org_status_date` (`organization_id`, `status`, `business_date`),
  KEY `ix_adj_warehouse` (`warehouse_id`),
  CONSTRAINT `fk_adj_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_adj_warehouse` FOREIGN KEY (`warehouse_id`) REFERENCES `warehouses`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8.6 stock_adjustment_lines
CREATE TABLE `stock_adjustment_lines` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `stock_adjustment_id`   INT UNSIGNED NOT NULL,
  `line_no`               INT UNSIGNED NOT NULL,
  `sku_id`                INT UNSIGNED NOT NULL,
  `uom_id`                INT UNSIGNED NOT NULL,
  `qty_before`            DECIMAL(18, 4) NOT NULL COMMENT '调整前账面量',
  `qty_after`             DECIMAL(18, 4) NOT NULL COMMENT '调整后实际量',
  `qty_diff`              DECIMAL(18, 4) AS (`qty_after` - `qty_before`) VIRTUAL,
  `unit_cost`             DECIMAL(18, 4) NULL COMMENT '盈亏时成本记录',
  `batch_no`              VARCHAR(64) NULL,
  `expiry_date`           DATE NULL,
  `notes`                 VARCHAR(500) NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_adjl_adj_lineno` (`stock_adjustment_id`, `line_no`),
  KEY `ix_adjl_sku` (`sku_id`),
  CONSTRAINT `fk_adjl_adj` FOREIGN KEY (`stock_adjustment_id`) REFERENCES `stock_adjustments`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_adjl_sku` FOREIGN KEY (`sku_id`) REFERENCES `skus`(`id`),
  CONSTRAINT `fk_adjl_uom` FOREIGN KEY (`uom_id`) REFERENCES `uoms`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- § 9 运行时支撑：DocumentSequence / Notification / AuditLog / AiCallLog / UploadedFile / LoginAttempt / DemoResetLog
-- ============================================================================

-- 9.1 document_sequences：Redis 为主，本表做审计 / 断电恢复
CREATE TABLE `document_sequences` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `doc_type`              VARCHAR(16) NOT NULL COMMENT 'PO | SO | INV | CN | GR | DO | TR | ADJ | PAY',
  `year`                  SMALLINT UNSIGNED NOT NULL,
  `current_value`         INT UNSIGNED NOT NULL DEFAULT 0,
  `last_generated_at`     TIMESTAMP NULL,
  `updated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_docseq` (`organization_id`, `doc_type`, `year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.2 notifications
CREATE TABLE `notifications` (
  `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `type`                  ENUM(
    'LOW_STOCK',
    'APPROVAL_PENDING',
    'EINVOICE_VALIDATED',
    'EINVOICE_REJECTED',
    'EINVOICE_EXPIRING',
    'PAYMENT_RECEIVED',
    'ORDER_CANCELLED',
    'DEMO_RESET_DONE',
    'OTHER'
  ) NOT NULL,
  `title`                 VARCHAR(200) NOT NULL,
  `body`                  TEXT NULL,
  `i18n_key`              VARCHAR(128) NULL COMMENT '前端据此 i18n',
  `i18n_params`           JSON NULL,
  -- 接收者（二选一或同时）
  `target_user_id`        INT UNSIGNED NULL COMMENT '点名接收人',
  `target_role`           VARCHAR(32) NULL COMMENT '全体此角色接收',
  -- 关联资源
  `related_entity_type`   VARCHAR(32) NULL,
  `related_entity_id`     INT UNSIGNED NULL,
  `action_url`            VARCHAR(512) NULL,
  -- 状态
  `severity`              ENUM('INFO','WARNING','ERROR','CRITICAL') NOT NULL DEFAULT 'INFO',
  `is_read`               BOOLEAN NOT NULL DEFAULT FALSE,
  `read_at`               TIMESTAMP NULL,
  `expires_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_notif_user_read` (`target_user_id`, `is_read`, `created_at`),
  KEY `ix_notif_role_read` (`target_role`, `is_read`, `created_at`),
  KEY `ix_notif_org_type` (`organization_id`, `type`, `created_at`),
  CONSTRAINT `fk_notif_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`target_user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.3 audit_logs：三张核心表（orders/invoices/credit_notes）的字段级变更
CREATE TABLE `audit_logs` (
  `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `entity_type`           VARCHAR(32) NOT NULL COMMENT 'PO | SO | INVOICE | CREDIT_NOTE',
  `entity_id`             INT UNSIGNED NOT NULL,
  `action`                ENUM(
    'CREATED','UPDATED','DELETED','RESTORED',
    'STATUS_CHANGED','APPROVED','CANCELLED',
    'SUBMITTED','VALIDATED','REJECTED','FINALIZED'
  ) NOT NULL,
  `actor_user_id`         INT UNSIGNED NULL,
  `before`                JSON NULL COMMENT '变更前字段快照',
  `after`                 JSON NULL COMMENT '变更后字段快照',
  `ip`                    VARCHAR(45) NULL,
  `user_agent`            VARCHAR(500) NULL,
  `request_id`            VARCHAR(64) NULL COMMENT '与前后端 request_id 串联',
  `occurred_at`           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_audit_entity` (`entity_type`, `entity_id`, `occurred_at`),
  KEY `ix_audit_org_actor` (`organization_id`, `actor_user_id`, `occurred_at`),
  CONSTRAINT `fk_audit_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_audit_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.4 ai_call_logs：AI 调用记录（D3）
CREATE TABLE `ai_call_logs` (
  `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `user_id`               INT UNSIGNED NULL,
  `feature`               ENUM('OCR_INVOICE','EINVOICE_PRECHECK','DASHBOARD_SUMMARY','OTHER') NOT NULL,
  `provider`              VARCHAR(32) NOT NULL COMMENT 'anthropic | openai',
  `model`                 VARCHAR(64) NOT NULL,
  `endpoint`              VARCHAR(128) NULL,
  `prompt_version`        VARCHAR(16) NULL,
  `input_tokens`          INT UNSIGNED NULL,
  `output_tokens`         INT UNSIGNED NULL,
  `cost_usd`              DECIMAL(10, 6) NULL,
  `latency_ms`            INT UNSIGNED NULL,
  `status`                ENUM('SUCCESS','FAILURE','TIMEOUT','RATE_LIMITED','DISABLED') NOT NULL,
  `error_code`            VARCHAR(64) NULL,
  `request_id`            VARCHAR(64) NULL,
  `metadata`              JSON NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ailog_org_feat_date` (`organization_id`, `feature`, `created_at`),
  KEY `ix_ailog_user` (`user_id`),
  CONSTRAINT `fk_ailog_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_ailog_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.5 uploaded_files：所有上传文件元数据
CREATE TABLE `uploaded_files` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id`       INT UNSIGNED NOT NULL,
  `category`              ENUM('OCR_INVOICE','EINVOICE_PDF','AVATAR','LOGO','IMPORT_EXCEL','REJECTION_ATTACHMENT','OTHER') NOT NULL,
  `original_filename`     VARCHAR(255) NOT NULL,
  `stored_path`           VARCHAR(512) NOT NULL COMMENT '相对于 UPLOAD_DIR 的路径',
  `mime_type`             VARCHAR(128) NOT NULL,
  `size_bytes`            BIGINT UNSIGNED NOT NULL,
  `sha256`                CHAR(64) NULL,
  -- 关联
  `related_entity_type`   VARCHAR(32) NULL,
  `related_entity_id`     INT UNSIGNED NULL,
  -- 生命周期
  `expires_at`            TIMESTAMP NULL COMMENT '临时文件过期时间',
  `uploaded_by`           INT UNSIGNED NULL,
  `is_active`             BOOLEAN NOT NULL DEFAULT TRUE,
  `deleted_at`            TIMESTAMP NULL,
  `created_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_files_org_category` (`organization_id`, `category`, `created_at`),
  KEY `ix_files_related` (`related_entity_type`, `related_entity_id`),
  KEY `ix_files_expires` (`expires_at`) COMMENT '清理过期文件扫描',
  CONSTRAINT `fk_files_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations`(`id`),
  CONSTRAINT `fk_files_user` FOREIGN KEY (`uploaded_by`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.6 login_attempts：登录失败锁定 5 次锁 5 分钟
CREATE TABLE `login_attempts` (
  `id`                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email`                 VARCHAR(120) NOT NULL,
  `ip`                    VARCHAR(45) NOT NULL,
  `user_agent`            VARCHAR(500) NULL,
  `success`               BOOLEAN NOT NULL,
  `failure_reason`        VARCHAR(120) NULL,
  `attempted_at`          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_login_email_time` (`email`, `attempted_at`),
  KEY `ix_login_ip_time` (`ip`, `attempted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 9.7 demo_reset_logs：每次 Demo Reset 的执行记录（审计）
CREATE TABLE `demo_reset_logs` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `triggered_by`          ENUM('SCHEDULED','MANUAL') NOT NULL,
  `triggered_by_user_id`  INT UNSIGNED NULL,
  `started_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at`          TIMESTAMP NULL,
  `status`                ENUM('RUNNING','SUCCESS','FAILURE','ROLLED_BACK') NOT NULL DEFAULT 'RUNNING',
  `backup_path`           VARCHAR(512) NULL,
  `error_message`         TEXT NULL,
  `tables_reset`          JSON NULL COMMENT '["purchase_orders", "sales_orders", ...]',
  `records_deleted`       JSON NULL COMMENT '{"purchase_orders": 500, ...}',
  PRIMARY KEY (`id`),
  KEY `ix_demoreset_status_time` (`status`, `started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================================
-- 初始种子：权限、角色、默认组织
-- 仅给出代码骨架，实际数据由 scripts/seed_master_data.py 填充
-- ============================================================================

-- 说明：
-- 1. organizations: seed (id=1, code='DEMO', name='Demo Malaysia Sdn Bhd')
-- 2. roles: seed ADMIN / MANAGER / SALES / PURCHASER 四个
-- 3. permissions: seed 模块级 + 动作级权限（约 40 条）
-- 4. role_permissions: 按 CLAUDE.md Part 7 的角色矩阵授权
-- 5. currencies: seed MYR / USD / SGD / CNY
-- 6. tax_rates: seed SST-10 / SST-6 / EXEMPT
-- 7. uoms: seed PCS / BOX / KG / L / PKT / DOZEN / CTN
-- 8. warehouses: seed Main-KL / Branch-Penang / Branch-JB
-- 9. users: seed admin@demo.my / manager@demo.my / sales@demo.my / purchaser@demo.my (bcrypt hash)
-- 10. msic_codes: seed 常用 30-50 个码（完整 MSIC 2008 表单独导入）


SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- End of DDL
-- ============================================================================
