<template>
  <details
    class="tree-node"
    :open="defaultExpanded"
  >
    <summary
      class="tree-node__summary"
      :style="{ '--node-depth': String(depth) }"
    >
      <span :class="['tree-node__icon', `is-${node.type}`]">
        {{ node.type === 'directory' ? 'D' : 'F' }}
      </span>
      <span class="tree-node__name">{{ node.name }}</span>
      <span v-if="node.children?.length" class="tree-node__meta">
        {{ node.children.length }} 项
      </span>
    </summary>

    <div v-if="node.children?.length" class="tree-node__children">
      <KnowledgeTreeNode
        v-for="child in node.children"
        :key="`${node.name}-${child.name}`"
        :node="child"
        :depth="depth + 1"
      />
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { KnowledgeBaseNode } from '@/data/knowledgeBaseTree'

const props = defineProps<{
  node: KnowledgeBaseNode
  depth?: number
}>()

const depth = computed(() => props.depth ?? 0)
const defaultExpanded = computed(() => depth.value <= 1)
</script>

<style scoped>
.tree-node {
  position: relative;
}

.tree-node__summary {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 12px 14px 12px calc(18px + (var(--node-depth) * 24px));
  border: 1px solid rgba(92, 60, 69, 0.08);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 250, 247, 0.96));
  box-shadow: 0 14px 28px rgba(82, 48, 57, 0.05);
  list-style: none;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.tree-node__summary::-webkit-details-marker {
  display: none;
}

.tree-node__summary:hover {
  transform: translateY(-1px);
  border-color: rgba(200, 95, 120, 0.22);
  box-shadow: 0 18px 34px rgba(82, 48, 57, 0.08);
}

.tree-node__summary::before {
  position: absolute;
  left: calc(8px + (var(--node-depth) * 24px));
  top: 50%;
  width: 14px;
  color: var(--brand-rose);
  font-size: 12px;
  content: '▸';
  transform: translateY(-50%);
  transition: transform 0.2s ease;
}

.tree-node[open] > .tree-node__summary::before {
  transform: translateY(-50%) rotate(90deg);
}

.tree-node__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.tree-node__icon.is-directory {
  background: rgba(53, 39, 45, 0.08);
  color: var(--color-ink);
}

.tree-node__icon.is-file {
  background: rgba(200, 75, 106, 0.12);
  color: var(--brand-rose-deep);
}

.tree-node__name {
  color: var(--text-heading);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}

.tree-node__meta {
  margin-left: auto;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(26, 42, 74, 0.08);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.tree-node__children {
  position: relative;
  display: grid;
  gap: 10px;
  padding: 10px 0 0;
}

@media (max-width: 640px) {
  .tree-node__summary {
    gap: 10px;
    min-height: 44px;
    padding: 10px 12px 10px calc(18px + (var(--node-depth) * 16px));
  }

  .tree-node__summary::before {
    left: calc(8px + (var(--node-depth) * 16px));
  }

  .tree-node__name {
    font-size: 13px;
  }

  .tree-node__meta {
    display: none;
  }
}
</style>
