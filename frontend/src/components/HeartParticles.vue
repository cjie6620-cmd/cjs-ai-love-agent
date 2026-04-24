<template>
  <div class="ambient-layer" aria-hidden="true">
    <span class="pulse pulse-one" />
    <span class="pulse pulse-two" />
    <span class="pulse pulse-three" />
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.ambient-layer {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}

.pulse {
  position: absolute;
  border: 1px solid rgba(200, 95, 120, 0.18);
  border-radius: 50%;
  opacity: 0.72;
  transform: scale(0.86);
  animation: pulse-breathe 9s ease-in-out infinite;
}

.pulse-one {
  top: 9%;
  left: 10%;
  width: 220px;
  height: 220px;
  border-color: rgba(200, 95, 120, 0.18);
}

.pulse-two {
  right: 9%;
  bottom: 14%;
  width: 280px;
  height: 280px;
  border-color: rgba(120, 147, 126, 0.16);
  animation-delay: 1.6s;
}

.pulse-three {
  top: 38%;
  right: 31%;
  width: 150px;
  height: 150px;
  border-color: rgba(139, 122, 150, 0.14);
  animation-delay: 3.2s;
}

@keyframes pulse-breathe {
  0%,
  100% {
    opacity: 0.34;
    transform: scale(0.86);
  }

  50% {
    opacity: 0.7;
    transform: scale(1);
  }
}

@media (max-width: 760px) {
  .pulse {
    opacity: 0.28;
  }
}
</style>
