<template>
  <main class="kb-tree-page">
    <section class="kb-hero">
      <div class="kb-hero__copy">
        <p class="kb-hero__eyebrow">RAG Knowledge Map</p>
        <h1 class="kb-hero__title">docs/knowledge_base 树状结构图</h1>
        <p class="kb-hero__desc">
          用可展开树把知识库分层直接展示出来，既能看总架构，也能下钻到具体目录和文档。
        </p>
      </div>

      <div class="kb-stats">
        <article class="kb-stat-card">
          <span class="kb-stat-card__label">目录数</span>
          <strong class="kb-stat-card__value">{{ stats.directories }}</strong>
        </article>
        <article class="kb-stat-card">
          <span class="kb-stat-card__label">文件数</span>
          <strong class="kb-stat-card__value">{{ stats.files }}</strong>
        </article>
        <article class="kb-stat-card">
          <span class="kb-stat-card__label">最大层级</span>
          <strong class="kb-stat-card__value">{{ stats.maxDepth + 1 }}</strong>
        </article>
      </div>
    </section>

    <section class="kb-board">
      <aside class="kb-sidebar">
        <div class="kb-sidebar__card">
          <h2 class="kb-sidebar__title">主分层</h2>
          <ul class="kb-sidebar__list">
            <li>00_meta：规范与索引</li>
            <li>01_foundation：理论基础</li>
            <li>02_scenario：现实场景</li>
            <li>03_skill：能力模块</li>
            <li>04_strategy：策略打法</li>
            <li>05_special：复杂专题</li>
            <li>06_case：成功/失败案例</li>
            <li>relationship_knowledge：高频话术库</li>
          </ul>
        </div>

        <div class="kb-sidebar__card">
          <h2 class="kb-sidebar__title">查看方式</h2>
          <p class="kb-sidebar__text">
            目录默认展开到前两层，深层内容按需点击展开，避免整棵树一次性铺开太乱。
          </p>
          <p class="kb-sidebar__tip">
            访问地址：<code>?view=kb-tree</code>
          </p>
        </div>
      </aside>

      <section class="kb-canvas">
        <div class="kb-canvas__header">
          <div>
            <p class="kb-canvas__label">Knowledge Tree</p>
            <h2 class="kb-canvas__title">层级可视化</h2>
          </div>
          <div class="kb-canvas__legend">
            <span class="legend-item"><i class="legend-dot is-directory" />目录</span>
            <span class="legend-item"><i class="legend-dot is-file" />文件</span>
          </div>
        </div>

        <div class="kb-canvas__body">
          <KnowledgeTreeNode :node="knowledgeBaseTree" />
        </div>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import KnowledgeTreeNode from '@/components/KnowledgeTreeNode.vue'
import { collectTreeStats, knowledgeBaseTree } from '@/data/knowledgeBaseTree'

const stats = collectTreeStats(knowledgeBaseTree)
</script>

<style scoped>
.kb-tree-page {
  min-height: 100dvh;
  padding: 32px;
  background:
    radial-gradient(circle at top left, rgba(200, 75, 106, 0.14), transparent 28%),
    radial-gradient(circle at top right, rgba(26, 42, 74, 0.14), transparent 24%),
    linear-gradient(180deg, #f7f9fc 0%, #eef2f7 100%);
  overflow: auto;
}

.kb-hero {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.kb-hero__eyebrow {
  margin: 0 0 8px;
  color: var(--brand-rose-deep);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.kb-hero__title {
  margin: 0;
  color: var(--brand-navy-deep);
  font-size: clamp(28px, 4vw, 48px);
  line-height: 1.05;
}

.kb-hero__desc {
  max-width: 720px;
  margin: 14px 0 0;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.8;
}

.kb-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 180px));
  gap: 14px;
  flex-shrink: 0;
}

.kb-stat-card {
  padding: 18px 20px;
  border: 1px solid rgba(15, 29, 53, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 20px 48px rgba(15, 29, 53, 0.08);
  backdrop-filter: blur(12px);
}

.kb-stat-card__label {
  display: block;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

.kb-stat-card__value {
  color: var(--brand-navy-deep);
  font-size: 32px;
  line-height: 1;
}

.kb-board {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
}

.kb-sidebar {
  display: grid;
  gap: 16px;
  align-content: start;
}

.kb-sidebar__card,
.kb-canvas {
  border: 1px solid rgba(15, 29, 53, 0.08);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 22px 54px rgba(15, 29, 53, 0.08);
  backdrop-filter: blur(14px);
}

.kb-sidebar__card {
  padding: 20px;
}

.kb-sidebar__title,
.kb-canvas__title {
  margin: 0;
  color: var(--brand-navy-deep);
  font-size: 18px;
}

.kb-sidebar__list {
  display: grid;
  gap: 10px;
  margin: 16px 0 0;
  padding-left: 18px;
  color: var(--text-primary);
  line-height: 1.6;
}

.kb-sidebar__text,
.kb-sidebar__tip {
  margin: 14px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.kb-sidebar__tip code {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(26, 42, 74, 0.08);
  color: var(--brand-navy-deep);
  font-family: var(--font-mono);
  font-size: 12px;
}

.kb-canvas {
  min-width: 0;
  overflow: hidden;
}

.kb-canvas__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 24px 24px 18px;
  border-bottom: 1px solid rgba(15, 29, 53, 0.08);
}

.kb-canvas__label {
  margin: 0 0 6px;
  color: var(--brand-rose);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.kb-canvas__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(26, 42, 74, 0.06);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot.is-directory {
  background: var(--brand-navy);
}

.legend-dot.is-file {
  background: var(--brand-rose);
}

.kb-canvas__body {
  display: grid;
  gap: 10px;
  padding: 24px;
}

@media (max-width: 1100px) {
  .kb-tree-page {
    padding: 20px;
  }

  .kb-hero,
  .kb-board {
    display: grid;
    grid-template-columns: 1fr;
  }

  .kb-stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kb-tree-page {
    padding: 12px;
  }

  .kb-hero {
    margin-bottom: 16px;
  }

  .kb-hero__desc {
    margin-top: 10px;
    font-size: 14px;
  }

  .kb-stats {
    grid-template-columns: 1fr;
  }

  .kb-stat-card {
    padding: 16px;
  }

  .kb-canvas__header,
  .kb-canvas__body,
  .kb-sidebar__card {
    padding: 16px;
  }

  .kb-canvas__header {
    align-items: start;
    flex-direction: column;
  }
}
</style>
