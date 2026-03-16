const { storeApi } = require('../../../../utils/adapters/store-api')
const { getCurrentRole } = require('../../../../utils/adapters/store-permission')
const { normalizeErrorMessage, isVersionConflictError } = require('../../../../utils/adapters/store-error')
const { syncOrderToFinance } = require('../../../../utils/finance-sync')
const {
  DAILY_WORK_BAY_LIMIT,
  getDailyCapacityMessage,
  getDailyCapacityStatus,
  isOrderScheduledOn,
} = require('../../../../utils/scheduling')
const {
  TECHNICIAN_OPTIONS,
  findTechnicianAccountById,
  findTechnicianAccountByName,
} = require('../../../../utils/staff-options')
const { getMiniAuthSession } = require('../../../../utils/mini-auth')

const WORK_BAY_OPTIONS = Array.from({ length: DAILY_WORK_BAY_LIMIT }, (_, index) => `${index + 1}号工位`)

const PART_TYPE_OPTIONS = [
  { label: '整车车衣', value: 'FULL_CAR' },
  { label: '局部车衣', value: 'PARTIAL_PATCH' },
  { label: '整车玻璃膜', value: 'FULL_GLASS' },
  { label: '局部玻璃膜', value: 'PARTIAL_GLASS' },
]

const PART_RULES = {
  FULL_CAR: [
    { code: 'FULL_FRONT_HOOD', label: '前杠机盖', amount: 200 },
    { code: 'FULL_REAR_TRUNK_WING', label: '后杠后盖尾翼', amount: 200 },
    { code: 'FULL_LEFT_SIDE', label: '左侧面', amount: 100 },
    { code: 'FULL_RIGHT_SIDE', label: '右侧面', amount: 100 },
  ],
  PARTIAL_PATCH: [
    { code: 'PATCH_HOOD', label: '机盖', amount: 40 },
    { code: 'PATCH_FRONT_BUMPER', label: '前杠', amount: 100 },
    { code: 'PATCH_ROOF', label: '顶', amount: 40 },
    { code: 'PATCH_FRONT_FENDER', label: '前叶', amount: 15 },
    { code: 'PATCH_REAR_FENDER', label: '后叶', amount: 40 },
    { code: 'PATCH_DOOR', label: '门', amount: 15 },
    { code: 'PATCH_TRUNK', label: '后盖', amount: 20 },
    { code: 'PATCH_REAR_BUMPER', label: '后杠', amount: 100 },
  ],
  FULL_GLASS: [
    { code: 'GLASS_FULL_METAL', label: '金属膜', amount: 200 },
    { code: 'GLASS_FULL_CERAMIC', label: '陶瓷膜', amount: 150 },
  ],
  PARTIAL_GLASS: [
    { code: 'GLASS_METAL_FRONT', label: '金属前挡', amount: 100 },
    { code: 'GLASS_CERAMIC_FRONT', label: '陶瓷前挡', amount: 50 },
    { code: 'GLASS_REAR', label: '后挡', amount: 60 },
    { code: 'GLASS_SIDE_FRONT', label: '主副玻璃', amount: 20 },
    { code: 'GLASS_SIDE_REAR', label: '后排玻璃', amount: 20 },
  ],
}

const CUTTING_FEE_AMOUNTS = [10, 15, 20, 30]

Page({
  data: {
    orderId: '',
    role: 'sales',
    loading: false,
    saving: false,
    errorText: '',
    servicePhone: '',
    order: null,
    hasOrder: false,

    currentUser: {},
    isManagerMode: false,
    isTechnicianMode: false,
    canSubmitWorkPart: false,
    canCompleteOrder: false,

    financeSyncLoading: false,
    generatingCommission: false,

    displayedCommissionRecords: [],
    displayedCommissionTotal: 0,

    priceView: {
      packagePrice: 0,
      addOnFee: 0,
      totalPrice: 0,
      deposit: 0,
    },

    partTypeOptions: PART_TYPE_OPTIONS,
    partTypeIndex: 0,
    partOptions: PART_RULES.FULL_CAR,
    partTechnicianIndex: -1,

    workBayOptions: WORK_BAY_OPTIONS,
    technicianOptions: TECHNICIAN_OPTIONS,
    dispatchTechnicianOptions: [],
    dispatchBayIndex: 0,
    dispatchForm: {
      date: '',
      time: '',
      workBay: WORK_BAY_OPTIONS[0],
      technicianNames: [],
      remark: '',
    },

    partForm: {
      partType: 'FULL_CAR',
      partCodes: ['FULL_FRONT_HOOD'],
      technicianAccountId: '',
      technicianAccountName: '',
      technicianName: '',
      photos: [],
    },

    cuttingFeeAmountOptions: CUTTING_FEE_AMOUNTS,
    cuttingFeeTechIndex: -1,
    cuttingFeeAmount: 0,
  },

  onLoad(options) {
    const role = getCurrentRole()
    const session = getMiniAuthSession()
    const user = buildCurrentUser(role, session && session.user)

    this.setData({
      orderId: options.id || '',
      role,
      servicePhone: (getApp() && getApp().globalData && getApp().globalData.servicePhone) || '',
      currentUser: user,
      isManagerMode: role === 'manager',
      isTechnicianMode: role === 'technician',
      canSubmitWorkPart: role === 'manager' || role === 'technician',
      dispatchTechnicianOptions: buildTechnicianCheckOptions([], TECHNICIAN_OPTIONS),
    })

    this.syncPartPicker('FULL_CAR', ['FULL_FRONT_HOOD'])
  },

  onShow() {
    if (!this.data.orderId) {
      this.setData({ errorText: '缺少订单ID' })
      return
    }
    this.loadDetail()
  },

  onPullDownRefresh() {
    this.loadDetail().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  async loadDetail() {
    this.setData({ loading: true, errorText: '' })
    try {
      const order = await storeApi.getOrderDetail(this.data.orderId, { role: this.data.role })
      this.refreshOrderView(normalizeOrder(order))
    } catch (error) {
      this.setData({
        errorText: normalizeErrorMessage(error, '详情加载失败'),
        order: null,
        hasOrder: false,
      })
    }
    this.setData({ loading: false })
  },

  refreshOrderView(order) {
    const normalizedOrder = normalizeOrder(order)
    if (!normalizedOrder) {
      this.setData({ order: null, hasOrder: false })
      return
    }

    const dispatchState = getDispatchState(normalizedOrder, this.data.workBayOptions, this.data.technicianOptions)
    const permissionState = buildOrderPermissionState(normalizedOrder, this.data.currentUser, this.data.role)
    const activeTechnician = getActiveTechnicianProfile(this.data.currentUser, this.data.role)
    const lockedTechnicianName = activeTechnician && activeTechnician.name ? activeTechnician.name : ''
    const partTechnicianName = this.data.isTechnicianMode
      ? lockedTechnicianName
      : (this.data.partForm.technicianName || '')
    const partTechnicianAccountId = this.data.isTechnicianMode
      ? (activeTechnician && activeTechnician.id ? activeTechnician.id : '')
      : getTechnicianAccountIdByName(partTechnicianName)
    const partTechnicianIndex = this.data.technicianOptions.indexOf(partTechnicianName)

    this.setData({
      order: normalizedOrder,
      hasOrder: true,
      priceView: normalizePriceSummary(normalizedOrder.priceSummary),
      canCompleteOrder: permissionState.canCompleteOrder,
      displayedCommissionRecords: permissionState.displayedCommissionRecords,
      displayedCommissionTotal: permissionState.displayedCommissionTotal,
      dispatchBayIndex: dispatchState.bayIndex,
      dispatchTechnicianOptions: buildTechnicianCheckOptions(dispatchState.form.technicianNames, this.data.technicianOptions),
      partTechnicianIndex: partTechnicianIndex >= 0 ? partTechnicianIndex : (this.data.isTechnicianMode ? 0 : -1),
      dispatchForm: dispatchState.form,
      partForm: {
        ...this.data.partForm,
        technicianAccountId: partTechnicianAccountId,
        technicianAccountName: partTechnicianName,
        technicianName: partTechnicianName,
      },
      cuttingFeeTechIndex: normalizedOrder.cuttingFee
        ? this.data.technicianOptions.indexOf(normalizedOrder.cuttingFee.technicianName)
        : this.data.cuttingFeeTechIndex,
      cuttingFeeAmount: normalizedOrder.cuttingFee
        ? (normalizedOrder.cuttingFee.amount || 0)
        : this.data.cuttingFeeAmount,
    })
  },

  normalizeSaveError(error) {
    if (isVersionConflictError(error)) {
      return {
        text: normalizeErrorMessage(error, '订单已被他人更新，请先刷新后重试'),
        suggestRefresh: true,
      }
    }
    return {
      text: normalizeErrorMessage(error, '保存失败'),
      suggestRefresh: false,
    }
  },

  handleSaveError(error) {
    const result = this.normalizeSaveError(error)
    if (!result.suggestRefresh) {
      wx.showToast({ title: result.text, icon: 'none' })
      return
    }

    wx.showModal({
      title: '保存失败',
      content: `${result.text}\n建议先刷新订单后再保存。`,
      confirmText: '刷新订单',
      cancelText: '稍后再试',
      success: (res) => {
        if (res.confirm) {
          this.loadDetail()
        }
      }
    })
  },

  async patchOrder(patch, options = {}) {
    if (!this.data.order || !this.data.order.id) {
      return null
    }

    const targetPatch = patch && typeof patch === 'object' ? patch : {}
    if (Object.keys(targetPatch).length === 0) {
      return this.data.order
    }

    // 保存滚动位置，防止 setData 刷新后跳回顶部
    const scrollTop = await new Promise((resolve) => {
      wx.createSelectorQuery().selectViewport().scrollOffset(function (res) {
        resolve(res ? res.scrollTop : 0)
      }).exec()
    })

    this.setData({ saving: true })
    try {
      const updated = await storeApi.updateOrder(this.data.order.id, {
        version: this.data.order.version,
        ...targetPatch,
      })
      const normalizedOrder = normalizeOrder(updated)
      this.refreshOrderView(normalizedOrder)

      if (options.syncEvent) {
        this.trySyncFinance(normalizedOrder, options.syncEvent, false)
      }
      if (options.successTitle) {
        wx.showToast({ title: options.successTitle, icon: 'success' })
      }

      return normalizedOrder
    } catch (error) {
      this.handleSaveError(error)
      return null
    } finally {
      this.setData({ saving: false })
      // 恢复滚动位置
      if (scrollTop > 0) {
        setTimeout(() => {
          wx.pageScrollTo({ scrollTop, duration: 0 })
        }, 50)
      }
    }
  },

  copyOrderId() {
    if (!this.data.order || !this.data.order.id) {
      return
    }
    wx.setClipboardData({ data: this.data.order.id })
  },

  callService() {
    if (!this.data.servicePhone) {
      return
    }
    wx.makePhoneCall({ phoneNumber: this.data.servicePhone })
  },

  previewVinPhoto() {
    const current = this.data.order && this.data.order.vinPhoto ? this.data.order.vinPhoto : ''
    if (!current) {
      return
    }
    wx.previewImage({ current, urls: [current] })
  },

  previewDepositProof(event) {
    const index = Number(event.currentTarget.dataset.index)
    const urls = this.data.order && Array.isArray(this.data.order.depositProofPhotos)
      ? this.data.order.depositProofPhotos
      : []
    const current = urls[index] || ''
    if (!current) {
      return
    }
    wx.previewImage({ current, urls })
  },

  onDispatchDateChange(event) {
    if (!this.data.isManagerMode) {
      return
    }
    this.setData({ 'dispatchForm.date': event.detail.value })
  },

  onDispatchTimeChange(event) {
    if (!this.data.isManagerMode) {
      return
    }
    this.setData({ 'dispatchForm.time': event.detail.value })
  },

  onDispatchBayChange(event) {
    if (!this.data.isManagerMode) {
      return
    }
    const index = Number(event.detail.value)
    const bayOptions = this.data.workBayOptions
    const bay = bayOptions[index] || bayOptions[0]
    this.setData({
      dispatchBayIndex: index,
      'dispatchForm.workBay': bay,
    })
  },

  onDispatchTechniciansChange(event) {
    if (!this.data.isManagerMode) {
      return
    }
    const selected = sanitizeStringList(event && event.detail ? event.detail.value : [])
    const validSet = new Set(this.data.technicianOptions)
    const technicianNames = selected.filter((item) => validSet.has(item))
    this.setData({
      dispatchTechnicianOptions: buildTechnicianCheckOptions(technicianNames, this.data.technicianOptions),
      'dispatchForm.technicianNames': technicianNames,
    })
  },

  onDispatchRemarkInput(event) {
    if (!this.data.isManagerMode) {
      return
    }
    this.setData({ 'dispatchForm.remark': event.detail.value || '' })
  },

  async saveDispatch() {
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可操作派工', icon: 'none' })
      return
    }
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)
    const dispatch = normalizeDispatchInfo(this.data.dispatchForm)
    const error = validateDispatchInfo(dispatch)
    if (error) {
      wx.showToast({ title: error, icon: 'none' })
      return
    }

    if (dispatch.technicianNames.some((name) => this.data.technicianOptions.indexOf(name) < 0)) {
      wx.showToast({ title: '请选择派工技师', icon: 'none' })
      return
    }

    try {
      const result = await storeApi.getOrders({ role: this.data.role, view: 'ALL', status: 'ALL' })
      const orders = Array.isArray(result && result.items) ? result.items : []
      const fullCapacityMessage = findDailyCapacityConflict(order.id, order, dispatch, orders, DAILY_WORK_BAY_LIMIT)
      if (fullCapacityMessage) {
        wx.showModal({ title: '工位已满', content: fullCapacityMessage, showCancel: false })
        return
      }

      const conflict = findDispatchConflict(order.id, dispatch, orders)
      if (conflict) {
        wx.showModal({ title: '派工冲突', content: conflict, showCancel: false })
        return
      }
    } catch (err) {
      wx.showToast({ title: normalizeErrorMessage(err, '派工校验失败'), icon: 'none' })
      return
    }

    const patch = {
      status: order.status === '已取消' ? '已取消' : (order.status === '已完工' ? '已完工' : '未完工'),
      technicianName: dispatch.technicianName || '',
      dispatchInfo: {
        ...dispatch,
        updatedAt: buildTimeText(new Date()),
      },
    }

    await this.patchOrder(patch, {
      successTitle: '派工已保存',
      syncEvent: 'ORDER_DISPATCH_UPDATED',
    })
  },

  goDispatchBoard() {
    const dispatchDate = this.data.dispatchForm && this.data.dispatchForm.date
      ? this.data.dispatchForm.date
      : ''
    const query = dispatchDate ? `?date=${dispatchDate}` : ''
    wx.navigateTo({ url: `/subpackages/store/pages/dispatch-board/index${query}` })
  },

  onPartTypeChange(event) {
    if (!this.data.canSubmitWorkPart) {
      return
    }
    const index = Number(event.detail.value)
    const option = PART_TYPE_OPTIONS[index] || PART_TYPE_OPTIONS[0]
    this.syncPartPicker(option.value, [])
  },

  onPartCodesChange(event) {
    if (!this.data.canSubmitWorkPart) {
      return
    }
    const selected = sanitizeStringList(event && event.detail ? event.detail.value : [])
    const validCodes = new Set(this.data.partOptions.map((item) => item.code))
    const partCodes = selected.filter((item) => validCodes.has(item))
    const partOptions = this.data.partOptions.map((item) => ({
      ...item,
      checked: partCodes.indexOf(item.code) >= 0,
    }))
    this.setData({ partOptions, 'partForm.partCodes': partCodes })
  },

  onPartTechnicianChange(event) {
    if (!this.data.canSubmitWorkPart || this.data.isTechnicianMode) {
      return
    }
    const index = Number(event.detail.value)
    const technicianOptions = this.data.technicianOptions
    const technicianName = technicianOptions[index] || ''
    const technicianAccountId = getTechnicianAccountIdByName(technicianName)
    this.setData({
      partTechnicianIndex: index,
      'partForm.technicianAccountId': technicianAccountId,
      'partForm.technicianAccountName': technicianName,
      'partForm.technicianName': technicianName,
    })
  },

  // ── 裁膜费选择 ──
  onCuttingFeeTechChange(event) {
    this.setData({ cuttingFeeTechIndex: Number(event.detail.value) })
  },

  onCuttingFeeAmountTap(event) {
    const amount = Number(event.currentTarget.dataset.amount) || 0
    this.setData({ cuttingFeeAmount: amount })
  },

  async saveCuttingFee() {
    if (!this.data.hasOrder) return
    const amount = this.data.cuttingFeeAmount || 0
    const techIndex = this.data.cuttingFeeTechIndex
    const techName = techIndex >= 0 ? (this.data.technicianOptions[techIndex] || '') : ''
    const cuttingFee = amount > 0 && techName
      ? { technicianName: techName, amount }
      : null
    await this.patchOrder({ cuttingFee })
    wx.showToast({ title: cuttingFee ? '裁膜费已保存' : '裁膜费已清除', icon: 'success' })
  },

  choosePartPhotos() {
    if (!this.data.canSubmitWorkPart) {
      wx.showToast({ title: '当前账号无施工提交权限', icon: 'none' })
      return
    }
    wx.chooseImage({
      count: 9,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const selected = Array.isArray(res.tempFilePaths) ? res.tempFilePaths : []
        const current = Array.isArray(this.data.partForm.photos) ? this.data.partForm.photos : []
        const merged = current.concat(selected).slice(0, 9)
        this.setData({ 'partForm.photos': merged })
      }
    })
  },

  removePartPhoto(event) {
    if (!this.data.canSubmitWorkPart) {
      return
    }
    const index = Number(event.currentTarget.dataset.index)
    const list = Array.isArray(this.data.partForm.photos) ? this.data.partForm.photos.slice() : []
    if (index < 0 || index >= list.length) {
      return
    }
    list.splice(index, 1)
    this.setData({ 'partForm.photos': list })
  },

  previewPartPhoto(event) {
    const index = Number(event.currentTarget.dataset.index)
    const urls = Array.isArray(this.data.partForm.photos) ? this.data.partForm.photos : []
    const current = urls[index] || ''
    if (!current) {
      return
    }
    wx.previewImage({ current, urls })
  },

  previewWorkPhoto(event) {
    const recordIndex = Number(event.currentTarget.dataset.recordIndex)
    const photoIndex = Number(event.currentTarget.dataset.photoIndex)
    const records = this.data.order && Array.isArray(this.data.order.workPartRecords)
      ? this.data.order.workPartRecords
      : []
    const record = records[recordIndex]
    if (!record || !Array.isArray(record.photos)) {
      return
    }

    const current = record.photos[photoIndex] || ''
    if (!current) {
      return
    }

    wx.previewImage({ current, urls: record.photos })
  },

  async saveWorkPartRecord() {
    if (!this.data.hasOrder) {
      return
    }
    if (!this.data.canSubmitWorkPart) {
      wx.showToast({ title: '当前账号无施工提交权限', icon: 'none' })
      return
    }

    const activeTechnician = getActiveTechnicianProfile(this.data.currentUser, this.data.role)
    const technicianName = this.data.isTechnicianMode
      ? (activeTechnician && activeTechnician.name ? activeTechnician.name : '')
      : String(this.data.partForm.technicianName || '').trim()
    const technicianAccountId = this.data.isTechnicianMode
      ? (activeTechnician && activeTechnician.id ? activeTechnician.id : '')
      : getTechnicianAccountIdByName(technicianName)
    const technicianAccountName = getTechnicianDisplayName(technicianAccountId, technicianName)
    const partType = getSafePartType(this.data.partForm.partType)
    const validPartCodes = new Set(getPartOptions(partType).map((item) => item.code))
    const partCodes = sanitizeStringList(this.data.partForm.partCodes).filter((code) => validPartCodes.has(code))
    const photos = sanitizePhotos(this.data.partForm.photos)

    if (!technicianName || this.data.technicianOptions.indexOf(technicianName) < 0) {
      wx.showToast({ title: '请选择施工人员', icon: 'none' })
      return
    }
    if (!technicianAccountId) {
      wx.showToast({ title: '施工账号无效，请重新选择', icon: 'none' })
      return
    }
    if (partCodes.length === 0) {
      wx.showToast({ title: '请选择施工部位', icon: 'none' })
      return
    }
    if (photos.length === 0) {
      wx.showToast({ title: '请上传施工照片', icon: 'none' })
      return
    }

    const currentOrder = normalizeOrder(this.data.order)
    const records = Array.isArray(currentOrder.workPartRecords) ? currentOrder.workPartRecords.slice() : []
    const nowText = buildTimeText(new Date())
    const selectedKeys = new Set(partCodes.map((partCode) => buildPartKey(partType, partCode)))
    const isTechMode = this.data.isTechnicianMode

    if (isTechMode) {
      const conflictRecord = records.find((item) => {
        const partKey = buildPartKey(item.partType, item.partCode)
        return selectedKeys.has(partKey) && !isOwnedByCurrentTechnician(item, this.data.currentUser, this.data.role)
      })
      if (conflictRecord) {
        wx.showToast({
          title: `${conflictRecord.partLabel || '该部位'}已由${conflictRecord.technicianName || '其他技师'}提交`,
          icon: 'none',
        })
        return
      }
    }

    const untouchedRecords = records.filter((item) => {
      const partKey = buildPartKey(item.partType, item.partCode)
      if (!selectedKeys.has(partKey)) {
        return true
      }
      return isTechMode && !isOwnedByCurrentTechnician(item, this.data.currentUser, this.data.role)
    })

    const nextRecords = partCodes.map((partCode) => {
      const partMeta = findPartMeta(partType, partCode)
      if (!partMeta) {
        return null
      }
      const key = buildPartKey(partType, partCode)
      const existing = records.find((item) => {
        if (buildPartKey(item.partType, item.partCode) !== key) {
          return false
        }
        return !isTechMode || isOwnedByCurrentTechnician(item, this.data.currentUser, this.data.role)
      })
      return {
        id: existing && existing.id ? existing.id : buildPartRecordId(),
        partType,
        partTypeLabel: getPartTypeLabel(partType),
        partCode: partMeta.code,
        partLabel: partMeta.label,
        amount: partMeta.amount,
        technicianAccountId,
        technicianAccountName,
        technicianName,
        photos,
        submittedAt: nowText,
      }
    }).filter((item) => Boolean(item))

    if (nextRecords.length === 0) {
      wx.showToast({ title: '施工部位无效', icon: 'none' })
      return
    }

    const patch = {
      status: currentOrder.status === '已取消' ? '已取消' : '未完工',
      workPartRecords: nextRecords.concat(untouchedRecords),
      deliveryStatus: '待交车验收',
      deliveryPassedAt: '',
      commissionStatus: '未生成',
      commissionGeneratedAt: '',
      commissionTotal: 0,
      commissionRecords: [],
    }

    const updatedOrder = await this.patchOrder(patch, {
      syncEvent: 'ORDER_WORK_PART_SAVED',
    })
    if (!updatedOrder) {
      return
    }

    this.setData({
      partTechnicianIndex: -1,
      partForm: {
        ...this.data.partForm,
        partCodes,
        technicianAccountId: this.data.isTechnicianMode ? technicianAccountId : '',
        technicianAccountName: this.data.isTechnicianMode ? technicianAccountName : '',
        technicianName: this.data.isTechnicianMode ? technicianName : '',
        photos: [],
      },
    })

    wx.showToast({
      title: nextRecords.length > 1 ? `已保存 ${nextRecords.length} 个施工部位` : '施工部位记录已保存',
      icon: 'success',
    })
  },

  removeWorkPartRecord(event) {
    if (!this.data.hasOrder) {
      return
    }

    const recordId = String(event.currentTarget.dataset.id || '').trim()
    if (!recordId) {
      return
    }

    const order = normalizeOrder(this.data.order)
    const targetRecord = Array.isArray(order.workPartRecords)
      ? order.workPartRecords.find((item) => item.id === recordId)
      : null

    if (!this.data.isManagerMode && !isOwnedByCurrentTechnician(targetRecord, this.data.currentUser, this.data.role)) {
      wx.showToast({ title: '仅可删除自己的施工记录', icon: 'none' })
      return
    }

    wx.showModal({
      title: '删除该施工记录？',
      content: '删除后该部位不会参与提成计算。',
      success: async (res) => {
        if (!res.confirm) {
          return
        }

        const records = order.workPartRecords.filter((item) => item.id !== recordId)
        const patch = {
          status: order.status === '已取消' ? '已取消' : '未完工',
          workPartRecords: records,
          deliveryStatus: '待交车验收',
          deliveryPassedAt: '',
          commissionStatus: '未生成',
          commissionGeneratedAt: '',
          commissionTotal: 0,
          commissionRecords: [],
        }

        const updatedOrder = await this.patchOrder(patch, {
          syncEvent: 'ORDER_WORK_PART_REMOVED',
        })
        if (!updatedOrder) {
          return
        }

        wx.showToast({ title: '已删除', icon: 'success' })
      }
    })
  },

  chooseConstructionPhotos() {
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)
    wx.chooseImage({
      count: 9,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const selected = Array.isArray(res.tempFilePaths) ? res.tempFilePaths : []
        const current = Array.isArray(order.constructionPhotos) ? order.constructionPhotos : []
        const merged = current.concat(selected).slice(0, 9)
        await this.patchOrder({ constructionPhotos: merged }, { syncEvent: 'ORDER_COMPLETION_PHOTOS_UPLOADED' })
      }
    })
  },

  removeConstructionPhoto(event) {
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)
    const index = Number(event.currentTarget.dataset.index)
    const list = Array.isArray(order.constructionPhotos) ? order.constructionPhotos.slice() : []
    if (index < 0 || index >= list.length) {
      return
    }

    list.splice(index, 1)
    this.patchOrder({ constructionPhotos: list }, { syncEvent: 'ORDER_COMPLETION_PHOTOS_UPDATED' })
  },

  previewConstructionPhoto(event) {
    const index = Number(event.currentTarget.dataset.index)
    const urls = this.data.order && Array.isArray(this.data.order.constructionPhotos)
      ? this.data.order.constructionPhotos
      : []
    const current = urls[index] || ''
    if (!current) {
      return
    }

    wx.previewImage({ current, urls })
  },

  // ── 箱头码照片（单张） ──
  chooseBoxCodePhoto() {
    if (!this.data.hasOrder) return
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const photo = res.tempFilePaths && res.tempFilePaths[0] ? res.tempFilePaths[0] : ''
        if (photo) await this.patchOrder({ boxCodePhoto: photo })
      }
    })
  },

  removeBoxCodePhoto() {
    if (!this.data.hasOrder) return
    this.patchOrder({ boxCodePhoto: '' })
  },

  previewBoxCodePhoto() {
    const url = this.data.order && this.data.order.boxCodePhoto ? this.data.order.boxCodePhoto : ''
    if (url) wx.previewImage({ current: url, urls: [url] })
  },

  // ── 卷芯码照片（单张） ──
  chooseRollNumberPhoto() {
    if (!this.data.hasOrder) return
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const photo = res.tempFilePaths && res.tempFilePaths[0] ? res.tempFilePaths[0] : ''
        if (photo) await this.patchOrder({ rollNumberPhoto: photo })
      }
    })
  },

  removeRollNumberPhoto() {
    if (!this.data.hasOrder) return
    this.patchOrder({ rollNumberPhoto: '' })
  },

  previewRollNumberPhoto() {
    const url = this.data.order && this.data.order.rollNumberPhoto ? this.data.order.rollNumberPhoto : ''
    if (url) wx.previewImage({ current: url, urls: [url] })
  },

  chooseFinalPaymentPhotos() {
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)

    wx.chooseImage({
      count: 9,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const selected = Array.isArray(res.tempFilePaths) ? res.tempFilePaths : []
        const current = Array.isArray(order.finalPaymentPhotos) ? order.finalPaymentPhotos : []
        const merged = current.concat(selected).slice(0, 9)
        const patch = {
          finalPaymentPhotos: merged,
          finalPaymentUploadedAt: merged.length > 0 ? buildTimeText(new Date()) : '',
        }
        await this.patchOrder(patch, { syncEvent: 'ORDER_FINAL_PAYMENT_UPLOADED' })
      }
    })
  },

  removeFinalPaymentPhoto(event) {
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)
    const index = Number(event.currentTarget.dataset.index)
    const list = Array.isArray(order.finalPaymentPhotos) ? order.finalPaymentPhotos.slice() : []
    if (index < 0 || index >= list.length) {
      return
    }

    list.splice(index, 1)
    const nextStatus = list.length > 0 || order.status === '已取消' || order.status !== '已完工'
      ? order.status
      : '未完工'
    const patch = {
      status: nextStatus,
      finalPaymentPhotos: list,
      finalPaymentUploadedAt: list.length > 0 ? (order.finalPaymentUploadedAt || buildTimeText(new Date())) : '',
    }
    this.patchOrder(patch, { syncEvent: 'ORDER_FINAL_PAYMENT_UPDATED' })
  },

  previewFinalPaymentPhoto(event) {
    const index = Number(event.currentTarget.dataset.index)
    const urls = this.data.order && Array.isArray(this.data.order.finalPaymentPhotos)
      ? this.data.order.finalPaymentPhotos
      : []
    const current = urls[index] || ''
    if (!current) {
      return
    }

    wx.previewImage({ current, urls })
  },

  async confirmDeliveryAndGenerate() {
    if (!this.data.hasOrder || this.data.generatingCommission) {
      return
    }
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可生成提成', icon: 'none' })
      return
    }

    const order = normalizeOrder(this.data.order)
    if (order.status === '已取消') {
      wx.showToast({ title: '已取消订单不能生成提成', icon: 'none' })
      return
    }

    const records = dedupeWorkPartRecords(order.workPartRecords)
    if (records.length === 0) {
      wx.showToast({ title: '请先提交施工部位记录', icon: 'none' })
      return
    }

    const commissionRecords = records.map((item) => {
      const technicianAccountId = item.technicianAccountId || getTechnicianAccountIdByName(item.technicianName)
      const technicianName = getTechnicianDisplayName(technicianAccountId, item.technicianName || item.technicianAccountName)
      return {
        id: item.id,
        partType: item.partType,
        partTypeLabel: item.partTypeLabel || getPartTypeLabel(item.partType),
        partCode: item.partCode,
        partLabel: item.partLabel,
        technicianAccountId,
        technicianAccountName: technicianName,
        technicianName,
        amount: getPartAmount(item.partType, item.partCode),
        submittedAt: item.submittedAt || '',
        photos: sanitizePhotos(item.photos),
      }
    }).filter((item) => item.amount > 0 && item.technicianAccountId)

    if (commissionRecords.length === 0) {
      wx.showToast({ title: '无有效施工提成记录', icon: 'none' })
      return
    }

    if (!Array.isArray(order.finalPaymentPhotos) || order.finalPaymentPhotos.length === 0) {
      wx.showToast({ title: '请先上传尾款凭证', icon: 'none' })
      return
    }

    const nowText = buildTimeText(new Date())
    const total = commissionRecords.reduce((sum, item) => sum + item.amount, 0)
    const patch = {
      status: order.status === '已取消' ? '已取消' : (order.status === '已完工' ? '已完工' : '未完工'),
      workPartRecords: records,
      deliveryStatus: '交车通过',
      deliveryPassedAt: nowText,
      commissionStatus: '已生成',
      commissionGeneratedAt: nowText,
      commissionTotal: total,
      commissionRecords,
    }

    this.setData({ generatingCommission: true })
    const updatedOrder = await this.patchOrder(patch, { syncEvent: 'ORDER_DELIVERY_CONFIRMED' })
    this.setData({ generatingCommission: false })
    if (!updatedOrder) {
      return
    }

    wx.showToast({
      title: order.commissionStatus === '已生成' ? '提成已重新生成' : '交车通过，提成已生成',
      icon: 'success',
    })
  },

  async confirmOrderCompleted() {
    if (!this.data.hasOrder) {
      return
    }
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可确认完工', icon: 'none' })
      return
    }

    const order = normalizeOrder(this.data.order)
    if (!order || order.status === '已取消') {
      wx.showToast({ title: '已取消订单不能完工', icon: 'none' })
      return
    }
    if (!Array.isArray(order.finalPaymentPhotos) || order.finalPaymentPhotos.length === 0) {
      wx.showToast({ title: '请先上传尾款凭证', icon: 'none' })
      return
    }
    if (order.deliveryStatus !== '交车通过' || order.commissionStatus !== '已生成') {
      wx.showToast({ title: '请先确认交车通过并生成提成', icon: 'none' })
      return
    }
    if (!canConfirmOrderCompleted(order)) {
      wx.showToast({ title: '当前状态暂不可确认完工', icon: 'none' })
      return
    }
    if (order.status === '已完工') {
      wx.showToast({ title: '订单已完工', icon: 'none' })
      return
    }

    const updatedOrder = await this.patchOrder({ status: '已完工' }, { syncEvent: 'ORDER_COMPLETED' })
    if (!updatedOrder) {
      return
    }

    wx.showToast({ title: '已确认完工', icon: 'success' })
  },

  syncFinanceNow() {
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可同步财务', icon: 'none' })
      return
    }
    if (!this.data.hasOrder) {
      return
    }

    this.trySyncFinance(this.data.order, 'MANUAL_RETRY', true)
  },

  async trySyncFinance(order, eventType, showToast) {
    if (!order || !order.id || this.data.financeSyncLoading || !this.data.hasOrder) {
      return
    }

    this.setData({ financeSyncLoading: true })

    try {
      const result = await syncOrderToFinance({
        order,
        eventType,
        source: 'MINIPROGRAM_ORDER_DETAIL',
      })

      const patch = buildFinancePatch(result, eventType)
      const updated = await storeApi.updateOrder(order.id, {
        version: this.data.order.version,
        ...patch,
      })
      this.refreshOrderView(normalizeOrder(updated))

      if (showToast) {
        wx.showToast({
          title: getFinanceToastText(result),
          icon: result.ok ? 'success' : 'none',
        })
      }
    } catch (error) {
      if (showToast) {
        wx.showToast({ title: normalizeErrorMessage(error, '财务同步失败'), icon: 'none' })
      }
    }

    this.setData({ financeSyncLoading: false })
  },

  cancelOrder() {
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可取消订单', icon: 'none' })
      return
    }
    if (!this.data.hasOrder) {
      return
    }

    const order = normalizeOrder(this.data.order)
    if (order.status === '已取消') {
      wx.showToast({ title: '订单已取消', icon: 'none' })
      return
    }

    wx.showModal({
      title: '确认取消订单吗？',
      content: '取消后需要重新下单，已支付定金请联系客服处理。',
      success: async (res) => {
        if (!res.confirm) {
          return
        }

        const updatedOrder = await this.patchOrder({ status: '已取消' }, { syncEvent: 'ORDER_CANCELLED' })
        if (!updatedOrder) {
          return
        }

        wx.showToast({ title: '已取消', icon: 'success' })
      }
    })
  },

  createNewOrder() {
    wx.navigateTo({ url: '/subpackages/store/pages/film-order/index' })
  },

  editOrder() {
    if (!this.data.isManagerMode) {
      wx.showToast({ title: '仅最高权限可编辑订单', icon: 'none' })
      return
    }
    if (!this.data.hasOrder || !this.data.order || !this.data.order.id) {
      return
    }

    wx.navigateTo({ url: `/subpackages/store/pages/order-edit/index?id=${this.data.order.id}` })
  },

  goWashDetail() {
    if (!this.data.hasOrder || !this.data.order || !this.data.order.id) {
      return
    }
    wx.navigateTo({ url: `/subpackages/store/pages/wash-order-detail/index?id=${this.data.order.id}` })
  },

  syncPartPicker(partType, partCodes) {
    const safePartType = getSafePartType(partType)
    const basePartOptions = getPartOptions(safePartType)
    const partTypeIndex = Math.max(0, PART_TYPE_OPTIONS.findIndex((item) => item.value === safePartType))
    const validCodeSet = new Set(basePartOptions.map((item) => item.code))
    const normalizedPartCodes = sanitizeStringList(partCodes).filter((code) => validCodeSet.has(code))
    const defaultCodes = normalizedPartCodes.length > 0
      ? normalizedPartCodes
      : (basePartOptions[0] ? [basePartOptions[0].code] : [])

    const partOptions = basePartOptions.map((item) => ({
      ...item,
      checked: defaultCodes.indexOf(item.code) >= 0,
    }))

    this.setData({
      partTypeIndex,
      partOptions,
      'partForm.partType': safePartType,
      'partForm.partCodes': defaultCodes,
    })
  },
})

function normalizePriceSummary(priceSummary) {
  const summary = priceSummary || {}
  const packagePrice = toNumber(summary.packagePrice, toNumber(summary.brandPrice, 0))
  const addOnFee = toNumber(summary.addOnFee, 0)
  const totalPrice = toNumber(summary.totalPrice, packagePrice + addOnFee)
  const deposit = toNumber(summary.deposit, Math.round(totalPrice * 0.1))

  return {
    packagePrice,
    addOnFee,
    totalPrice,
    deposit,
  }
}

function toNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function buildCurrentUser(role, sessionUser) {
  const source = sessionUser && typeof sessionUser === 'object' ? sessionUser : {}
  const normalizedRole = normalizeRole(role || source.role)
  const accountId = normalizeText(source.username || source.sales_id)
  const accountName = normalizeText(source.name || source.sales_name || wx.getStorageSync('sales_name'))
  return {
    role: normalizedRole,
    roleLabel: getRoleLabel(normalizedRole),
    accountId,
    accountName,
  }
}

function getRoleLabel(role) {
  const target = normalizeRole(role)
  if (target === 'manager') {
    return '最高权限'
  }
  if (target === 'sales') {
    return '销售账号'
  }
  if (target === 'finance') {
    return '财务账号'
  }
  return '施工账号'
}

function normalizeRole(value) {
  return normalizeText(value).toLowerCase() || 'sales'
}

function buildFinancePatch(result, eventType) {
  const now = buildTimeText(new Date())

  if (result && result.ok) {
    return {
      financeSyncStatus: '已同步',
      financeSyncAt: now,
      financeSyncMessage: result.message || '同步成功',
      financeExternalId: result.externalId || '',
      financeLastEvent: eventType,
    }
  }

  if (result && result.skipped) {
    return {
      financeSyncStatus: '未启用',
      financeSyncAt: now,
      financeSyncMessage: result.message || '未启用同步',
      financeLastEvent: eventType,
    }
  }

  return {
    financeSyncStatus: '同步失败',
    financeSyncAt: now,
    financeSyncMessage: (result && result.message) || '同步失败',
    financeLastEvent: eventType,
  }
}

function getFinanceToastText(result) {
  if (result && result.ok) {
    return '财务同步成功'
  }
  if (result && result.skipped) {
    return '财务同步未启用'
  }
  return '财务同步失败'
}

function buildTimeText(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function buildPartRecordId() {
  const random = Math.floor(Math.random() * 9000) + 1000
  return `WPR${Date.now()}${random}`
}

function getSafePartType(value) {
  const matched = PART_TYPE_OPTIONS.find((item) => item.value === value)
  return matched ? matched.value : PART_TYPE_OPTIONS[0].value
}

function getPartTypeLabel(value) {
  const matched = PART_TYPE_OPTIONS.find((item) => item.value === value)
  return matched ? matched.label : PART_TYPE_OPTIONS[0].label
}

function getPartOptions(partType) {
  const safeType = getSafePartType(partType)
  return Array.isArray(PART_RULES[safeType]) ? PART_RULES[safeType] : []
}

function findPartMeta(partType, partCode) {
  const options = getPartOptions(partType)
  return options.find((item) => item.code === partCode) || null
}

function getPartAmount(partType, partCode) {
  const matched = findPartMeta(partType, partCode)
  return matched ? toNumber(matched.amount, 0) : 0
}

function getTechnicianAccountIdByName(name) {
  const matched = findTechnicianAccountByName(name)
  return matched ? matched.id : ''
}

function getTechnicianDisplayName(accountId, fallbackName) {
  const matchedById = findTechnicianAccountById(accountId)
  if (matchedById) {
    return matchedById.name
  }
  const matchedByName = findTechnicianAccountByName(fallbackName)
  if (matchedByName) {
    return matchedByName.name
  }
  return normalizeText(fallbackName)
}

function getActiveTechnicianProfile(userContext, role) {
  if (normalizeRole(role) !== 'technician') {
    return null
  }

  const accountId = normalizeText(userContext && userContext.accountId)
  if (!accountId) {
    return null
  }

  const matched = findTechnicianAccountById(accountId)
  if (matched) {
    return { id: matched.id, name: matched.name }
  }

  const fallbackName = normalizeText(userContext && userContext.accountName)
  if (!fallbackName) {
    return null
  }

  return { id: accountId, name: fallbackName }
}

function isOwnedByCurrentTechnician(record, userContext, role) {
  if (!record || typeof record !== 'object') {
    return false
  }
  if (normalizeRole(role) === 'manager') {
    return true
  }
  if (normalizeRole(role) !== 'technician') {
    return false
  }

  const userAccountId = normalizeText(userContext && userContext.accountId)
  const userName = normalizeText(userContext && userContext.accountName)
  const recordAccountId = normalizeText(record.technicianAccountId)
  const recordName = normalizeText(record.technicianName || record.technicianAccountName)

  if (userAccountId && recordAccountId && userAccountId === recordAccountId) {
    return true
  }

  return Boolean(userName && recordName && userName === recordName)
}

function canConfirmOrderCompleted(order) {
  if (!order || typeof order !== 'object' || order.status === '已取消') {
    return false
  }
  if (order.status === '已完工') {
    return false
  }
  if (!Array.isArray(order.finalPaymentPhotos) || order.finalPaymentPhotos.length === 0) {
    return false
  }
  if (order.deliveryStatus !== '交车通过') {
    return false
  }
  if (order.commissionStatus !== '已生成') {
    return false
  }
  return true
}

function buildOrderPermissionState(order, userContext, role) {
  const isManagerMode = normalizeRole(role) === 'manager'
  const isTechnicianMode = normalizeRole(role) === 'technician'
  const normalized = normalizeOrder(order)
  const commissionRecords = normalized ? normalizeCommissionRecords(normalized.commissionRecords) : []
  const displayedCommissionRecords = isTechnicianMode
    ? commissionRecords.filter((item) => isOwnedByCurrentTechnician(item, userContext, role))
    : commissionRecords
  const displayedCommissionTotal = displayedCommissionRecords.reduce((sum, item) => sum + toNumber(item.amount, 0), 0)

  return {
    isManagerMode,
    isTechnicianMode,
    canSubmitWorkPart: isManagerMode || isTechnicianMode,
    canCompleteOrder: isManagerMode && canConfirmOrderCompleted(normalized),
    displayedCommissionRecords,
    displayedCommissionTotal,
  }
}

function sanitizePhotos(photos) {
  if (!Array.isArray(photos)) {
    return []
  }

  return photos
    .map((item) => String(item || '').trim())
    .filter((item) => item)
}

function sanitizeSinglePhoto(photo) {
  if (typeof photo !== 'string') {
    return ''
  }
  return photo.trim()
}

function normalizeWorkPartRecords(records) {
  if (!Array.isArray(records)) {
    return []
  }

  return records.map((item) => {
    const safePartType = getSafePartType(item && item.partType)
    const safePartCode = item && item.partCode ? String(item.partCode) : ''
    const partMeta = findPartMeta(safePartType, safePartCode)
    const label = partMeta ? partMeta.label : (item && item.partLabel ? String(item.partLabel) : '')
    const amount = partMeta ? partMeta.amount : toNumber(item && item.amount, 0)
    const technicianName = normalizeText(item && item.technicianName)
    const technicianAccountId = normalizeText(item && item.technicianAccountId) || getTechnicianAccountIdByName(technicianName)
    const technicianAccountName = getTechnicianDisplayName(
      technicianAccountId,
      item && item.technicianAccountName ? String(item.technicianAccountName) : technicianName
    )
    const normalizedTechnicianName = technicianAccountName || technicianName

    return {
      id: item && item.id ? String(item.id) : buildPartRecordId(),
      partType: safePartType,
      partTypeLabel: getPartTypeLabel(safePartType),
      partCode: partMeta ? partMeta.code : safePartCode,
      partLabel: label,
      amount,
      technicianAccountId,
      technicianAccountName,
      technicianName: normalizedTechnicianName,
      photos: sanitizePhotos(item && item.photos),
      submittedAt: item && item.submittedAt ? String(item.submittedAt) : '',
    }
  }).filter((item) => item.partCode && item.partLabel)
}

function dedupeWorkPartRecords(records) {
  const normalized = normalizeWorkPartRecords(records)
  const map = {}
  normalized.forEach((item) => {
    map[buildPartKey(item.partType, item.partCode)] = item
  })

  return Object.keys(map).map((key) => map[key])
}

function normalizeCommissionRecords(records) {
  if (!Array.isArray(records)) {
    return []
  }

  return records.map((item) => {
    const safePartType = getSafePartType(item && item.partType)
    const safePartCode = item && item.partCode ? String(item.partCode) : ''
    const partMeta = findPartMeta(safePartType, safePartCode)
    const technicianName = normalizeText(item && item.technicianName)
    const technicianAccountId = normalizeText(item && item.technicianAccountId) || getTechnicianAccountIdByName(technicianName)
    const technicianAccountName = getTechnicianDisplayName(
      technicianAccountId,
      item && item.technicianAccountName ? String(item.technicianAccountName) : technicianName
    )
    const normalizedTechnicianName = technicianAccountName || technicianName

    return {
      id: item && item.id ? String(item.id) : buildPartRecordId(),
      partType: safePartType,
      partTypeLabel: getPartTypeLabel(safePartType),
      partCode: partMeta ? partMeta.code : safePartCode,
      partLabel: partMeta ? partMeta.label : (item && item.partLabel ? String(item.partLabel) : ''),
      technicianAccountId,
      technicianAccountName,
      technicianName: normalizedTechnicianName,
      amount: toNumber(item && item.amount, partMeta ? partMeta.amount : 0),
      submittedAt: item && item.submittedAt ? String(item.submittedAt) : '',
      photos: sanitizePhotos(item && item.photos),
    }
  }).filter((item) => item.partCode || item.partLabel)
}

function buildPartKey(partType, partCode) {
  return `${getSafePartType(partType)}::${String(partCode || '')}`
}

function getDispatchState(order, workBayOptions, technicianOptions) {
  const options = Array.isArray(workBayOptions) && workBayOptions.length > 0
    ? workBayOptions
    : ['1号工位']
  const technicians = Array.isArray(technicianOptions) && technicianOptions.length > 0
    ? technicianOptions
    : []
  const dispatch = normalizeDispatchInfo(order && order.dispatchInfo)
  const fallbackDate = order && order.appointmentDate ? String(order.appointmentDate) : ''
  const fallbackTime = order && order.appointmentTime ? String(order.appointmentTime) : '10:00'
  const workBay = dispatch.workBay && options.indexOf(dispatch.workBay) >= 0
    ? dispatch.workBay
    : options[0]
  const bayIndex = Math.max(0, options.indexOf(workBay))
  const technicianNames = dispatch.technicianNames.filter((name) => technicians.indexOf(name) >= 0)

  return {
    bayIndex,
    form: {
      date: dispatch.date || fallbackDate,
      time: dispatch.time || fallbackTime,
      workBay,
      technicianNames,
      remark: dispatch.remark || '',
    }
  }
}

function normalizeDispatchInfo(dispatchInfo) {
  const raw = dispatchInfo && typeof dispatchInfo === 'object' ? dispatchInfo : {}
  const date = normalizeDateText(raw.date)
  const time = normalizeTimeText(raw.time)
  const workBay = normalizeText(raw.workBay)
  const technicianNames = normalizeTechnicianNames(
    Array.isArray(raw.technicianNames) && raw.technicianNames.length > 0
      ? raw.technicianNames
      : raw.technicianName
  )
  const technicianName = technicianNames[0] || ''
  const remark = normalizeText(raw.remark)
  const updatedAt = normalizeText(raw.updatedAt)

  return {
    date,
    time,
    workBay,
    technicianName,
    technicianNames,
    technicianDisplay: technicianNames.length > 0 ? technicianNames.join(' / ') : '',
    remark,
    updatedAt,
  }
}

function validateDispatchInfo(dispatch) {
  if (!dispatch.date) {
    return '请选择派工日期'
  }
  if (!dispatch.time) {
    return '请选择派工时间'
  }
  if (!dispatch.workBay) {
    return '请选择工位'
  }
  if (!Array.isArray(dispatch.technicianNames) || dispatch.technicianNames.length === 0) {
    return '请选择派工技师'
  }
  return ''
}

function findDispatchConflict(orderId, dispatch, orders) {
  const list = Array.isArray(orders) ? orders : []
  const targetDate = dispatch.date
  const targetTime = dispatch.time
  const targetBay = dispatch.workBay
  const targetTechnicians = Array.isArray(dispatch.technicianNames) ? dispatch.technicianNames : []

  for (let i = 0; i < list.length; i += 1) {
    const item = list[i]
    if (!item || item.id === orderId || item.status === '已取消') {
      continue
    }

    const itemDispatch = getOrderDispatchSnapshot(item)
    if (!itemDispatch.date || !itemDispatch.time) {
      continue
    }
    if (itemDispatch.date !== targetDate) {
      continue
    }

    if (targetBay && itemDispatch.workBay && itemDispatch.workBay === targetBay) {
      return `同日期同工位冲突：${item.id}（${item.customerName || '未知客户'}）`
    }

    if (
      targetTime
      && itemDispatch.time === targetTime
      && targetTechnicians.length > 0
      && itemDispatch.technicianNames.length > 0
      && hasIntersection(targetTechnicians, itemDispatch.technicianNames)
    ) {
      return `同时间同技师冲突：${item.id}（${item.customerName || '未知客户'}）`
    }
  }

  return ''
}

function findDailyCapacityConflict(orderId, order, dispatch, orders, limit) {
  const capacityStatus = getDailyCapacityStatus({
    orders,
    date: dispatch && dispatch.date,
    store: order && order.store,
    excludeOrderId: orderId,
    limit,
  })
  const wasScheduledOnTarget = isOrderScheduledOn(order, dispatch && dispatch.date, order && order.store)

  if (capacityStatus.full && !wasScheduledOnTarget) {
    return getDailyCapacityMessage(capacityStatus)
  }

  return ''
}

function getOrderDispatchSnapshot(order) {
  const dispatch = order && order.dispatchInfo && typeof order.dispatchInfo === 'object'
    ? order.dispatchInfo
    : {}
  const date = normalizeDateText(dispatch.date || (order && order.appointmentDate))
  const time = normalizeTimeText(dispatch.time || (order && order.appointmentTime))
  const workBay = normalizeText(dispatch.workBay)
  const technicianNames = normalizeTechnicianNames(
    Array.isArray(dispatch.technicianNames) && dispatch.technicianNames.length > 0
      ? dispatch.technicianNames
      : dispatch.technicianName
  )
  const technicianName = technicianNames[0] || ''

  return {
    date,
    time,
    workBay,
    technicianName,
    technicianNames,
  }
}

function normalizeDateText(value) {
  const text = normalizeText(value)
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : ''
}

function normalizeTimeText(value) {
  const text = normalizeText(value)
  return /^\d{2}:\d{2}$/.test(text) ? text : ''
}

function normalizeText(value) {
  return String(value || '').trim()
}

function sanitizeStringList(list) {
  if (!Array.isArray(list)) {
    return []
  }

  return list
    .map((item) => normalizeText(item))
    .filter((item) => item)
}

function normalizeTechnicianNames(value) {
  if (Array.isArray(value)) {
    return sanitizeStringList(value)
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

function hasIntersection(sourceA, sourceB) {
  const set = new Set(Array.isArray(sourceA) ? sourceA : [])
  const list = Array.isArray(sourceB) ? sourceB : []
  for (let i = 0; i < list.length; i += 1) {
    if (set.has(list[i])) {
      return true
    }
  }
  return false
}

function buildTechnicianCheckOptions(selectedNames, technicianOptions) {
  const selectedSet = new Set(sanitizeStringList(selectedNames))
  const source = Array.isArray(technicianOptions) ? technicianOptions : []
  return source.map((name) => ({
    name,
    checked: selectedSet.has(name),
  }))
}

function normalizeOrder(order) {
  if (!order || typeof order !== 'object') {
    return null
  }

  return {
    ...order,
    workPartRecords: dedupeWorkPartRecords(order.workPartRecords),
    commissionRecords: normalizeCommissionRecords(order.commissionRecords),
    vinPhoto: sanitizeSinglePhoto(order.vinPhoto),
    constructionPhotos: sanitizePhotos(order.constructionPhotos),
    boxCodePhoto: sanitizeSinglePhoto(order.boxCodePhoto),
    rollNumberPhoto: sanitizeSinglePhoto(order.rollNumberPhoto),
    damagePhotos: sanitizePhotos(order.damagePhotos),
    dispatchInfo: normalizeDispatchInfo(order.dispatchInfo),
    deliveryStatus: order.deliveryStatus || '待交车验收',
    deliveryPassedAt: order.deliveryPassedAt || '',
    commissionStatus: order.commissionStatus || '未生成',
    commissionGeneratedAt: order.commissionGeneratedAt || '',
    commissionTotal: toNumber(order.commissionTotal, 0),
    depositProofPhotos: sanitizePhotos(order.depositProofPhotos),
    finalPaymentPhotos: sanitizePhotos(order.finalPaymentPhotos),
    finalPaymentUploadedAt: order.finalPaymentUploadedAt || '',
    financeSyncStatus: normalizeText(order.financeSyncStatus),
    financeSyncAt: normalizeText(order.financeSyncAt),
    financeSyncMessage: normalizeText(order.financeSyncMessage),
    financeExternalId: normalizeText(order.financeExternalId),
    financeLastEvent: normalizeText(order.financeLastEvent),
    cuttingFee: order.cuttingFee && typeof order.cuttingFee === 'object' ? order.cuttingFee : null,
  }
}
