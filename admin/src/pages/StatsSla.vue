<template>
  <div class="page">
    <h2>SLA 统计</h2>

    <div class="filters">
      <el-date-picker v-model="statDate" type="date" placeholder="选择日期" />
      <el-select v-model="storeCode" placeholder="门店" clearable style="width: 160px">
        <el-option label="BOP店" value="BOP" />
        <el-option label="龙膜店" value="LM" />
      </el-select>
      <el-button type="primary" @click="loadData">查询</el-button>
    </div>

    <div class="cards">
      <el-card>
        <template #header>1 分钟 SLA</template>
        <p>通过: {{ sla1.pass }}</p>
        <p>失败: {{ sla1.fail }}</p>
        <p>通过率: {{ Number(sla1.pass_rate || 0).toFixed(1) }}%</p>
      </el-card>
      <el-card>
        <template #header>3 分钟 SLA</template>
        <p>通过: {{ sla3.pass }}</p>
        <p>失败: {{ sla3.fail }}</p>
        <p>通过率: {{ Number(sla3.pass_rate || 0).toFixed(1) }}%</p>
      </el-card>
      <el-card>
        <template #header>10 分钟 SLA</template>
        <p>通过: {{ sla10.pass }}</p>
        <p>失败: {{ sla10.fail }}</p>
        <p>通过率: {{ Number(sla10.pass_rate || 0).toFixed(1) }}%</p>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { statsApi } from '../utils/api'

const statDate = ref(new Date())
const storeCode = ref('')
const sla1 = ref({ pass: 0, fail: 0, pass_rate: 0 })
const sla3 = ref({ pass: 0, fail: 0, pass_rate: 0 })
const sla10 = ref({ pass: 0, fail: 0, pass_rate: 0 })

async function loadData() {
  try {
    const date = statDate.value.toISOString().slice(0, 10)
    const data = await statsApi.sla({ stat_date: date, store_code: storeCode.value || null })
    sla1.value = data?.sla_1m || sla1.value
    sla3.value = data?.sla_3m || sla3.value
    sla10.value = data?.sla_10m || sla10.value
  } catch (error) {
    ElMessage.error('加载 SLA 统计失败')
  }
}

loadData()
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

.cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 12px;
}
</style>
