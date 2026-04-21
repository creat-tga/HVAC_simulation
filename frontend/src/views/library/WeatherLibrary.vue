<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox, type UploadRawFile } from 'element-plus'
import { Delete, Search, UploadFilled } from '@element-plus/icons-vue'
import { listWeatherFiles, uploadWeatherFile, deleteWeatherFile } from '@/api/library'
import type { WeatherFile } from '@/types/library'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()

const list = ref<WeatherFile[]>([])
const loading = ref(false)
const search = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await listWeatherFiles(search.value || undefined)
    list.value = data
  } finally {
    loading.value = false
  }
}

onMounted(load)

// Upload
const upDlg = ref(false)
const upFile = ref<File | null>(null)
const upMeta = ref({ name: '', province: '', city: '' })

function beforeUpload(file: UploadRawFile) {
  if (!file.name.toLowerCase().endsWith('.epw')) {
    ElMessage.error(t('lib.weather.onlyEpw'))
    return false
  }
  upFile.value = file
  upMeta.value.name = file.name.replace(/\.epw$/i, '')
  return false // prevent auto-upload
}

async function doUpload() {
  if (!upFile.value) return
  await uploadWeatherFile(upFile.value, upMeta.value)
  ElMessage.success(t('lib.weather.uploadSuccess'))
  upDlg.value = false
  upFile.value = null
  await load()
}

async function handleDelete(wf: WeatherFile) {
  await ElMessageBox.confirm(t('common.deleteConfirm'), t('common.warning'), { type: 'warning' })
  await deleteWeatherFile(wf.id)
  ElMessage.success(t('common.deleteSuccess'))
  await load()
}

const canDelete = (wf: WeatherFile) => auth.isAdmin || (!wf.is_preset && wf.owner_id != null)
</script>

<template>
  <div class="lib-view">
    <div class="lib-header">
      <h1>{{ t('lib.weather.title') }}</h1>
      <el-button type="primary" :icon="UploadFilled" @click="upDlg = true">
        {{ t('lib.weather.upload') }}
      </el-button>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="search"
        :prefix-icon="Search"
        :placeholder="t('lib.weather.searchPlaceholder')"
        clearable
        style="width: 320px"
        @change="load"
      />
    </div>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="name" :label="t('common.name')" min-width="200" show-overflow-tooltip />
      <el-table-column prop="province" :label="t('lib.weather.province')" width="100" />
      <el-table-column prop="city" :label="t('lib.weather.city')" width="120" />
      <el-table-column :label="t('lib.weather.location')" width="180">
        <template #default="{ row }">
          <span v-if="row.latitude != null">{{ row.latitude.toFixed(2) }}°, {{ row.longitude?.toFixed(2) }}°</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('lib.weather.elev')" width="100">
        <template #default="{ row }">{{ row.elevation?.toFixed(0) || '-' }} m</template>
      </el-table-column>
      <el-table-column :label="t('lib.weather.source')" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_preset" type="info" size="small">{{ t('lib.preset') }}</el-tag>
          <el-tag v-else type="success" size="small">{{ t('lib.userUpload') }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('common.operation')" width="100">
        <template #default="{ row }">
          <el-button
            v-if="canDelete(row)"
            type="danger"
            size="small"
            :icon="Delete"
            text
            @click="handleDelete(row)"
          />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="upDlg" :title="t('lib.weather.upload')" width="480px">
      <el-form label-width="100px">
        <el-form-item :label="t('lib.weather.fileLabel')" required>
          <el-upload
            :auto-upload="false"
            :show-file-list="!!upFile"
            :before-upload="beforeUpload"
            accept=".epw"
            :limit="1"
          >
            <el-button>{{ t('lib.weather.chooseFile') }}</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item :label="t('common.name')">
          <el-input v-model="upMeta.name" />
        </el-form-item>
        <el-form-item :label="t('lib.weather.province')">
          <el-input v-model="upMeta.province" />
        </el-form-item>
        <el-form-item :label="t('lib.weather.city')">
          <el-input v-model="upMeta.city" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="upDlg = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :disabled="!upFile" @click="doUpload">{{ t('common.upload') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lib-view { padding: 24px 28px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.lib-header h1 { margin: 0; font-size: 22px; color: #0f172a; }
.filter-bar { margin-bottom: 12px; }
</style>
