<template>
  <main class="knowledge-view">
    <section class="knowledge-hero">
      <div class="hero-copy">
        <p class="hero-kicker">Knowledge map</p>
        <h1>恋爱知识地图</h1>
        <p>
          这不是随便安慰两句的聊天工具，而是一套把关系阶段、沟通技巧、情绪处理和策略打法串起来的知识底座。
        </p>
      </div>

      <div class="hero-stats">
        <article class="stat-card">
          <span>知识目录</span>
          <strong>{{ stats.directories }}</strong>
        </article>
        <article class="stat-card">
          <span>文档文件</span>
          <strong>{{ stats.files }}</strong>
        </article>
        <article class="stat-card">
          <span>最大层级</span>
          <strong>{{ stats.maxDepth + 1 }}</strong>
        </article>
      </div>
    </section>

    <section class="knowledge-layout">
      <aside class="knowledge-card side-card">
        <p class="card-kicker">知识分层</p>
        <h2>从基础理论到场景打法</h2>
        <ul class="info-list">
          <li>基础层：心理学、传播学、社会学，负责解释关系背后的机制。</li>
          <li>场景层：亲密关系、家庭、职场、社交，负责落到真实处境。</li>
          <li>能力层：沟通、冲突、情绪、边界，负责把建议变成可执行表达。</li>
          <li>策略层：破冰、推进、修复、深化，负责把节奏和方法串起来。</li>
        </ul>
      </aside>

      <section class="knowledge-card tree-card">
        <div class="tree-head">
          <div>
            <p class="card-kicker">Tree canvas</p>
            <h2>层级可视化主画布</h2>
          </div>
          <div class="legend">
            <span><i class="legend-dot is-directory" />目录</span>
            <span><i class="legend-dot is-file" />文件</span>
          </div>
        </div>

        <div class="tree-body">
          <KnowledgeTreeNode :node="knowledgeBaseTree" />
        </div>
      </section>

      <aside class="knowledge-card side-card">
        <p class="card-kicker">使用建议</p>
        <h2>怎么把地图用在聊天里</h2>
        <ul class="info-list">
          <li>先在聊天页识别你现在是情绪倾诉、关系分析，还是边界表达问题。</li>
          <li>再回到知识地图看它对应落在哪个主题，这样更容易理解建议为什么成立。</li>
          <li>当你发现同类问题反复出现，优先看策略层和关系维护层，而不是只盯当前一句话。</li>
        </ul>

        <div class="soft-note">
          <strong>你会看到的不是技术字段，而是更贴近用户感受的结构化依据。</strong>
          <span>目标是让 AI 的陪伴更有信任感，也更有章法。</span>
        </div>
      </aside>
    </section>
  </main>
</template>

<script setup lang="ts">
import KnowledgeTreeNode from '@/components/KnowledgeTreeNode.vue'
import { collectTreeStats, knowledgeBaseTree } from '@/data/knowledgeBaseTree'

const stats = collectTreeStats(knowledgeBaseTree)
</script>

<style scoped>
.knowledge-view {
  display: grid;
  gap: 18px;
  height: 100%;
  min-height: 0;
}

.knowledge-hero,
.knowledge-layout {
  min-width: 0;
}

.knowledge-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
}

.hero-copy,
.hero-stats,
.knowledge-card {
  border: 1px solid rgba(92, 60, 69, 0.08);
  border-radius: 28px;
  background: rgba(255, 252, 250, 0.78);
  box-shadow: 0 24px 48px rgba(82, 48, 57, 0.08);
}

.hero-copy {
  padding: 24px 26px;
}

.hero-kicker,
.card-kicker {
  margin: 0 0 8px;
  color: var(--color-rose-deep);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h1,
h2 {
  margin: 0;
  color: var(--color-ink);
  font-family: var(--font-display);
}

h1 {
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.08;
}

h2 {
  font-size: 22px;
}

.hero-copy p:last-child {
  max-width: 720px;
  margin: 14px 0 0;
  color: var(--color-ink-soft);
  font-size: 14px;
  line-height: 1.9;
}

.hero-stats {
  display: grid;
  gap: 12px;
  padding: 18px;
}

.stat-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.82);
}

.stat-card span {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 700;
}

.stat-card strong {
  color: var(--color-ink);
  font-size: 32px;
  line-height: 1;
}

.knowledge-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 280px;
  gap: 18px;
  min-height: 0;
}

.knowledge-card {
  padding: 20px;
}

.tree-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
}

.tree-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(92, 60, 69, 0.08);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  color: var(--color-ink-soft);
  font-size: 12px;
  font-weight: 700;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.legend-dot.is-directory {
  background: var(--color-ink);
}

.legend-dot.is-file {
  background: var(--color-rose);
}

.tree-body {
  min-height: 0;
  padding-top: 16px;
  overflow: auto;
}

.info-list {
  display: grid;
  gap: 12px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}

.info-list li {
  color: var(--color-ink-soft);
  font-size: 13px;
  line-height: 1.85;
}

.soft-note {
  display: grid;
  gap: 6px;
  margin-top: 18px;
  padding: 16px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(244, 213, 221, 0.66), rgba(255, 250, 247, 0.9));
  color: var(--color-ink-soft);
  font-size: 13px;
  line-height: 1.75;
}

.soft-note strong {
  color: var(--color-ink);
}

@media (max-width: 1180px) {
  .knowledge-hero,
  .knowledge-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .hero-copy,
  .hero-stats,
  .knowledge-card {
    border-radius: 24px;
  }

  .hero-copy,
  .knowledge-card {
    padding: 18px;
  }

  .tree-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
