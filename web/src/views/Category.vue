<template>
  <div class="page-container">
    <div class="page-card">
      <div class="toolbar">
        <span class="page-title">物料分类管理</span>
        <el-tooltip content="最多支持三级分类" placement="bottom">
          <span class="tip-text"><el-icon><InfoFilled /></el-icon>最多三级，末级可挂物料</span>
        </el-tooltip>
        <div class="spacer"></div>
        <el-button type="primary" :icon="Plus" @click="openCreate(0, null)">新增一级分类</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-tree
        v-loading="loading"
        class="cate-tree"
        :data="tree"
        node-key="id"
        :props="{ label: 'name', children: 'children' }"
        default-expand-all
        :expand-on-click-node="false"
      >
        <template #default="{ data }">
          <div class="tree-node">
            <el-icon class="folder-icon">
              <FolderOpened v-if="!isLeaf(data)" />
              <Folder v-else />
            </el-icon>
            <span class="node-name">{{ data.name }}</span>
            <el-tag size="small" :type="isLeaf(data) ? 'success' : 'info'" effect="light">
              {{ isLeaf(data) ? '末级·可挂物料' : `含 ${childCount(data)} 个子分类` }}
            </el-tag>
            <span class="node-actions">
              <el-button v-if="data.level < 3" link type="primary" size="small" :icon="Plus" @click.stop="openCreate(1, data)">加子类</el-button>
              <el-button link type="warning" size="small" :icon="Edit" @click.stop="openEdit(data)">编辑</el-button>
            </span>
          </div>
        </template>
      </el-tree>
    </div>

    <!-- 新增分类弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.title"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item v-if="dialog.parentLabel" label="上级分类">
          <el-input :model-value="dialog.parentLabel" disabled />
        </el-form-item>
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入分类名称" clearable maxlength="50" />
        </el-form-item>
        <el-form-item label="排序值" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :max="99999" />
          <div class="el-form-item__content-hint">数值越大越靠前</div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, Edit, FolderOpened, Folder, InfoFilled } from '@element-plus/icons-vue'
import { listCategory, createCategory, updateCategory } from '@/api'

const loading = ref(false)
const saving = ref(false)
const flat = ref([]) // 扁平全量分类
const formRef = ref(null)

const tree = computed(() => buildTree(flat.value))

const dialog = reactive({
  visible: false,
  mode: 'create',
  title: '',
  parentId: 0,
  parentLabel: '',
  nodeId: null
})

const form = reactive({ name: '', sort_order: 0 })

const rules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
}

function buildTree(list) {
  const map = new Map()
  list.forEach((c) => map.set(c.id, { ...c, children: [] }))
  const roots = []
  map.forEach((c) => {
    if (c.parent_id === 0) {
      roots.push(c)
    } else {
      const p = map.get(c.parent_id)
      if (p) p.children.push(c)
      else roots.push(c)
    }
  })
  const sort = (arr) => {
    arr.sort((a, b) => (b.sort_order || 0) - (a.sort_order || 0) || a.id - b.id)
    arr.forEach((x) => sort(x.children))
  }
  sort(roots)
  return roots
}

function isLeaf(node) {
  return !flat.value.some((c) => c.parent_id === node.id)
}

function childCount(node) {
  return flat.value.filter((c) => c.parent_id === node.id).length
}

async function load() {
  loading.value = true
  try {
    flat.value = await listCategory()
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.sort_order = 0
}

function openCreate(level, parentNode) {
  dialog.mode = 'create'
  dialog.title = level === 0 ? '新增一级分类' : '新增子分类'
  dialog.parentId = parentNode ? parentNode.id : 0
  dialog.parentLabel = parentNode ? parentNode.name : ''
  dialog.nodeId = null
  resetForm()
  dialog.visible = true
}

function openEdit(node) {
  dialog.mode = 'edit'
  dialog.title = '编辑分类'
  dialog.nodeId = node.id
  dialog.parentId = node.parent_id
  dialog.parentLabel = ''
  form.name = node.name
  form.sort_order = node.sort_order || 0
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
      await createCategory({
        name: form.name,
        parent_id: dialog.parentId,
        sort_order: form.sort_order
      })
      ElMessage.success('新增成功')
    } else {
      await updateCategory(dialog.nodeId, {
        name: form.name,
        sort_order: form.sort_order
      })
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
.tip-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8a94a6;
}
.cate-tree {
  padding: 6px 4px;
}
.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 12px;
  height: 40px;
}
.folder-icon {
  color: #e6a23c;
  font-size: 17px;
}
.node-name {
  font-weight: 500;
  color: #2a3348;
}
.node-actions {
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.15s;
}
.tree-node:hover .node-actions {
  opacity: 1;
}
:deep(.el-form-item__content-hint) {
  margin-left: 12px;
  font-size: 12px;
  color: #a0a8b8;
}
</style>
