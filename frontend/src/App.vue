<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth } from './health'
import { AnalysisRequestError, countOperations } from './analysis'

const status = ref('正在检查后端…')
onMounted(async () => {
  try { status.value = await getHealth() }
  catch (error) { status.value = `连接失败：${error instanceof Error ? error.message : String(error)}` }
})

const nInput = ref('100')
const programInput = ref(JSON.stringify({ type: 'triangle' }, null, 2))
const result = ref('')
const errorText = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  result.value = ''
  errorText.value = ''
  let program: unknown
  try {
    program = JSON.parse(programInput.value)
  }
  catch {
    errorText.value = 'program 不是合法 JSON，请检查后重试'
    return
  }
  busy.value = true
  try {
    result.value = await countOperations(nInput.value.trim(), program)
  }
  catch (error) {
    if (error instanceof AnalysisRequestError) {
      errorText.value = `拒绝：${error.code}（路径 ${error.path}）`
    }
    else {
      errorText.value = error instanceof Error ? error.message : String(error)
    }
  }
  finally {
    busy.value = false
  }
}
</script>
<template>
  <main>
    <p class="label">STANDALONE 01 · INITIAL ENVIRONMENT</p>
    <h1>数据结构实验台</h1>
    <p>Vue + TypeScript / Python + FastAPI</p>
    <section aria-label="环境状态"><h2>初始工程已启动</h2><p role="status">{{ status }}</p></section>

    <section aria-label="操作计数">
      <h2>程序操作计数 POST /api/analysis/count</h2>
      <div class="field">
        <label for="n-input">n（十进制字符串，1..10¹⁸）</label>
        <input id="n-input" v-model="nInput" inputmode="numeric" spellcheck="false">
      </div>
      <div class="field">
        <label for="program-input">program（op / seq / repeat / double / triangle，可嵌套）</label>
        <textarea id="program-input" v-model="programInput" rows="8" spellcheck="false"></textarea>
      </div>
      <button type="button" :disabled="busy" @click="submit">
        {{ busy ? '计算中…' : '计算 count' }}
      </button>
      <p v-if="result" class="result" role="status">count = {{ result }}</p>
      <p v-if="errorText" class="error" role="alert">{{ errorText }}</p>
    </section>
  </main>
</template>
<style>
body{margin:0;background:#f4f6fa;color:#182331;font:16px/1.7 system-ui,sans-serif}main{max-width:800px;margin:10vh auto;padding:32px}.label{color:#546b82;font-size:13px;letter-spacing:2px}h1{font-size:38px}section{background:white;border:1px solid #dce3eb;border-radius:12px;padding:20px 28px;margin:32px 0}.field{display:flex;flex-direction:column;gap:6px;margin:14px 0}label{font-weight:600}input,textarea{font:14px/1.6 ui-monospace,Consolas,monospace;padding:8px 10px;border:1px solid #c4cfdb;border-radius:8px;background:#fbfdff}textarea{resize:vertical}button{font-size:15px;padding:8px 18px;border:0;border-radius:8px;background:#2563eb;color:white;cursor:pointer}button:disabled{opacity:.6;cursor:default}.result{font:600 18px/1.6 ui-monospace,Consolas,monospace;color:#15803d;word-break:break-all}.error{color:#b91c1c}
</style>
