import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import enCommon from './locales/en-US/common.json'
import enCustomer from './locales/en-US/customer.json'
import enDeliveryOrder from './locales/en-US/delivery_order.json'
import enEinvoice from './locales/en-US/einvoice.json'
import enGoodsReceipt from './locales/en-US/goods_receipt.json'
import enMenu from './locales/en-US/menu.json'
import enOcr from './locales/en-US/ocr.json'
import enPurchaseOrder from './locales/en-US/purchase_order.json'
import enSalesOrder from './locales/en-US/sales_order.json'
import enStockAdjustment from './locales/en-US/stock_adjustment.json'
import enStockMovement from './locales/en-US/stock_movement.json'
import enStockTransfer from './locales/en-US/stock_transfer.json'
import enSupplier from './locales/en-US/supplier.json'
import enWarehouse from './locales/en-US/warehouse.json'
import zhCommon from './locales/zh-CN/common.json'
import zhCustomer from './locales/zh-CN/customer.json'
import zhDeliveryOrder from './locales/zh-CN/delivery_order.json'
import zhEinvoice from './locales/zh-CN/einvoice.json'
import zhGoodsReceipt from './locales/zh-CN/goods_receipt.json'
import zhMenu from './locales/zh-CN/menu.json'
import zhOcr from './locales/zh-CN/ocr.json'
import zhPurchaseOrder from './locales/zh-CN/purchase_order.json'
import zhSalesOrder from './locales/zh-CN/sales_order.json'
import zhStockAdjustment from './locales/zh-CN/stock_adjustment.json'
import zhStockMovement from './locales/zh-CN/stock_movement.json'
import zhStockTransfer from './locales/zh-CN/stock_transfer.json'
import zhSupplier from './locales/zh-CN/supplier.json'
import zhWarehouse from './locales/zh-CN/warehouse.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'en-US': {
        common: enCommon,
        menu: enMenu,
        supplier: enSupplier,
        customer: enCustomer,
        warehouse: enWarehouse,
        purchase_order: enPurchaseOrder,
        goods_receipt: enGoodsReceipt,
        sales_order: enSalesOrder,
        delivery_order: enDeliveryOrder,
        ocr: enOcr,
        einvoice: enEinvoice,
        stock_transfer: enStockTransfer,
        stock_adjustment: enStockAdjustment,
        stock_movement: enStockMovement,
      },
      'zh-CN': {
        common: zhCommon,
        menu: zhMenu,
        supplier: zhSupplier,
        customer: zhCustomer,
        warehouse: zhWarehouse,
        purchase_order: zhPurchaseOrder,
        goods_receipt: zhGoodsReceipt,
        sales_order: zhSalesOrder,
        delivery_order: zhDeliveryOrder,
        ocr: zhOcr,
        einvoice: zhEinvoice,
        stock_transfer: zhStockTransfer,
        stock_adjustment: zhStockAdjustment,
        stock_movement: zhStockMovement,
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
