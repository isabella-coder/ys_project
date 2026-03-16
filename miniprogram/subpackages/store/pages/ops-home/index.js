const { getCurrentRole } = require('../../../../utils/adapters/store-permission')
const { storeApi, getStoreApiBaseUrl } = require('../../../../utils/adapters/store-api')
const { getMiniAuthSession, logoutMiniProgram } = require('../../../../utils/mini-auth')

const EMPTY_DASHBOARD = {
  washSlotCount: 0,
  constructionSlotCount: 0,
  salesAmount: 0,
  leadCount: 0,
  dealRateText: '0.0%',
  avgPrice: 0,
}

Page({
  data: {
    roleLabel: '销售',
    statDate: '',
    dashboardLoading: false,
    dashboard: EMPTY_DASHBOARD,
    filmChain: {
      route: '/subpackages/store/pages/film-order/index',
    },
    washChain: {
      route: '/subpackages/store/pages/wash-order/index',
    },
    quickEntries: [],
  },

  onShow() {
    const role = getCurrentRole()
    const roleLabelMap = {
      manager: '店长',
      sales: '销售',
      finance: '财务',
      technician: '施工'
    }

    const quickEntries = [
      { key: 'all-orders', name: '全部订单', route: '/subpackages/store/pages/order-list/index' },
      { key: 'dispatch-film', name: '贴膜派工看板', route: '/subpackages/store/pages/dispatch-board/index' },
      { key: 'dispatch-wash', name: '洗车派工看板', route: '/subpackages/store/pages/wash-dispatch-board/index' },
      { key: 'sales-board', name: '销售业绩看板', route: '/subpackages/store/pages/sales-performance/index' },
      { key: 'lead-board', name: '线索分配看板', route: '/subpackages/store/pages/douyin-leads/index' },
      { key: 'followup-board', name: '回访提醒看板', route: '/subpackages/store/pages/followup-reminder/index' },
    ]

    this.setData({
      roleLabel: roleLabelMap[role] || '销售',
      quickEntries,
      statDate: this.formatDate(new Date()),
    })

    this.loadDashboard(role)
  },

  async loadDashboard(role) {
    const statDate = this.formatDate(new Date())
    this.setData({
      dashboardLoading: true,
      statDate,
    })

    try {
      const orders = await this.loadOrderItems(role)
      const orderMetrics = this.buildOrderMetrics(orders, statDate)
      const leadMetrics = await this.loadLeadMetrics()

      this.setData({
        dashboard: {
          ...orderMetrics,
          ...leadMetrics,
        },
      })
    } catch (error) {
      this.setData({ dashboard: EMPTY_DASHBOARD })
    }

    this.setData({ dashboardLoading: false })
  },

  async loadOrderItems(role) {
    const safeRole = String(role || 'sales').toLowerCase()
    try {
      const allResult = await storeApi.getOrders({
        role: safeRole,
        view: 'ALL',
        status: 'ALL',
      })
      return Array.isArray(allResult.items) ? allResult.items : []
    } catch (error) {
      // Roles without ALL permission can still view MINE; fallback keeps dashboard usable.
      const mineResult = await storeApi.getOrders({
        role: safeRole,
        view: 'MINE',
        status: 'ALL',
      })
      return Array.isArray(mineResult.items) ? mineResult.items : []
    }
  },

  buildOrderMetrics(orders, statDate) {
    const list = Array.isArray(orders) ? orders : []
    const activeOrders = list.filter((item) => String(item.status || '') !== '已取消')
    const todayOrders = activeOrders.filter((item) => {
      const appointmentDate = String(item.appointmentDate || '').trim()
      if (appointmentDate) {
        return appointmentDate === statDate
      }
      const createdAt = String(item.createdAt || '').trim()
      return createdAt.slice(0, 10) === statDate
    })

    const washSlotCount = todayOrders.filter((item) => String(item.serviceType || '') === 'WASH').length
    const constructionSlotCount = todayOrders.filter((item) => String(item.serviceType || '') !== 'WASH').length
    const salesAmount = this.roundMoney(
      todayOrders.reduce((sum, item) => sum + Number((item.priceSummary && item.priceSummary.totalPrice) || 0), 0)
    )
    const avgPrice = todayOrders.length > 0 ? this.roundMoney(salesAmount / todayOrders.length) : 0

    return {
      washSlotCount,
      constructionSlotCount,
      salesAmount,
      avgPrice,
    }
  },

  loadLeadMetrics() {
    const session = getMiniAuthSession()
    const token = String((session && session.token) || '').trim()
    if (!token) {
      return Promise.resolve({ leadCount: 0, dealRateText: '0.0%' })
    }

    const baseUrl = getStoreApiBaseUrl()
    const url = `${baseUrl}/api/v1/store/leads?grade=ALL&view=ALL`
    return new Promise((resolve) => {
      wx.request({
        url,
        method: 'GET',
        header: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Api-Token': token,
        },
        timeout: 12000,
        success: (res) => {
          const body = res && res.data ? res.data : {}
          const ok = (res.statusCode >= 200 && res.statusCode < 300)
            && (body.success === true || body.ok === true || body.code === 0)
          if (!ok) {
            resolve({ leadCount: 0, dealRateText: '0.0%' })
            return
          }

          const items = Array.isArray(body.items) ? body.items : []
          const leadCount = items.length
          const dealCount = items.filter((item) => String(item.leadStatus || '') === '已成交').length
          const dealRateText = leadCount > 0 ? `${((dealCount * 100) / leadCount).toFixed(1)}%` : '0.0%'
          resolve({ leadCount, dealRateText })
        },
        fail: () => {
          resolve({ leadCount: 0, dealRateText: '0.0%' })
        }
      })
    })
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定退出当前账号吗？',
      success: async (res) => {
        if (!res.confirm) {
          return
        }

        await logoutMiniProgram()
        const app = getApp()
        if (app && typeof app.logout === 'function') {
          app.logout()
        }
        wx.reLaunch({ url: '/pages/login' })
      }
    })
  },

  roundMoney(value) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) {
      return 0
    }
    return Math.round(parsed * 100) / 100
  },

  formatDate(date) {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  },

  onOpenRoute(e) {
    const route = e.currentTarget.dataset.route || ''
    if (route) {
      wx.navigateTo({ url: route })
      return
    }

    wx.showToast({
      title: '该入口暂未开放',
      icon: 'none'
    })
  }
})
