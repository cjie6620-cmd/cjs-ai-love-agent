<template>
  <div :class="['app-shell', { 'is-chat-route': isChatRoute, 'is-admin-route': isAdminRoute }]">
    <header v-if="!isChatRoute && !isAdminRoute" class="shell-header">
      <RouterLink class="brand" to="/chat" aria-label="AI Love">
        <img class="brand-logo" src="/i-love-new-york.svg" alt="" />
        <strong>AI Love</strong>
      </RouterLink>

      <nav class="shell-nav" aria-label="主导航">
        <RouterLink to="/chat">聊天</RouterLink>
        <RouterLink to="/knowledge">知识地图</RouterLink>
      </nav>
    </header>

    <main class="shell-main">
      <RouterView v-slot="{ Component }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isChatRoute = computed(() => route.path === '/chat')
const isAdminRoute = computed(() => route.path.startsWith('/admin'))
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100dvh;
  overflow: hidden;
  background:
    radial-gradient(circle at top, rgba(59, 91, 219, 0.12), transparent 24%),
    linear-gradient(180deg, #07090d 0%, #0b0f15 100%);
}

.app-shell.is-chat-route {
  grid-template-rows: minmax(0, 1fr);
}

.app-shell.is-admin-route {
  grid-template-rows: minmax(0, 1fr);
  background: #eef1f4;
}

.shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--chat-line);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-logo {
  width: 34px;
  height: 34px;
  object-fit: contain;
  filter: grayscale(1) brightness(1.45);
}

.brand strong {
  color: var(--chat-text-primary);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.shell-nav {
  display: inline-flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--chat-line);
  background: rgba(255, 255, 255, 0.04);
}

.shell-nav a {
  min-width: 88px;
  padding: 10px 16px;
  color: var(--chat-text-muted);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  transition: color var(--transition-base), background var(--transition-base);
}

.shell-nav a + a {
  border-left: 1px solid var(--chat-line);
}

.shell-nav a.router-link-active {
  color: var(--chat-text-primary);
  background: rgba(123, 162, 255, 0.14);
}

.shell-main {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  padding: 0 20px 20px;
  overflow: hidden;
}

.shell-main > * {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
}

.app-shell.is-chat-route .shell-main {
  padding: 0;
}

.app-shell.is-admin-route .shell-main {
  padding: 0;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 760px) {
  .shell-header {
    align-items: stretch;
    flex-direction: column;
    padding: 14px 12px 10px;
  }

  .shell-nav {
    width: 100%;
  }

  .shell-nav a {
    flex: 1;
  }

  .shell-main {
    padding: 0 12px 12px;
  }

  .app-shell.is-chat-route .shell-main {
    padding: 0;
  }
}
</style>
