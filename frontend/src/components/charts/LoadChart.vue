<script setup lang="ts">
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'

const { t } = useI18n()

const props = defineProps<{
  coolingLoad: number[]
  heatingLoad: number[]
}>()

const option = computed<EChartsOption>(() => ({
  title: { text: t('report.chart.hourlyLoad'), left: 'center' },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
  },
  legend: { data: [t('report.chart.coolingLoad'), t('report.chart.heatingLoad')], bottom: 0 },
  xAxis: {
    type: 'category',
    name: t('report.chart.hour'),
    data: Array.from({ length: props.coolingLoad.length }, (_, i) => i + 1),
    axisLabel: {
      formatter: (val: string) => {
        const h = Number(val)
        if (h % 730 === 0) return `${Math.floor(h / 730) + 1}${t('report.chart.month')}`
        return ''
      },
    },
  },
  yAxis: { type: 'value', name: 'kW' },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider' },
  ],
  series: [
    {
      name: t('report.chart.coolingLoad'),
      type: 'line',
      data: props.coolingLoad,
      itemStyle: { color: '#409EFF' },
      showSymbol: false,
    },
    {
      name: t('report.chart.heatingLoad'),
      type: 'line',
      data: props.heatingLoad,
      itemStyle: { color: '#F56C6C' },
      showSymbol: false,
    },
  ],
}))
</script>

<template>
  <VChart :option="option" autoresize style="height: 400px" />
</template>
