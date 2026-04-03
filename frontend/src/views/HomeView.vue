<template>
  <div class="page-stack">
    <section class="hero-panel surface-card">
      <div class="hero-copy">
        <span class="section-kicker">Architecture Starter</span>
        <h1>把“能聊”做成“能落地”的 AI 恋爱智能体工程</h1>
        <p>
          当前骨架围绕陪伴、建议、风格复刻、长期记忆与安全治理展开，先把目录边界、联调链路和基础设施位搭稳，再逐步填业务。
        </p>

        <div class="hero-actions">
          <RouterLink to="/workbench">
            <a-button type="primary" size="large">进入联调工作台</a-button>
          </RouterLink>
          <a-tag :color="healthTagColor">{{ healthText }}</a-tag>
        </div>
      </div>

      <div class="hero-side">
        <div class="metric-card">
          <div class="metric-label">前端</div>
          <div class="metric-value">Vue 3 + Vite + Ant Design Vue</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">后端</div>
          <div class="metric-value">FastAPI + Pydantic v2 + LangGraph</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">基础盘</div>
          <div class="metric-value">Memory / RAG / Safety / Prompt / Task</div>
        </div>
      </div>
    </section>

    <section class="content-grid">
      <a-card title="核心模块" class="surface-card">
        <a-row :gutter="[16, 16]">
          <a-col v-for="item in moduleCards" :key="item.title" :xs="24" :md="12">
            <div class="module-card">
              <div class="module-name">{{ item.title }}</div>
              <div class="module-desc">{{ item.description }}</div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <a-card title="主流程" class="surface-card">
        <a-timeline>
          <a-timeline-item v-for="step in flowSteps" :key="step">{{ step }}</a-timeline-item>
        </a-timeline>
      </a-card>
    </section>

    <section class="content-grid">
      <a-card title="当前落地说明" class="surface-card">
        <ul class="plain-list">
          <li>后端提供健康检查和最小聊天接口，方便前后端先跑通。</li>
          <li>Agent 先采用可控串行流程，后续可平滑替换为 LangGraph 状态图。</li>
          <li>记忆、RAG、安全和 Prompt 已独立分层，避免后期堆在单文件里。</li>
        </ul>
      </a-card>

      <a-card title="后续优先级" class="surface-card">
        <ul class="plain-list">
          <li>P0：补齐会话持久化、用户体系、Prompt 配置与基础审核。</li>
          <li>P1：接入 MySQL / Redis / pgvector / MinIO 与异步任务。</li>
          <li>P2：补齐风格复刻、知识库检索与可观测性链路。</li>
        </ul>
      </a-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchHealth } from '@/api/chat'

const serviceReady = ref(false)

const moduleCards = [
  {
    title: 'Companion Runtime',
    description: '对话主入口，负责模式路由、上下文聚合和响应生成。',
  },
  {
    title: 'Memory Layer',
    description: '负责长期记忆与用户画像检索，避免每轮都从零开始。',
  },
  {
    title: 'RAG Layer',
    description: '承接恋爱建议、风格样本和风险知识的检索增强。',
  },
  {
    title: 'Safety Guard',
    description: '输入输出双向治理，确保安全优先于风格沉浸。',
  },
]

const flowSteps = [
  '接收用户消息并恢复会话上下文',
  '识别模式并做输入安全预检查',
  '按需触发记忆与知识检索',
  '生成候选回复并执行输出安全治理',
  '异步沉淀会话摘要、画像和检索索引',
]

const healthText = computed(() => (serviceReady.value ? '后端已联通' : '等待后端启动'))
const healthTagColor = computed(() => (serviceReady.value ? 'success' : 'warning'))

onMounted(async () => {
  try {
    const health = await fetchHealth()
    serviceReady.value = health.status === 'ok'
  } catch {
    serviceReady.value = false
  }
})
</script>

<style scoped>
.page-stack {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.95fr);
  gap: 24px;
  align-items: stretch;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
}

.hero-copy h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(34px, 5vw, 56px);
  line-height: 1.08;
  color: var(--brand-ink);
}

.hero-copy p {
  max-width: 720px;
  margin: 0;
  font-size: 16px;
  line-height: 1.9;
  color: var(--text-secondary);
}

.section-kicker {
  color: var(--brand-accent);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 12px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.hero-side {
  display: grid;
  gap: 14px;
}

.metric-card,
.module-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(20, 33, 61, 0.08);
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.metric-value {
  margin-top: 8px;
  font-size: 18px;
  line-height: 1.7;
  color: var(--brand-ink);
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.module-name {
  font-weight: 700;
  color: var(--brand-ink);
}

.module-desc {
  margin-top: 8px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.plain-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.9;
}

@media (max-width: 960px) {
  .hero-panel,
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
