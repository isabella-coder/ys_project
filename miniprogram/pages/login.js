const { authApi } = require('../utils/api')
const { loginMiniProgram } = require('../utils/mini-auth')
const { getAvailableAccounts } = require('../utils/user-context')

Page({
  data: {
    accountOptions: [],
    selectedIndex: 0,
    selectedLabel: '',
    selectedAccountId: '',
    selectedRole: 'sales',
    password: '',
    rememberAccount: true,
    loading: false,
  },

  async onLoad() {
    // 强制刷新后端地址到最新配置
    wx.removeStorageSync('financeBaseUrl')
    wx.removeStorageSync('store_api_base_url')

    const remembered = wx.getStorageSync('remember_login_account')
    const rememberEnabled = wx.getStorageSync('remember_login_enabled')

    this.setData({
      selectedAccountId: remembered || '',
      rememberAccount: rememberEnabled !== false,
    })

    await this.loadAccountOptions()
  },

  async onShow() {
    const app = getApp()
    if (app.checkLogin()) {
      const role = String(wx.getStorageSync('mini_role') || wx.getStorageSync('user_role') || 'sales').toLowerCase()
      if (role === 'technician' || role === 'finance' || role === 'manager') {
        wx.redirectTo({ url: '/subpackages/store/pages/ops-home/index' })
        return
      }
      wx.switchTab({ url: '/pages/index' })
    }
  },

  async loadAccountOptions() {
    try {
      let salesOptions = []
      try {
        salesOptions = await authApi.getSalesOptions()
      } catch (error) {
        salesOptions = []
      }

      const options = this.buildAccountOptions(salesOptions)
      const selected = this.pickDefaultAccountId(options)
      const selectedIndex = this.getSelectedIndexByAccountId(options, selected)
      const selectedOption = options[selectedIndex] || {}
      this.setData({
        accountOptions: options,
        selectedIndex,
        selectedLabel: this.buildAccountLabel(selectedOption),
        selectedAccountId: selected,
        selectedRole: selectedOption.role || 'sales',
      })
    } catch (e) {
      wx.showToast({ title: '加载账号失败', icon: 'none' })
    }
  },

  buildAccountOptions(salesOptions = []) {
    const accountMap = new Map()
    const localOptions = getAvailableAccounts()
    localOptions.forEach((item) => {
      const accountId = String(item.accountId || '').trim()
      if (!accountId) {
        return
      }
      accountMap.set(accountId, {
        account_id: accountId,
        account_name: String(item.accountName || accountId),
        role: this.normalizeRole(item.role),
        role_label: String(item.roleLabel || this.getRoleLabel(this.normalizeRole(item.role))),
        store_code: '',
      })
    })

    const remoteSales = Array.isArray(salesOptions) ? salesOptions : []
    remoteSales.forEach((item) => {
      const accountId = String(item.sales_id || '').trim()
      if (!accountId) {
        return
      }

      const current = accountMap.get(accountId) || {}
      accountMap.set(accountId, {
        ...current,
        account_id: accountId,
        account_name: String(item.sales_name || current.account_name || accountId),
        role: 'sales',
        role_label: this.getRoleLabel('sales'),
        store_code: String(item.store_code || current.store_code || ''),
      })
    })

    const options = Array.from(accountMap.values())
    return options.map((item) => ({
      ...item,
      display_name: this.buildAccountLabel(item),
    }))
  },

  normalizeRole(role) {
    const key = String(role || '').trim().toLowerCase()
    if (!key) {
      return 'sales'
    }
    if (key === 'manager' || key === 'sales' || key === 'finance' || key === 'technician') {
      return key
    }

    const map = {
      MANAGER: 'manager',
      SALES: 'sales',
      FINANCE: 'finance',
      TECHNICIAN: 'technician',
    }
    return map[String(role || '').trim().toUpperCase()] || 'sales'
  },

  getRoleLabel(role) {
    const normalized = this.normalizeRole(role)
    if (normalized === 'manager') {
      return '店长'
    }
    if (normalized === 'sales') {
      return '销售'
    }
    if (normalized === 'finance') {
      return '财务'
    }
    return '施工'
  },

  pickDefaultAccountId(options) {
    if (!options || options.length === 0) {
      return ''
    }

    const current = this.data.selectedAccountId
    if (current && options.find(item => item.account_id === current)) {
      return current
    }

    return options[0].account_id
  },

  getSelectedIndexByAccountId(options, accountId) {
    const index = options.findIndex(item => item.account_id === accountId)
    return index >= 0 ? index : 0
  },

  buildAccountLabel(item) {
    if (!item) {
      return '请选择账号'
    }
    const name = String(item.account_name || '').trim()
    const roleLabel = String(item.role_label || this.getRoleLabel(item.role)).trim()
    const storeCode = String(item.store_code || '').trim()
    if (storeCode) {
      return `${name}（${roleLabel}/${storeCode}）`
    }
    return `${name}（${roleLabel}）`
  },

  onAccountChange(e) {
    const selectedIndex = Number(e.detail.value || 0)
    const selected = this.data.accountOptions[selectedIndex] || {}
    this.setData({
      selectedIndex,
      selectedAccountId: selected.account_id || '',
      selectedRole: selected.role || 'sales',
      selectedLabel: this.buildAccountLabel(selected),
    })
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  onRememberChange(e) {
    this.setData({ rememberAccount: !!e.detail.value.length })
  },

  async handleLogin() {
    if (this.data.loading) {
      return
    }

    const accountId = this.data.selectedAccountId
    const selectedRole = this.normalizeRole(this.data.selectedRole)
    const password = this.data.password

    if (!accountId) {
      wx.showToast({ title: '请选择账号', icon: 'none' })
      return
    }

    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }

    this.setData({ loading: true })

    console.log('[handleLogin] accountId=', accountId, 'selectedRole=', selectedRole, 'password=', password)

    try {
      if (selectedRole === 'sales') {
        await this.loginSalesAccount(accountId, password)
      } else {
        await this.loginStoreAccount(accountId, password, selectedRole)
      }

      if (this.data.rememberAccount) {
        wx.setStorageSync('remember_login_account', accountId)
        wx.setStorageSync('remember_login_enabled', true)
      } else {
        wx.removeStorageSync('remember_login_account')
        wx.setStorageSync('remember_login_enabled', false)
      }

      wx.showToast({ title: '登录成功', icon: 'success' })

      // 登录成功后请求订阅消息授权（新线索提醒）
      this.requestSubscribePermission()

      setTimeout(() => {
        const resolvedRole = this.normalizeRole(wx.getStorageSync('mini_role') || wx.getStorageSync('user_role') || selectedRole)
        if (resolvedRole === 'technician' || resolvedRole === 'finance' || resolvedRole === 'manager') {
          wx.redirectTo({ url: '/subpackages/store/pages/ops-home/index' })
          return
        }
        wx.switchTab({ url: '/pages/index' })
      }, 250)
    } catch (e) {
      wx.showToast({ title: e.message || '登录失败', icon: 'none' })
    }

    this.setData({ loading: false })
  },

  async loginSalesAccount(accountId, password) {
    try {
      const result = await authApi.login(accountId, password)
      const resolvedRole = String(result.role || wx.getStorageSync('mini_role') || 'sales').toLowerCase()
      const app = getApp()
      app.setLoginInfo({
        token: result.token,
        salesId: result.sales_id,
        salesName: result.sales_name,
        storeCode: result.store_code,
        userRole: resolvedRole,
        userInfo: {
          sales_name: result.sales_name,
          store_code: result.store_code,
          role: resolvedRole,
        },
      })
    } catch (error) {
      await this.loginStoreAccount(accountId, password, 'sales')
    }
  },

  requestSubscribePermission() {
    const tmplId = wx.getStorageSync('subscribe_template_lead') || ''
    if (!tmplId) return
    wx.requestSubscribeMessage({
      tmplIds: [tmplId],
      success(res) {
        console.log('订阅消息授权结果:', res)
      },
      fail(err) {
        console.warn('订阅消息授权失败:', err)
      },
    })
  },

  async loginStoreAccount(accountId, password, selectedRole) {
    const result = await loginMiniProgram({
      username: accountId,
      password,
    })
    const user = result && result.user ? result.user : {}
    const token = result && result.token ? result.token : ''
    const role = String(user.role || selectedRole || 'technician').toLowerCase()

    const app = getApp()
    app.setLoginInfo({
      token,
      salesId: user.username || accountId,
      salesName: user.name || accountId,
      storeCode: user.store || user.store_code || '',
      userRole: role,
      userInfo: {
        sales_name: user.name || accountId,
        store_code: user.store || user.store_code || '',
        role,
      },
    })
  },
})
