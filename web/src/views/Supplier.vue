<template>
  <div class="page-container">
    <div class="page-card">
      <div class="toolbar">
        <span class="page-title">供应商管理</span>
        <div class="spacer"></div>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增供应商</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="list" stripe @row-click="goToInventory">
        <el-table-column type="index" label="#" width="55" align="center" />
        <el-table-column prop="name" label="供应商名称" min-width="160">
          <template #default="{ row }">
            <el-icon class="text-primary"><OfficeBuilding /></el-icon>
            {{ row.name }}
          </template>
        </el-table-column>
        <el-table-column prop="contact" label="联系人" width="140">
          <template #default="{ row }">{{ row.contact || '—' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="联系电话" width="160">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click.stop="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新增供应商' : '编辑供应商'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item label="供应商名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入供应商名称" clearable />
        </el-form-item>
        <el-form-item label="联系人" prop="contact">
          <el-input v-model="form.contact" placeholder="请输入联系人" clearable />
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入联系电话" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, Edit, OfficeBuilding } from '@element-plus/icons-vue'
import { listSupplier, createSupplier, updateSupplier } from '@/api'
import { fmtDateTime } from '@/utils/format'

const router = useRouter()

// 整行点击 = 跳到库存页并按该供应商过滤；编辑按钮已 .stop，不会冒泡到这里
function goToInventory(row) {
  if (window.getSelection()?.toString()) return   // 防止选文字时误触
  router.push({ path: '/inventory', query: { supplier_id: row.id } })
}

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const formRef = ref(null)

const dialog = reactive({ visible: false, mode: 'create' })
const form = reactive({ id: null, name: '', contact: '', phone: '' })

const rules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    list.value = await listSupplier()
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.id = null
  form.name = ''
  form.contact = ''
  form.phone = ''
}

function openCreate() {
  dialog.mode = 'create'
  resetForm()
  dialog.visible = true
}

function openEdit(row) {
  dialog.mode = 'edit'
  form.id = row.id
  form.name = row.name
  form.contact = row.contact || ''
  form.phone = row.phone || ''
  dialog.visible = true
}

async function submit() {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      contact: form.contact || null,
      phone: form.phone || null
    }
    if (dialog.mode === 'create') {
      await createSupplier(payload)
      ElMessage.success('新增成功')
    } else {
      await updateSupplier(form.id, payload)
      ElMessage.success('保存成功')
    }
    dialog.visible = false
    load()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-title {
  font-size: 16px;
  font-weight: 600;
}
.text-primary {
  color: var(--el-color-primary);
  vertical-align: -2px;
  margin-right: 4px;
}
/* 整行可点：给出鼠标反馈（按钮本身是 pointer，不受影响） */
:deep(.el-table__row) {
  cursor: pointer;
}
</style>
