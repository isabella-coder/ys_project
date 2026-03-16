<template>
  <div class="page">
    <h2>线索详情</h2>
    <p class="desc">线索 ID: {{ leadId }}</p>

    <el-descriptions v-if="detail" :column="2" border>
      <el-descriptions-item label="线索ID">{{ detail.lead_id }}</el-descriptions-item>
      <el-descriptions-item label="平台">{{ detail.platform }}</el-descriptions-item>
      <el-descriptions-item label="客户">{{ detail.customer_nickname || '-' }}</el-descriptions-item>
      <el-descriptions-item label="车型">{{ detail.car_model || '-' }}</el-descriptions-item>
      <el-descriptions-item label="服务类型">{{ detail.service_type || '-' }}</el-descriptions-item>
      <el-descriptions-item label="门店">{{ detail.store_code || '-' }}</el-descriptions-item>
      <el-descriptions-item label="分配销售">{{ detail.assigned_to || '-' }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ detail.status || '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-empty v-else description="暂无可展示的线索详情" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { leadApi } from '../utils/api'

const route = useRoute()
const leadId = computed(() => route.params.id)
const detail = ref(null)

onMounted(async () => {
  if (!leadId.value) return
  try {
    detail.value = await leadApi.get(leadId.value)
  } catch (error) {
    detail.value = null
    ElMessage.error('加载线索详情失败')
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
