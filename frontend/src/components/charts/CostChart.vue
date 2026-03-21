<script setup lang="ts">
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'

const { t } = useI18n()

const props = defineProps<{
  monthlyCost: number[]
  totalCost: number
}>()

const months = computed(() =>
  Array.from({ length: 12 }, (_, i) => `${i + 1}${t('report.chart.month')}`)
)

const option = computed<EChartsOption>(() => ({
  title: {
    text: t('report.chart.costAnalysis'),
    subtext: `${t('report.chart.totalCostLabel')}: ¥${props.totalCost.toFixed(2)}`,
    left: 'center',
  },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: months.value },
  yAxis: { type: 'value', name: '¥' },
  series: [
    {
      name: t('report.chart.monthlyCost'),
      type: 'bar',
      data: props.monthlyCost,
      itemStyle: { color: '#E6A23C' },
    },
  ],
}))
</script>

<template>
  <VChart :option="option" autoresize style="height: 400px" />
</template>
