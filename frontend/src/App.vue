<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth } from './health'
const status = ref('正在检查后端…')
onMounted(async () => {
  try { status.value = await getHealth() }
  catch (error) { status.value = `连接失败：${error instanceof Error ? error.message : String(error)}` }
})
</script>
<template>
  <main>
    <p class="label">STANDALONE 02 · INITIAL ENVIRONMENT</p>
    <h1>计算机组成原理实验台</h1>
    <p>Vue + TypeScript / Python + FastAPI</p>
    <section aria-label="环境状态"><h2>初始工程已启动</h2><p role="status">{{ status }}</p></section>
    <p class="note">当前仅提供运行环境，算法分析与可视化功能尚未实现。</p>
  </main>
</template>
<style>
body{margin:0;background:#f4f6fa;color:#182331;font:16px/1.7 system-ui,sans-serif}main{max-width:800px;margin:10vh auto;padding:32px}.label{color:#546b82;font-size:13px;letter-spacing:2px}h1{font-size:38px}section{background:white;border:1px solid #dce3eb;border-radius:12px;padding:20px 28px;margin:32px 0}.note{color:#627183}
</style>
