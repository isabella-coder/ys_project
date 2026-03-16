<template>
  <div class="page">
    <h2>账号管理</h2>
    <p class="desc">展示可用账号列表，用于联调与基础管理。</p>

    <el-table :data="accounts" stripe>
      <el-table-column prop="account_code" label="账号编码" min-width="180" />
      <el-table-column prop="platform" label="平台" width="120" />
      <el-table-column prop="store_code" label="门店" width="120" />
      <el-table-column prop="status" label="状态" width="120" />
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '../utils/api'

const accounts = ref([])

onMounted(async () => {
  try {
    const data = await accountApi.list({ page: 1, page_size: 50 })
    accounts.value = data?.items || []
  } catch (error) {
    // Backend may not expose account endpoints in this stage.
    accounts.value = []
    ElMessage.warning('账号接口暂不可用，当前显示空数据')
  }
})
</script>

<style scoped>
.page {
  padding: 4px;
}

.desc {
  margin-bottom: 16px;
  color: #6b7280;
  font-size: 14px;
}
</style>
