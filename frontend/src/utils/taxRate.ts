/**
 * Helper for looking up a tax rate's percentage by id from the locally
 * cached `taxRateOptions` list. Used by SO/PO edit pages so the row's
 * real-time totals stay in sync when the user changes the Tax Rate
 * dropdown without re-selecting the SKU.
 *
 * Note: backend (`_load_tax_rate_map` in services/sales.py + purchase.py)
 * is the source of truth on save — this helper is purely a UX convenience.
 */
export interface TaxRateOption {
  value: number
  label: string
  rate: number
}

export function getTaxRatePercent(
  options: TaxRateOption[],
  taxRateId: number | undefined | null,
): number {
  if (taxRateId == null) return 0
  return options.find((t) => t.value === taxRateId)?.rate ?? 0
}
