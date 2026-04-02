<template>
  <div class="home">
    <a-card title="欢迎使用客户运营中台">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-statistic title="客户总数" :value="1286" />
        </a-col>
        <a-col :span="8">
          <a-statistic title="本月消耗" :value="256.8" :precision="2" suffix="万元" />
        </a-col>
        <a-col :span="8">
          <a-statistic title="待处理事项" :value="12" />
        </a-col>
      </a-row>
    </a-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home {
  padding: 20px;
}
</style>
