<script setup lang="ts">
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EChartsOption } from 'echarts'

const { t } = useI18n()

const props = defineProps<{
  dryBulbTemperature: number[]
  dewPointTemperature: number[]
  relativeHumidity: number[]
}>()

const option = computed<EChartsOption>(() => ({
  title: { text: t('weather.chart.title'), left: 'center' },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' },
    formatter: (params: any) => {
      if (!Array.isArray(params)) return ''
      const hour = params[0]?.dataIndex ?? 0
      const month = Math.floor(hour / 730) + 1
      const dayOfMonth = Math.floor((hour % 730) / 24) + 1
      const hourOfDay = hour % 24
      let html = `<b>${month}${t('weather.chart.month')}${dayOfMonth}${t('weather.chart.day')} ${hourOfDay}:00</b><br/>`
      for (const p of params) {
        html += `${p.marker} ${p.seriesName}: <b>${p.value?.toFixed(1)}</b>${p.seriesIndex < 2 ? '°C' : '%'}<br/>`
      }
      return html
    },
  },
  legend: {
    data: [
      t('weather.chart.dryBulb'),
      t('weather.chart.dewPoint'),
      t('weather.chart.relHumidity'),
    ],
    bottom: 0,
  },
  xAxis: {
    type: 'category',
    data: Array.from({ length: props.dryBulbTemperature.length }, (_, i) => i + 1),
    axisLabel: {
      formatter: (val: string) => {
        const h = Number(val)
        if (h % 730 === 0) return `${Math.floor(h / 730) + 1}${t('weather.chart.month')}`
        return ''
      },
    },
  },
  yAxis: [
    {
      type: 'value',
      name: '°C',
      position: 'left',
    },
    {
      type: 'value',
      name: '%',
      position: 'right',
      min: 0,
      max: 100,
      splitLine: { show: false },
    },
  ],
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider' },
  ],
  series: [
    {
      name: t('weather.chart.dryBulb'),
      type: 'line',
      data: props.dryBulbTemperature,
      itemStyle: { color: '#E6A23C' },
      showSymbol: false,
      lineStyle: { width: 1 },
    },
    {
      name: t('weather.chart.dewPoint'),
      type: 'line',
      data: props.dewPointTemperature,
      itemStyle: { color: '#67C23A' },
      showSymbol: false,
      lineStyle: { width: 1 },
    },
    {
      name: t('weather.chart.relHumidity'),
      type: 'line',
      yAxisIndex: 1,
      data: props.relativeHumidity,
      itemStyle: { color: '#909399' },
      showSymbol: false,
      lineStyle: { width: 1, type: 'dashed' },
    },
  ],
}))
</script>

<template>
  <VChart :option="option" autoresize style="height: 400px" />
</template>
