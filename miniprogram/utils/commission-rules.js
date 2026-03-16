const FIXED_TECHNICIAN_COMMISSION_RULES = {
  WASH: {
    label: '洗车固定提成(8%)',
    rate: 0.08,
  },
}

function normalizeText(value) {
  return String(value || '').trim()
}

function normalizeMoneyValue(value, fallback = 0) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) {
    return fallback
  }
  return Math.round(amount * 100) / 100
}

function normalizeServiceType(value) {
  return normalizeText(value).toUpperCase()
}

function getOrderTotalPrice(order) {
  if (!order || typeof order !== 'object') {
    return 0
  }

  const summary = order.priceSummary && typeof order.priceSummary === 'object'
    ? order.priceSummary
    : {}
  const fromSummary = normalizeMoneyValue(summary.totalPrice, NaN)
  if (Number.isFinite(fromSummary) && fromSummary > 0) {
    return fromSummary
  }

  return normalizeMoneyValue(order.totalPrice, 0)
}

function calculateFixedTechnicianCommission(input = {}) {
  const serviceType = normalizeServiceType(input.serviceType)
  const rule = FIXED_TECHNICIAN_COMMISSION_RULES[serviceType]
  if (!rule) {
    return null
  }

  const totalPrice = normalizeMoneyValue(input.totalPrice, 0)
  const commissionTotal = totalPrice > 0
    ? normalizeMoneyValue(totalPrice * rule.rate, 0)
    : 0

  return {
    serviceType,
    label: rule.label,
    rate: rule.rate,
    totalPrice,
    commissionTotal,
  }
}

module.exports = {
  calculateFixedTechnicianCommission,
  getOrderTotalPrice,
}
