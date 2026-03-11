<template>
  <div class="page">
    <h2>销售统计</h2>

    <div class="filters">
      <el-select v-model="storeCode" placeholder="选择门店" style="width: 160px">
        <el-option label="BOP店" value="BOP" />
        <el-option label="龙膜店" value="LM" />
      </el-select>
      <el-select v-model="days" placeholder="统计天数" style="width: 140px">
        <el-option label="7 天" :value="7" />
        <el-option label="15 天" :value="15" />
        <el-option label="30 天" :value="30" />
      </el-select>
      <el-button type="primary" @click="loadData">查询</el-button>
    </div>

    <el-table :data="rows" stripe>
      <el-table-column prop="sales_name" label="销售" min-width="140" />
      <el-table-column prop="assigned_count" label="分配数" width="120" />
      <el-table-column prop="first_reply_count" label="首响数" width="120" />
      <el-table-column prop="first_reply_rate" label="首响率" width="120">
        <template #default="{ row }">{{ Number(row.first_reply_rate || 0).toFixed(1) }}%</template>
      </el-table-column>
      <el-table-column prop="wechat_success_count" label="微信成功数" width="140" />
      <el-table-column prop="wechat_success_rate" label="微信成功率" width="140">
        <template #default="{ row }">{{ Number(row.wechat_success_rate || 0).toFixed(1) }}%</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { statsApi } from '../utils/api'

const storeCode = ref('BOP')
const days = ref(7)
const rows = ref([])

async function loadData() {
  try {
    const data = await statsApi.bySales({ store_code: storeCode.value, days: days.value })
    rows.value = data?.sales || []
  } catch (error) {
    rows.value = []
    ElMessage.error('加载销售统计失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.page {
  padding: 20px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
</style>
