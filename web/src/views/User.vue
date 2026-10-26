<template>
  <div class="page-container">
    <div class="page-card">
      <div class="toolbar">
        <span class="page-title">账号管理</span>
        <div class="spacer"></div>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增账号</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="list" stripe>
        <el-table-column type="index" label="#" width="55" align="center" />
        <el-table-column prop="username" label="用户名" min-width="150">
          <template #default="{ row }">
            <el-icon class="text-primary"><UserFilled /></el-icon>
            {{ row.username }}
            <el-tag v-if="row.username === userStore.username" size="small" type="success" class="self-tag">当前登录</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-tag :type="LEVELS[row.level]?.tag || 'info'" effect="light" size="small">
              {{ LEVELS[row.level]?.label || `未知(${row.level})` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="级别" width="90" align="center">
          <template #default="{ row }">Lv.{{ row.level }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button
              type="danger"
              link
              :icon="Delete"
              :disabled="row.username === userStore.username"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新增账号' : '编辑账号'"
      width="460px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            :disabled="dialog.mode === 'edit'"
            placeholder="请输入用户名"
            clearable
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="dialog.mode === 'create' ? '请输入密码' : '留空表示不修改密码'"
          />
        </el-form-item>
        <el-form-item label="角色级别" prop="level">
          <el-radio-group v-model="form.level">
            <el-radio :value="1">普通用户</el-radio>
            <el-radio :value="2">管理员</el-radio>
            <el-radio :value="3">超级管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <div v-if="dialog.mode === 'edit' && form.username === userStore.username" class="self-tip">
        这是当前登录账号：级别不可低于超级管理员（后端同样拦截），密码可改
      </div>
      <template #footer>
        <el-button @click="dialog.visible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, UserFilled } from '@element-plus/icons-vue'
import { listUsers, createUser, updateUser, deleteUser } from '@/api'
import { fmtDateTime } from '@/utils/format'
import { userStore } from '@/store/user'

const LEVELS = {
  1: { label: '普通用户', tag: 'info' },
  2: { label: '管理员', tag: 'warning' },
  3: { label: '超级管理员', tag: 'danger' }
}

const loading = ref(false)
const saving = ref(false)
const list = ref([])
const formRef = ref(null)

const dialog = reactive({ visible: false, mode: 'create' })
const form = reactive({ id: null, username: '', password: '', level: 1 })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    {
      // 新增必填；编辑留空 = 不改密码
      validator: (rule, value, callback) => {
        if (dialog.mode === 'create' && !value) {
          callback(new Error('请输入密码'))
        } else if (value && value.length < 6) {
          callback(new Error('密码至少 6 位'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  level: [{ required: true, message: '请选择角色级别', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    list.value = await listUsers()
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.id = null
  form.username = ''
  form.password = ''
  form.level = 1
}

function openCreate() {
  dialog.mode = 'create'
  resetForm()
  dialog.visible = true
}

function openEdit(row) {
  dialog.mode = 'edit'
  form.id = row.id
  form.username = row.username
  form.password = ''           // 编辑时不回填密码（后端也不返回）
  form.level = row.level
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
    if (dialog.mode === 'create') {
      await createUser({
        username: form.username,
        password: form.password,
        level: form.level
      })
      ElMessage.success('新增成功')
    } else {
      const payload = { level: form.level }
      if (form.password) payload.password = form.password   // 留空 = 不改
      await updateUser(form.id, payload)
      ElMessage.success('保存成功')
    }
    dialog.visible = false
    load()
  } catch (e) {
    /* 拦截器已提示（重名 409 / 级别非法 400 / 不能降自己 400） */
  } finally {
    saving.value = false
  }
}

// 删除账号：二次确认；删自己 / 删最后一个超管时后端 400（拦截器已提示）
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${row.username}」吗？删除后该账号将无法登录！`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删 除', cancelButtonText: '取 消' }
    )
  } catch (e) {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    /* 拦截器已提示 */
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
.self-tag {
  margin-left: 8px;
}
.self-tip {
  margin: -6px 0 10px 86px;
  font-size: 12px;
  color: #e6a23c;
}
</style>
