<template>
  <a-layout class="app-shell">
    <a-layout-header class="app-header">
      <div class="brand-block">
        <div class="brand-kicker">AI Love Agent</div>
        <div class="brand-title">企业级恋爱智能体工程骨架</div>
      </div>

      <a-menu
        mode="horizontal"
        :selected-keys="[selectedKey]"
        class="nav-menu"
        @click="handleMenuClick"
      >
        <a-menu-item key="/">项目总览</a-menu-item>
        <a-menu-item key="/workbench">联调工作台</a-menu-item>
      </a-menu>
    </a-layout-header>

    <a-layout-content class="app-content">
      <RouterView />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import type { MenuProps } from 'ant-design-vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

const selectedKey = computed(() => route.path)

const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
  router.push(String(key))
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(237, 96, 72, 0.22), transparent 30%),
    radial-gradient(circle at 80% 20%, rgba(20, 33, 61, 0.22), transparent 26%),
    linear-gradient(180deg, #fff8f1 0%, #f6efe8 100%);
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  height: auto;
  padding: 20px 32px;
  background: rgba(255, 248, 241, 0.78);
  border-bottom: 1px solid rgba(20, 33, 61, 0.08);
  backdrop-filter: blur(18px);
}

.brand-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-kicker {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--brand-accent);
}

.brand-title {
  font-family: var(--font-display);
  font-size: 26px;
  color: var(--brand-ink);
}

.nav-menu {
  flex: 1;
  justify-content: flex-end;
  min-width: 280px;
  background: transparent;
  border-bottom: none;
}

.app-content {
  padding: 32px;
}

@media (max-width: 900px) {
  .app-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 18px 20px;
  }

  .nav-menu {
    width: 100%;
  }

  .app-content {
    padding: 20px;
  }
}
</style>
