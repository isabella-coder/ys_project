const { isVersionConflictError, getCurrentVersion } = require('./store-error')
const { getFinanceConfig } = require('../../config/finance.config')
const { getMiniAuthSession } = require('../mini-auth')

function getStoreApiBaseUrl() {
  const customBaseUrl = wx.getStorageSync('store_api_base_url')
  const fallbackBaseUrl = getFinanceConfig().baseUrl
  return String(customBaseUrl || fallbackBaseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '')
}

function requestStore(path, options = {}) {
  return new Promise((resolve, reject) => {
    const session = getMiniAuthSession()
    const token = String((session && session.token) || '').trim()
    if (!token) {
      reject(new Error('请先登录经营系统账号'))
      return
    }

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'X-Api-Token': token,
    }

    wx.request({
      url: `${getStoreApiBaseUrl()}${path}`,
      method: options.method || 'GET',
      header: headers,
      data: options.data || {},
      timeout: 12000,
      success: (res) => {
        const body = res && res.data ? res.data : {}
        const ok = (res.statusCode >= 200 && res.statusCode < 300) && (body.success === true || body.ok === true || body.code === 0)
        if (!ok) {
          const err = new Error(body.message || `经营系统请求失败(${res.statusCode})`)
          err.statusCode = Number(res.statusCode || 0)
          err.code = body.code
          err.response = body
          if (body.currentVersion !== undefined) {
            err.currentVersion = Number(body.currentVersion)
          }
          reject(err)
          return
        }
        resolve(body)
      },
      fail: (error) => {
        reject(new Error((error && error.errMsg) || '经营系统网络请求失败'))
      }
    })
  })
}

function normalizeText(value) {
  return String(value || '').trim()
}

function normalizeKeyword(value) {
  return normalizeText(value).replace(/\s+/g, '').toLowerCase()
}

function normalizeMoneyValue(value, fallback = 0) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) {
    return fallback
  }
  return Math.round(amount * 100) / 100
}

function normalizeStringList(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeText(item))
      .filter((item) => item)
  }

  const text = normalizeText(value)
  if (!text) {
    return []
  }

  return text
    .split(/[、/,，\s]+/)
    .map((item) => normalizeText(item))
    .filter((item) => item)
}

function normalizePhotoList(value) {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => normalizeText(item))
    .filter((item) => item)
}

function normalizeFollowupRecords(value) {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .map((item) => {
      const source = item && typeof item === 'object' ? item : {}
      const type = normalizeText(source.type).toUpperCase()
      if (!type) {
        return null
      }
      return {
        type,
        done: Boolean(source.done),
        doneAt: normalizeText(source.doneAt),
        remark: normalizeText(source.remark),
      }
    })
    .filter((item) => Boolean(item))
}

function normalizeDispatchInfo(value, fallback = {}) {
  const source = value && typeof value === 'object' ? value : {}
  const base = fallback && typeof fallback === 'object' ? fallback : {}
  const technicianNames = normalizeStringList(
    Array.isArray(source.technicianNames) && source.technicianNames.length > 0
      ? source.technicianNames
      : source.technicianName
  )
  const technicianName = normalizeText(source.technicianName || technicianNames[0])
  if (technicianName && technicianNames.indexOf(technicianName) < 0) {
    technicianNames.unshift(technicianName)
  }
  return {
    date: normalizeText(source.date || base.appointmentDate),
    time: normalizeText(source.time || base.appointmentTime),
    workBay: normalizeText(source.workBay),
    technicianName,
    technicianNames,
    technicianDisplay: technicianNames.join(' / '),
    remark: normalizeText(source.remark),
    updatedAt: normalizeText(source.updatedAt),
  }
}

function normalizeWorkPartRecords(records) {
  if (!Array.isArray(records)) {
    return []
  }

  return records
    .map((item) => {
      const source = item && typeof item === 'object' ? item : {}
      const partType = normalizeText(source.partType)
      const partCode = normalizeText(source.partCode)
      const partLabel = normalizeText(source.partLabel)
      if (!partType && !partCode && !partLabel) {
        return null
      }
      const technicianName = normalizeText(source.technicianName || source.technicianAccountName)
      return {
        id: normalizeText(source.id),
        partType,
        partTypeLabel: normalizeText(source.partTypeLabel),
        partCode,
        partLabel,
        amount: normalizeMoneyValue(source.amount, 0),
        technicianAccountId: normalizeText(source.technicianAccountId),
        technicianAccountName: normalizeText(source.technicianAccountName || technicianName),
        technicianName,
        photos: normalizePhotoList(source.photos),
        submittedAt: normalizeText(source.submittedAt),
      }
    })
    .filter((item) => Boolean(item))
}

function normalizeCommissionRecords(records) {
  if (!Array.isArray(records)) {
    return []
  }

  return records
    .map((item) => {
      const source = item && typeof item === 'object' ? item : {}
      const technicianName = normalizeText(source.technicianName || source.technicianAccountName)
      return {
        id: normalizeText(source.id),
        partType: normalizeText(source.partType),
        partTypeLabel: normalizeText(source.partTypeLabel),
        partCode: normalizeText(source.partCode),
        partLabel: normalizeText(source.partLabel),
        technicianAccountId: normalizeText(source.technicianAccountId),
        technicianAccountName: normalizeText(source.technicianAccountName || technicianName),
        technicianName,
        submittedAt: normalizeText(source.submittedAt),
        amount: normalizeMoneyValue(source.amount, 0),
        photos: normalizePhotoList(source.photos),
      }
    })
    .filter((item) => Boolean(item.partCode || item.partLabel || item.technicianName))
}

function normalizeOrderItem(item) {
  const source = item && typeof item === 'object' ? item : {}
  const priceSummary = source.priceSummary && typeof source.priceSummary === 'object' ? source.priceSummary : {}
  const packagePrice = Number(priceSummary.packagePrice)
  const addOnFee = Number(priceSummary.addOnFee)
  const totalPrice = Number(priceSummary.totalPrice)
  const deposit = Number(priceSummary.deposit)
  const commissionTotal = Number(source.commissionTotal)
  const version = Number(source.version)
  const dispatchInfo = normalizeDispatchInfo(source.dispatchInfo, source)
  const workPartRecords = normalizeWorkPartRecords(source.workPartRecords)
  const commissionRecords = normalizeCommissionRecords(source.commissionRecords)
  const technicianName = normalizeText(source.technicianName || dispatchInfo.technicianName)

  return {
    ...source,
    id: normalizeText(source.id),
    serviceType: normalizeText(source.serviceType || 'FILM') || 'FILM',
    status: normalizeText(source.status || '未完工') || '未完工',
    customerName: normalizeText(source.customerName),
    phone: normalizeText(source.phone),
    plateNumber: normalizeText(source.plateNumber),
    carModel: normalizeText(source.carModel),
    salesBrandText: normalizeText(source.salesBrandText),
    store: normalizeText(source.store),
    packageLabel: normalizeText(source.packageLabel),
    packageDesc: normalizeText(source.packageDesc),
    appointmentDate: normalizeText(source.appointmentDate),
    appointmentTime: normalizeText(source.appointmentTime),
    technicianName,
    commissionStatus: normalizeText(source.commissionStatus || '未生成'),
    commissionGeneratedAt: normalizeText(source.commissionGeneratedAt),
    deliveryStatus: normalizeText(source.deliveryStatus || '待交车验收'),
    deliveryPassedAt: normalizeText(source.deliveryPassedAt),
    createdAt: normalizeText(source.createdAt),
    updatedAt: normalizeText(source.updatedAt),
    commissionTotal: Number.isFinite(commissionTotal) ? commissionTotal : 0,
    dispatchInfo,
    workPartRecords,
    commissionRecords,
    constructionPhotos: normalizePhotoList(source.constructionPhotos),
    damagePhotos: normalizePhotoList(source.damagePhotos),
    depositProofPhotos: normalizePhotoList(source.depositProofPhotos),
    finalPaymentPhotos: normalizePhotoList(source.finalPaymentPhotos),
    finalPaymentUploadedAt: normalizeText(source.finalPaymentUploadedAt),
    financeSyncStatus: normalizeText(source.financeSyncStatus),
    financeSyncAt: normalizeText(source.financeSyncAt),
    financeSyncMessage: normalizeText(source.financeSyncMessage),
    financeExternalId: normalizeText(source.financeExternalId),
    financeLastEvent: normalizeText(source.financeLastEvent),
    followupRecords: normalizeFollowupRecords(source.followupRecords),
    followupLastUpdatedAt: normalizeText(source.followupLastUpdatedAt),
    version: Number.isFinite(version) ? version : 0,
    priceSummary: {
      ...priceSummary,
      packagePrice: Number.isFinite(packagePrice) ? packagePrice : 0,
      addOnFee: Number.isFinite(addOnFee) ? addOnFee : 0,
      totalPrice: Number.isFinite(totalPrice) ? totalPrice : 0,
      deposit: Number.isFinite(deposit) ? deposit : 0,
    }
  }
}

function matchKeyword(order, keyword) {
  const source = normalizeKeyword(keyword)
  if (!source) {
    return true
  }

  const fields = [
    order.id,
    order.customerName,
    order.phone,
    order.plateNumber,
    order.carModel,
    order.salesBrandText,
    order.packageLabel,
  ]

  return fields.some((field) => normalizeKeyword(field).includes(source))
}

function matchMine(order, role, salesName) {
  if (role !== 'sales' && role !== 'technician') {
    return true
  }
  const me = normalizeKeyword(salesName)
  if (!me) {
    return false
  }

  if (role === 'sales') {
    const owner = normalizeKeyword(order.salesBrandText)
    return owner === me
  }

  const dispatch = order && order.dispatchInfo && typeof order.dispatchInfo === 'object'
    ? order.dispatchInfo
    : {}
  const technicianNames = normalizeStringList(
    Array.isArray(dispatch.technicianNames) && dispatch.technicianNames.length > 0
      ? dispatch.technicianNames
      : dispatch.technicianName
  )
  if (technicianNames.some((name) => normalizeKeyword(name) === me)) {
    return true
  }

  const records = Array.isArray(order && order.workPartRecords) ? order.workPartRecords : []
  return records.some((item) => normalizeKeyword(item && item.technicianName) === me)
}

function sortOrders(orders) {
  return orders.slice().sort((a, b) => {
    const at = Date.parse(a.updatedAt || a.createdAt || '') || 0
    const bt = Date.parse(b.updatedAt || b.createdAt || '') || 0
    return bt - at
  })
}

function buildStats(orders) {
  const list = Array.isArray(orders) ? orders : []
  return {
    total: list.length,
    pending: list.filter((item) => item.status === '未完工').length,
    confirmed: list.filter((item) => item.status === '已完工').length,
    cancelled: list.filter((item) => item.status === '已取消').length,
  }
}

const storeApi = {
  async getOrders(params = {}) {
    const role = String(params.role || 'sales').toLowerCase()
    const view = String(params.view || 'ALL').toUpperCase()
    const status = String(params.status || 'ALL')
    const keyword = String(params.keyword || '')
    const session = getMiniAuthSession()
    const sessionName = String((session && session.user && session.user.name) || '')
    const salesName = String(params.salesName || sessionName || wx.getStorageSync('sales_name') || '')

    const data = await requestStore('/api/v1/store/orders', { method: 'GET' })
    const source = Array.isArray(data.items) ? data.items : []
    const normalized = source.map(normalizeOrderItem).filter((item) => item.id)

    let result = normalized
    if (status !== 'ALL') {
      result = result.filter((item) => item.status === status)
    }
    if (view === 'MINE') {
      result = result.filter((item) => matchMine(item, role, salesName))
    }
    result = result.filter((item) => matchKeyword(item, keyword))
    result = sortOrders(result)

    return {
      items: result,
      stats: buildStats(result),
    }
  },

  async getOrderDetail(orderId, params = {}) {
    const targetId = normalizeText(orderId)
    if (!targetId) {
      throw new Error('缺少订单ID')
    }

    const { items } = await this.getOrders({
      ...params,
      status: 'ALL',
      view: 'ALL',
    })

    const item = items.find((entry) => entry.id === targetId)
    if (!item) {
      throw new Error('订单不存在或无权限查看')
    }

    return item
  },

  async updateOrder(orderId, payload = {}) {
    const targetId = normalizeText(orderId)
    if (!targetId) {
      throw new Error('缺少订单ID')
    }

    const body = payload && typeof payload === 'object' ? payload : {}
    const version = Number(body.version)
    if (!Number.isFinite(version)) {
      throw new Error('缺少订单版本号，请先刷新后重试')
    }

    const patch = {
      version,
    }

    if (body.status !== undefined) {
      patch.status = normalizeText(body.status)
    }
    if (body.remark !== undefined) {
      patch.remark = normalizeText(body.remark)
    }
    if (body.appointmentDate !== undefined) {
      patch.appointmentDate = normalizeText(body.appointmentDate)
    }
    if (body.appointmentTime !== undefined) {
      patch.appointmentTime = normalizeText(body.appointmentTime)
    }
      if (body.salesBrandText !== undefined) {
        patch.salesBrandText = normalizeText(body.salesBrandText)
      }
      if (body.store !== undefined) {
        patch.store = normalizeText(body.store)
      }
      if (body.technicianName !== undefined) {
        patch.technicianName = normalizeText(body.technicianName)
      }
    if (body.dispatchInfo !== undefined) {
      patch.dispatchInfo = normalizeDispatchInfo(body.dispatchInfo, body)
    }
      if (body.workPartRecords !== undefined) {
        patch.workPartRecords = normalizeWorkPartRecords(body.workPartRecords)
      }
      if (body.constructionPhotos !== undefined) {
        patch.constructionPhotos = normalizePhotoList(body.constructionPhotos)
      }
      if (body.finalPaymentPhotos !== undefined) {
        patch.finalPaymentPhotos = normalizePhotoList(body.finalPaymentPhotos)
      }
      if (body.finalPaymentUploadedAt !== undefined) {
        patch.finalPaymentUploadedAt = normalizeText(body.finalPaymentUploadedAt)
      }
      if (body.deliveryStatus !== undefined) {
        patch.deliveryStatus = normalizeText(body.deliveryStatus)
      }
      if (body.deliveryPassedAt !== undefined) {
        patch.deliveryPassedAt = normalizeText(body.deliveryPassedAt)
      }
    if (body.commissionStatus !== undefined) {
      patch.commissionStatus = normalizeText(body.commissionStatus)
    }
      if (body.commissionGeneratedAt !== undefined) {
        patch.commissionGeneratedAt = normalizeText(body.commissionGeneratedAt)
      }
    if (body.commissionTotal !== undefined) {
      patch.commissionTotal = normalizeMoneyValue(body.commissionTotal, 0)
    }
      if (body.commissionRecords !== undefined) {
        patch.commissionRecords = normalizeCommissionRecords(body.commissionRecords)
      }
      if (body.financeSyncStatus !== undefined) {
        patch.financeSyncStatus = normalizeText(body.financeSyncStatus)
      }
      if (body.financeSyncAt !== undefined) {
        patch.financeSyncAt = normalizeText(body.financeSyncAt)
      }
      if (body.financeSyncMessage !== undefined) {
        patch.financeSyncMessage = normalizeText(body.financeSyncMessage)
      }
      if (body.financeExternalId !== undefined) {
        patch.financeExternalId = normalizeText(body.financeExternalId)
      }
      if (body.financeLastEvent !== undefined) {
        patch.financeLastEvent = normalizeText(body.financeLastEvent)
      }
      if (body.followupRecords !== undefined) {
        patch.followupRecords = normalizeFollowupRecords(body.followupRecords)
      }
      if (body.followupLastUpdatedAt !== undefined) {
        patch.followupLastUpdatedAt = normalizeText(body.followupLastUpdatedAt)
      }

    let data
    try {
      data = await requestStore(`/api/v1/store/orders/${encodeURIComponent(targetId)}`, {
        method: 'PATCH',
        data: patch,
      })
    } catch (error) {
      if (isVersionConflictError(error)) {
        const currentVersion = getCurrentVersion(error)
        if (currentVersion !== null) {
          throw new Error(`订单已被他人更新（最新版本 ${currentVersion}），请刷新后重试`)
        }
        throw new Error('订单已被他人更新，请刷新后重试')
      }
      throw error
    }

    return normalizeOrderItem(data.item || {})
  }
}

module.exports = {
  storeApi,
  getStoreApiBaseUrl,
}
