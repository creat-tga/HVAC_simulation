<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: number | null | undefined
  min?: number
  max?: number
  step?: number
  precision?: number
  disabled?: boolean
}>(), {
  step: 1,
  precision: 0,
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [v: number] }>()
const displayValue = ref(String(props.modelValue ?? props.min ?? 0))

function normalize(raw: number): number {
  let next = Number.isFinite(raw) ? raw : props.min ?? 0
  if (props.min !== undefined) next = Math.max(props.min, next)
  if (props.max !== undefined) next = Math.min(props.max, next)
  const scale = 10 ** props.precision
  return Math.round(next * scale) / scale
}

watch(
  () => props.modelValue,
  (v) => {
    displayValue.value = String(v ?? props.min ?? 0)
  },
)

function syncNormalized(el: HTMLInputElement, raw: number) {
  const next = normalize(raw)
  displayValue.value = String(next)
  el.value = displayValue.value
  emit('update:modelValue', next)
}

function onInput(evt: Event) {
  const el = evt.target as HTMLInputElement
  displayValue.value = el.value
  const raw = Number(el.value)
  if (el.value === '' || !Number.isFinite(raw)) return
  if ((props.precision ?? 0) === 0 || (props.min !== undefined && raw < props.min)) {
    syncNormalized(el, raw)
  } else {
    emit('update:modelValue', raw)
  }
}

function commit(raw: Event) {
  const el = raw.target as HTMLInputElement
  syncNormalized(el, Number(el.value))
}
</script>

<template>
  <div class="num-input" :class="{ 'is-disabled': disabled }">
    <input
      type="number"
      :value="displayValue"
      :min="min"
      :max="max"
      :step="step"
      :disabled="disabled"
      @input="onInput"
      @blur="commit"
      @change="commit"
      @keyup.enter="commit"
    >
  </div>
</template>

<style scoped>
.num-input {
  display: block;
  width: var(--scheme-control-width, 72px);
  max-width: 100%;
  height: var(--scheme-control-height, 22px);
  line-height: var(--scheme-control-height, 22px);
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
}
.num-input input {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  border: 0;
  padding: 0 6px;
  line-height: var(--scheme-control-height, 22px);
  text-align: center;
  color: #303133;
  font-size: var(--scheme-control-font-size, 13px) !important;
  outline: none;
}
.num-input input::-webkit-outer-spin-button,
.num-input input::-webkit-inner-spin-button {
  appearance: none;
  margin: 0;
}
.num-input:focus-within {
  border-color: #409eff;
}
.num-input.is-disabled {
  opacity: 0.65;
}
.num-input input:disabled {
  cursor: not-allowed;
}

</style>
