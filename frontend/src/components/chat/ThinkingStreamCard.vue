<template>
  <section :class="['thinking-card', { 'is-done': status === 'done', 'is-collapsed': !expanded }]">
    <button class="thinking-head focus-ring" type="button" @click="expanded = !expanded">
      <span class="thinking-orbit" aria-hidden="true">
        <span />
      </span>
      <span class="thinking-title">{{ status === 'done' ? '已思考' : '思考中' }}</span>
      <span class="thinking-duration">用时 {{ elapsedSeconds }} 秒</span>
      <DownOutlined class="thinking-chevron" />
    </button>

    <Transition name="thinking-expand">
      <div v-if="expanded" class="thinking-body">
        <TransitionGroup v-if="chunks.length > 0" name="thinking-line" tag="div" class="thinking-lines">
          <p
            v-for="(chunk, index) in chunks"
            :key="chunk.id"
            :class="{ 'is-latest': index === chunks.length - 1 && status !== 'done' }"
          >
            {{ chunk.content }}
          </p>
        </TransitionGroup>
        <p v-else class="thinking-empty">{{ summaryText }}</p>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
import { DownOutlined } from '@ant-design/icons-vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import type { ThinkingChunk, ThinkingStatus } from '@/types/chat'

const props = defineProps<{
  status: ThinkingStatus
  chunks: ThinkingChunk[]
}>()

const expanded = ref(true)
const startedAt = ref(Date.now())
const elapsedSeconds = ref(0)
let timer: number | null = null

const summaryText = computed(() => {
  if (props.chunks.length === 0) {
    return props.status === 'done' ? '已经整理好啦' : '正在接住你的情绪线索'
  }
  if (props.status === 'done') {
    return `已经整理好 ${props.chunks.length} 条思路`
  }
  return props.chunks[props.chunks.length - 1]?.content ?? '正在接住你的情绪线索'
})

const tickElapsed = () => {
  elapsedSeconds.value = Math.max(0, Math.ceil((Date.now() - startedAt.value) / 1000))
}

const startTimer = () => {
  if (timer !== null) {
    return
  }
  tickElapsed()
  timer = window.setInterval(tickElapsed, 500)
}

const stopTimer = () => {
  tickElapsed()
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

watch(
  () => props.status,
  (nextStatus) => {
    expanded.value = nextStatus !== 'done'
    if (nextStatus === 'streaming' && timer === null) {
      startedAt.value = Date.now()
      startTimer()
    }
    if (nextStatus === 'done') {
      stopTimer()
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (props.status === 'streaming') {
    startTimer()
  }
})

onUnmounted(stopTimer)
</script>

<style scoped>
.thinking-card {
  position: relative;
  display: grid;
  width: min(100%, 620px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 24px;
  background:
    linear-gradient(145deg, rgba(43, 45, 54, 0.94), rgba(57, 58, 68, 0.9)),
    radial-gradient(circle at 12% 0%, rgba(133, 164, 255, 0.2), transparent 34%),
    radial-gradient(circle at 100% 20%, rgba(255, 206, 171, 0.08), transparent 32%);
  color: rgba(241, 244, 250, 0.92);
  box-shadow:
    0 22px 54px rgba(88, 45, 56, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  overflow: hidden;
  backdrop-filter: blur(18px);
}

.thinking-card::before {
  position: absolute;
  inset: 25px auto 24px 29px;
  width: 1px;
  background: linear-gradient(180deg, rgba(141, 170, 255, 0.82), rgba(141, 170, 255, 0.08));
  content: "";
  opacity: 0;
  transition: opacity 0.2s ease;
}

.thinking-card:not(.is-collapsed)::before {
  opacity: 1;
}

.thinking-head {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 19px 22px 15px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.thinking-orbit {
  position: relative;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  color: #88a7ff;
  flex: 0 0 auto;
}

.thinking-orbit::before,
.thinking-orbit::after,
.thinking-orbit span {
  position: absolute;
  width: 19px;
  height: 8px;
  border: 2px solid currentColor;
  border-radius: 999px;
  content: "";
  opacity: 0.95;
}

.thinking-orbit::before {
  transform: rotate(60deg);
}

.thinking-orbit::after {
  transform: rotate(-60deg);
}

.thinking-orbit span {
  transform: rotate(0deg);
}

.thinking-card:not(.is-done) .thinking-orbit {
  animation: thinkingSpin 3.2s linear infinite;
}

.thinking-title,
.thinking-duration {
  color: rgba(245, 247, 252, 0.96);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.02em;
  line-height: 1.2;
}

.thinking-duration {
  color: rgba(220, 226, 236, 0.86);
  font-weight: 700;
}

.thinking-chevron {
  margin-left: 4px;
  color: rgba(220, 226, 236, 0.88);
  font-size: 14px;
  transition: transform 0.2s ease;
}

.thinking-card.is-collapsed .thinking-chevron {
  transform: rotate(-90deg);
}

.thinking-body {
  margin: 0 22px 22px 36px;
  padding: 4px 0 0 28px;
  color: rgba(229, 233, 242, 0.86);
  font-size: 15px;
  line-height: 1.78;
}

.thinking-lines {
  display: grid;
  gap: 13px;
}

.thinking-lines p,
.thinking-empty {
  position: relative;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.thinking-lines p:first-child::before {
  position: absolute;
  left: -39px;
  top: 0.82em;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: rgba(229, 233, 242, 0.9);
  box-shadow:
    0 0 0 7px rgba(136, 167, 255, 0.16),
    0 0 18px rgba(136, 167, 255, 0.34);
  content: "";
}

.thinking-lines p.is-latest::after {
  display: inline-block;
  width: 8px;
  height: 1em;
  margin-left: 3px;
  border-radius: 99px;
  background: #88a7ff;
  vertical-align: -0.18em;
  animation: caretBlink 0.9s steps(2, jump-none) infinite;
  content: "";
}

.thinking-line-enter-active {
  transition: opacity 0.22s ease, transform 0.22s ease, filter 0.22s ease;
}

.thinking-line-enter-from {
  opacity: 0;
  filter: blur(4px);
  transform: translateY(8px);
}

.thinking-expand-enter-active,
.thinking-expand-leave-active {
  max-height: 520px;
  transition: max-height 0.22s ease, opacity 0.18s ease;
}

.thinking-expand-enter-from,
.thinking-expand-leave-to {
  max-height: 0;
  opacity: 0;
}

@keyframes thinkingSpin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes caretBlink {
  0%,
  45% {
    opacity: 1;
  }

  46%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 760px) {
  .thinking-card {
    width: 100%;
    border-radius: 18px;
  }

  .thinking-title,
  .thinking-duration {
    font-size: 15px;
  }

  .thinking-body {
    margin-right: 16px;
    font-size: 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-card:not(.is-done) .thinking-orbit,
  .thinking-lines p.is-latest::after {
    animation: none;
  }
}
</style>
