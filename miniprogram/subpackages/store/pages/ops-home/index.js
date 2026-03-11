const { getCurrentRole } = require('../../../../utils/adapters/store-permission')

Page({
  data: {
    roleLabel: '销售',
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
    ]

    this.setData({
      roleLabel: roleLabelMap[role] || '销售',
      quickEntries,
    })
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
