<template>
  <aside class="insight-panel">
    <section class="panel-card">
      <p class="panel-kicker">当前陪伴模式</p>
      <h3>{{ modeTitle }}</h3>
      <p>{{ modeDesc }}</p>
      <div class="tone-tags">
        <span v-for="tag in toneTags" :key="tag">{{ tag }}</span>
      </div>
    </section>

    <section class="panel-card">
      <p class="panel-kicker">我建议你下一步聊什么</p>
      <h3>继续聊下去的入口</h3>
      <div class="suggestion-list">
        <button
          v-for="question in suggestions"
          :key="question"
          class="suggestion-chip focus-ring"
          type="button"
          @click="$emit('ask', question)"
        >
          {{ question }}
        </button>
      </div>
    </section>

    <section class="panel-card">
      <p class="panel-kicker">最近对话主题</p>
      <h3>我正在理解什么</h3>
      <ul class="summary-list">
        <li v-for="item in topicSummary" :key="item">{{ item }}</li>
      </ul>
    </section>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  modeTitle: string
  modeDesc: string
  toneTags: string[]
  suggestions: string[]
  topicSummary: string[]
}>()

defineEmits<{
  (event: 'ask', question: string): void
}>()
</script>

<style scoped>
.insight-panel {
  display: grid;
  gap: 14px;
  min-width: 0;
  align-content: start;
}

.panel-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border: 1px solid rgba(92, 60, 69, 0.08);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 18px 34px rgba(82, 48, 57, 0.08);
}

.panel-kicker {
  margin: 0;
  color: var(--color-rose-deep);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h3 {
  margin: 0;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 20px;
}

.panel-card > p:last-of-type {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: 13px;
  line-height: 1.8;
}

.tone-tags,
.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tone-tags span,
.suggestion-chip {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.tone-tags span {
  display: inline-flex;
  align-items: center;
  background: rgba(200, 95, 120, 0.1);
  color: var(--color-rose-deep);
}

.suggestion-chip {
  border: 1px solid rgba(92, 60, 69, 0.08);
  background: rgba(255, 250, 247, 0.9);
  color: var(--color-ink-soft);
  cursor: pointer;
  transition:
    transform var(--transition-base),
    border-color var(--transition-base),
    color var(--transition-base);
}

.suggestion-chip:hover {
  border-color: rgba(164, 61, 88, 0.18);
  color: var(--color-rose-deep);
  transform: translateY(-1px);
}

.summary-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.summary-list li {
  position: relative;
  padding-left: 16px;
  color: var(--color-ink-soft);
  font-size: 13px;
  line-height: 1.8;
}

.summary-list li::before {
  position: absolute;
  left: 0;
  top: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-apricot);
  content: "";
}
</style>
