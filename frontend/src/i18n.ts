import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import enAuth from './locales/en-US/auth.json'
import enCommon from './locales/en-US/common.json'
import enErrors from './locales/en-US/errors.json'
import enCustomer from './locales/en-US/customer.json'
import enDashboard from './locales/en-US/dashboard.json'
import enDeliveryOrder from './locales/en-US/delivery_order.json'
import enEinvoice from './locales/en-US/einvoice.json'
import enGoodsReceipt from './locales/en-US/goods_receipt.json'
import enInventory from './locales/en-US/inventory.json'
import enNotification from './locales/en-US/notification.json'
import enMenu from './locales/en-US/menu.json'
import enOcr from './locales/en-US/ocr.json'
import enPurchaseOrder from './locales/en-US/purchase_order.json'
import enReports from './locales/en-US/reports.json'
import enSalesOrder from './locales/en-US/sales_order.json'
import enSku from './locales/en-US/sku.json'
import enStockAdjustment from './locales/en-US/stock_adjustment.json'
import enStockMovement from './locales/en-US/stock_movement.json'
import enStockTransfer from './locales/en-US/stock_transfer.json'
import enSupplier from './locales/en-US/supplier.json'
import enWarehouse from './locales/en-US/warehouse.json'
import enSettings from './locales/en-US/settings.json'
import enUsers from './locales/en-US/users.json'
import enAdmin from './locales/en-US/admin.json'
import zhAuth from './locales/zh-CN/auth.json'
import zhCommon from './locales/zh-CN/common.json'
import zhErrors from './locales/zh-CN/errors.json'
import zhCustomer from './locales/zh-CN/customer.json'
import zhDashboard from './locales/zh-CN/dashboard.json'
import zhDeliveryOrder from './locales/zh-CN/delivery_order.json'
import zhEinvoice from './locales/zh-CN/einvoice.json'
import zhGoodsReceipt from './locales/zh-CN/goods_receipt.json'
import zhInventory from './locales/zh-CN/inventory.json'
import zhNotification from './locales/zh-CN/notification.json'
import zhMenu from './locales/zh-CN/menu.json'
import zhOcr from './locales/zh-CN/ocr.json'
import zhPurchaseOrder from './locales/zh-CN/purchase_order.json'
import zhReports from './locales/zh-CN/reports.json'
import zhSalesOrder from './locales/zh-CN/sales_order.json'
import zhSku from './locales/zh-CN/sku.json'
import zhStockAdjustment from './locales/zh-CN/stock_adjustment.json'
import zhStockMovement from './locales/zh-CN/stock_movement.json'
import zhStockTransfer from './locales/zh-CN/stock_transfer.json'
import zhSupplier from './locales/zh-CN/supplier.json'
import zhWarehouse from './locales/zh-CN/warehouse.json'
import zhSettings from './locales/zh-CN/settings.json'
import zhUsers from './locales/zh-CN/users.json'
import zhAdmin from './locales/zh-CN/admin.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'en-US': {
        auth: enAuth,
        common: enCommon,
        errors: enErrors,
        menu: enMenu,
        dashboard: enDashboard,
        reports: enReports,
        supplier: enSupplier,
        customer: enCustomer,
        warehouse: enWarehouse,
        purchase_order: enPurchaseOrder,
        goods_receipt: enGoodsReceipt,
        sales_order: enSalesOrder,
        sku: enSku,
        delivery_order: enDeliveryOrder,
        ocr: enOcr,
        einvoice: enEinvoice,
        stock_transfer: enStockTransfer,
        stock_adjustment: enStockAdjustment,
        stock_movement: enStockMovement,
        inventory: enInventory,
        notification: enNotification,
        settings: enSettings,
        users: enUsers,
        admin: enAdmin,
      },
      'zh-CN': {
        auth: zhAuth,
        common: zhCommon,
        errors: zhErrors,
        menu: zhMenu,
        dashboard: zhDashboard,
        reports: zhReports,
        supplier: zhSupplier,
        customer: zhCustomer,
        warehouse: zhWarehouse,
        purchase_order: zhPurchaseOrder,
        goods_receipt: zhGoodsReceipt,
        sales_order: zhSalesOrder,
        sku: zhSku,
        delivery_order: zhDeliveryOrder,
        ocr: zhOcr,
        einvoice: zhEinvoice,
        stock_transfer: zhStockTransfer,
        stock_adjustment: zhStockAdjustment,
        stock_movement: zhStockMovement,
        inventory: zhInventory,
        notification: zhNotification,
        settings: zhSettings,
        users: zhUsers,
        admin: zhAdmin,
      },
    },
    fallbackLng: 'en-US',
    defaultNS: 'common',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'erp-lang',
    },
  })

export default i18n
