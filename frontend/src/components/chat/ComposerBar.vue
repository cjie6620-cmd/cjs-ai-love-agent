<template>
  <footer class="composer-bar">
    <div class="composer-shell">
      <div class="composer-input-wrap">
        <a-textarea
          :value="draft"
          :auto-size="{ minRows: 2, maxRows: 5 }"
          :bordered="false"
          class="composer-input"
          placeholder="给 AI Love 发送消息"
          @update:value="$emit('update:draft', String($event ?? ''))"
          @pressEnter="handleEnter"
        />
      </div>

      <div class="composer-footer">
        <div class="mode-row" aria-label="模式切换">
          <button
            v-for="mode in modeOptions"
            :key="mode.value"
            :class="['mode-chip', { 'is-active': mode.value === activeMode }]"
            type="button"
            @click="$emit('change-mode', mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>

        <a-button
          class="send-button"
          type="primary"
          :loading="submitting"
          @click="$emit('submit')"
        >
          发送
        </a-button>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import type { ChatMode } from '@/types/chat'

interface ModeOption {
  label: string
  value: ChatMode
}

const props = defineProps<{
  activeMode: ChatMode
  draft: string
  modeOptions: ModeOption[]
  submitting: boolean
}>()

const emit = defineEmits<{
  (event: 'change-mode', mode: ChatMode): void
  (event: 'submit'): void
  (event: 'update:draft', value: string): void
}>()

const handleEnter = (event: KeyboardEvent) => {
  if (event.shiftKey) {
    return
  }
  event.preventDefault()
  emit('submit')
}
</script>

<style scoped>
.composer-bar {
  display: block;
  flex-shrink: 0;
  padding: 12px 16px 0;
  background: linear-gradient(180deg, rgba(13, 16, 22, 0), rgba(13, 16, 22, 0.94) 24%);
}

.composer-shell {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--chat-line);
  background: rgba(20, 24, 32, 0.96);
  box-shadow: 0 22px 40px rgba(0, 0, 0, 0.28);
}

.composer-input-wrap {
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.02);
}

.composer-input {
  padding: 10px 12px 8px;
  color: var(--chat-text-primary);
  font-size: 15px;
}

.composer-input :deep(textarea.ant-input) {
  max-height: 124px !important;
  padding: 0 !important;
  color: var(--chat-text-primary) !important;
  overflow-y: auto !important;
  resize: none;
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.mode-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mode-chip {
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.04);
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    color var(--transition-base);
}

.mode-chip:hover,
.mode-chip.is-active {
  border-color: rgba(123, 162, 255, 0.4);
  background: rgba(123, 162, 255, 0.12);
  color: var(--chat-text-primary);
}

.send-button.send-button {
  min-width: 88px;
  height: 40px;
  font-weight: 600;
}

@media (max-width: 760px) {
  .composer-bar {
    padding: 12px 12px 0;
  }

  .composer-shell {
    padding: 14px;
  }

  .composer-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .send-button.send-button {
    width: 100%;
  }
}
</style>
