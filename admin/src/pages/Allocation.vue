<template>
  <div class="page">
    <h2>分配管理</h2>
    <p class="desc">该页面用于展示销售分配规则与当前状态，便于后续接入自动分配策略。</p>

    <el-alert
      title="当前为基础占位页"
      type="info"
      show-icon
      :closable="false"
    />

    <el-card class="card">
      <template #header>
        <span>建议接入项</span>
      </template>
      <ul>
        <li>账号维度分配优先级</li>
        <li>门店轮转规则</li>
        <li>SLA 超时二次分派</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
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

.card {
  margin-top: 16px;
}

ul {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
  color: #3d4148;
}
</style>
