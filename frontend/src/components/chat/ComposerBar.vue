<template>
  <footer class="composer-bar">
    <div class="composer-shell">
      <div class="composer-input-wrap">
        <a-textarea
          :value="draft"
          :auto-size="{ minRows: 2, maxRows: 5 }"
          :bordered="false"
          class="composer-input"
          placeholder="写下想对 TA 说的话，或把心里的小纠结交给我"
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
          发送心意
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
  padding: 12px 20px 18px;
  background: linear-gradient(180deg, rgba(255, 244, 241, 0), rgba(255, 244, 241, 0.88) 30%);
}

.composer-shell {
  display: grid;
  gap: 14px;
  max-width: 900px;
  margin: 0 auto;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 26px;
  background: rgba(255, 250, 247, 0.84);
  box-shadow: 0 18px 44px rgba(125, 72, 84, 0.14);
  backdrop-filter: blur(18px);
}

.composer-input-wrap {
  border: 1px solid rgba(157, 83, 100, 0.1);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
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
  background: transparent !important;
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
  border: 1px solid rgba(157, 83, 100, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.56);
  color: var(--chat-text-muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color var(--transition-base),
    background var(--transition-base),
    color var(--transition-base);
}

.mode-chip:hover,
.mode-chip.is-active {
  border-color: rgba(200, 95, 120, 0.32);
  background: rgba(248, 223, 229, 0.88);
  color: var(--chat-accent-strong);
}

.send-button.send-button {
  min-width: 104px;
  height: 40px;
  font-weight: 800;
}

@media (max-width: 760px) {
  .composer-bar {
    padding: 12px 12px 14px;
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
