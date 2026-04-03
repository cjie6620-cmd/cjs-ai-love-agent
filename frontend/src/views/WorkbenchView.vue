<template>
  <div class="workbench-grid">
    <a-card class="surface-card" title="对话联调">
      <a-form layout="vertical">
        <a-form-item label="会话模式">
          <a-segmented
            v-model:value="form.mode"
            :options="modeOptions"
            block
          />
        </a-form-item>

        <a-form-item label="用户消息">
          <a-textarea
            v-model:value="form.message"
            :rows="6"
            placeholder="输入一句话，验证后端主流程是否走通"
          />
        </a-form-item>

        <div class="action-row">
          <a-button type="primary" :loading="submitting" @click="submitMessage">
            发送到后端
          </a-button>
          <a-button @click="fillDemo">填充示例</a-button>
        </div>
      </a-form>
    </a-card>

    <a-card class="surface-card" title="返回结果">
      <template v-if="response">
        <a-alert message="链路调用成功" type="success" show-icon />

        <div class="result-block">
          <div class="result-label">回复内容</div>
          <div class="result-text">{{ response.reply }}</div>
        </div>

        <div class="trace-grid">
          <div class="trace-card">
            <div class="result-label">风险等级</div>
            <div class="trace-value">{{ response.trace.safety_level }}</div>
          </div>
          <div class="trace-card">
            <div class="result-label">记忆命中</div>
            <div class="trace-value">
              {{ response.trace.memory_hits.join(' / ') || '无' }}
            </div>
          </div>
          <div class="trace-card">
            <div class="result-label">知识命中</div>
            <div class="trace-value">
              {{ response.trace.knowledge_hits.join(' / ') || '无' }}
            </div>
          </div>
        </div>
      </template>

      <a-empty v-else description="发送一条消息后，这里会展示后端返回结果" />
    </a-card>

    <a-card class="surface-card" title="联调建议">
      <ul class="plain-list">
        <li>先启动 `docker compose up -d`，准备 MySQL、Redis、pgvector、MinIO。</li>
        <li>再启动后端 `uvicorn app.main:app --reload`，确认 `/api/v1/health` 可访问。</li>
        <li>最后启动前端 `npm run dev`，在当前页面完成接口联调。</li>
      </ul>
    </a-card>

    <a-card class="surface-card" title="下一步开发建议">
      <ul class="plain-list">
        <li>把当前 mock 工作流替换为 LangGraph 节点图。</li>
        <li>把记忆、知识、风格样本拆成独立仓储与检索策略。</li>
        <li>补齐登录、会话持久化、Prompt 管理和审计能力。</li>
      </ul>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { sendChatMessage } from '@/api/chat'
import type { ChatMode, ChatResponse } from '@/types/chat'

const modeOptions = [
  { label: '陪伴', value: 'companion' },
  { label: '建议', value: 'advice' },
  { label: '复刻', value: 'style_clone' },
  { label: '安抚', value: 'soothing' },
]

const form = reactive<{
  session_id: string
  user_id: string
  message: string
  mode: ChatMode
}>({
  session_id: 'session-demo-001',
  user_id: 'user-demo-001',
  message: '',
  mode: 'companion',
})

const response = ref<ChatResponse>()
const submitting = ref(false)

const fillDemo = () => {
  form.mode = 'advice'
  form.message = '她今天回复我很冷淡，我应该怎么继续聊，才不会显得太着急？'
}

const submitMessage = async () => {
  if (!form.message.trim()) {
    message.warning('先输入一条消息')
    return
  }

  submitting.value = true
  try {
    response.value = await sendChatMessage({
      session_id: form.session_id,
      user_id: form.user_id,
      message: form.message.trim(),
      mode: form.mode,
    })
    message.success('请求成功，后端链路已打通')
  } catch (error) {
    console.error(error)
    message.error('请求失败，请先确认后端服务是否启动')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.workbench-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.action-row {
  display: flex;
  gap: 12px;
}

.result-block {
  margin-top: 18px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
}

.result-label {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.result-text {
  margin-top: 10px;
  color: var(--brand-ink);
  line-height: 1.9;
  font-size: 16px;
}

.trace-grid {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.trace-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(20, 33, 61, 0.05);
}

.trace-value {
  margin-top: 8px;
  line-height: 1.8;
  color: var(--brand-ink);
}

.plain-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.9;
  color: var(--text-secondary);
}

@media (max-width: 960px) {
  .workbench-grid {
    grid-template-columns: 1fr;
  }
}
</style>
