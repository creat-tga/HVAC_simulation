<script setup lang="ts">
// HVAC-themed CSS background with thermal gradient blobs and engineering grid
</script>

<template>
  <div class="hvac-background">
    <!-- Technical Grid Pattern -->
    <div class="grid-pattern" />
    <!-- Thermal Fluid Blobs -->
    <div class="blob-container">
      <div class="blob blob-cold" />
      <div class="blob blob-warm" />
      <div class="blob blob-neutral" />
    </div>
    <!-- Vignette Overlay -->
    <div class="vignette" />
  </div>
</template>

<style scoped>
.hvac-background {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: #f1f5f9;
  overflow: hidden;
}

/* Engineering grid pattern */
.grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.7;
}

/* Fluid dynamics blobs container */
.blob-container {
  position: absolute;
  inset: 0;
  overflow: hidden;
  filter: blur(80px);
  opacity: 0.5;
}

/* Base blob style */
.blob {
  position: absolute;
  border-radius: 50%;
  animation: blob-float 18s infinite alternate ease-in-out;
}

/* Cold air (cyan) — top-left */
.blob-cold {
  top: -8%;
  left: -8%;
  width: 45%;
  height: 45%;
  background: rgba(6, 182, 212, 0.25);
}

/* Warm air (orange) — bottom-right */
.blob-warm {
  bottom: -10%;
  right: -10%;
  width: 50%;
  height: 50%;
  background: rgba(251, 146, 60, 0.15);
  animation-delay: 2s;
}

/* Neutral mixed (blue) — center-right */
.blob-neutral {
  top: 35%;
  left: 50%;
  width: 35%;
  height: 35%;
  background: rgba(59, 130, 246, 0.18);
  animation-delay: 4s;
}

/* Vignette depth overlay */
.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, transparent 0%, rgba(241, 245, 249, 0.5) 100%);
}

@keyframes blob-float {
  0% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(25px, -40px) scale(1.08);
  }
  66% {
    transform: translate(-15px, 20px) scale(0.92);
  }
  100% {
    transform: translate(0, 0) scale(1);
  }
}
</style>
