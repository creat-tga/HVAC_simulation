<script setup lang="ts">
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'

const { t } = useI18n()

const props = defineProps<{
  monthlyEnergy: number[]
  totalEnergy: number
}>()

const months = computed(() =>
  Array.from({ length: 12 }, (_, i) => `${i + 1}${t('report.chart.month')}`)
)

const option = computed<EChartsOption>(() => ({
  title: {
    text: t('report.chart.energyAnalysis'),
    subtext: `${t('report.chart.totalEnergyLabel')}: ${props.totalEnergy.toFixed(1)} kWh`,
    left: 'center',
  },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: months.value },
  yAxis: { type: 'value', name: 'kWh' },
  series: [
    {
      name: t('report.chart.monthlyEnergy'),
      type: 'bar',
      data: props.monthlyEnergy,
      itemStyle: { color: '#67C23A' },
    },
  ],
}))
</script>

<template>
  <VChart :option="option" autoresize style="height: 400px" />
</template>
