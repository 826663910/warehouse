<template>
  <div class="login-page">
    <div class="login-bg"></div>
    <div class="login-box">
      <div class="login-brand">
        <div class="brand-icon">
          <el-icon :size="30"><Box /></el-icon>
        </div>
        <h1>库存管理系统</h1>
        <p>Warehouse Inventory Management</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        size="large"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <div class="login-tip">若没有账号，请联系管理员在系统后台注册开通</div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { login } from '@/api'
import { setAuth } from '@/store/user'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  loading.value = true
  try {
    const data = await login(form.username, form.password)
    setAuth(data.access_token, form.username)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(135deg, #0f1f4b 0%, #1e3a8a 45%, #2f6bff 100%);
}
.login-bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 15% 20%, rgba(255, 255, 255, 0.08) 0, transparent 32%),
    radial-gradient(circle at 85% 15%, rgba(255, 255, 255, 0.06) 0, transparent 28%),
    radial-gradient(circle at 70% 90%, rgba(255, 255, 255, 0.05) 0, transparent 35%);
}
.login-box {
  position: relative;
  width: 400px;
  background: rgba(255, 255, 255, 0.97);
  border-radius: 16px;
  padding: 40px 36px 28px;
  box-shadow: 0 20px 60px rgba(2, 10, 35, 0.45);
  backdrop-filter: blur(6px);
}
.login-brand {
  text-align: center;
  margin-bottom: 28px;
}
.brand-icon {
  width: 62px;
  height: 62px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 16px;
  background: linear-gradient(135deg, #2f6bff, #5a8bff);
  box-shadow: 0 8px 20px rgba(47, 107, 255, 0.4);
}
.login-brand h1 {
  margin: 0;
  font-size: 22px;
  color: #17223b;
  letter-spacing: 1px;
}
.login-brand p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #8a94a6;
  letter-spacing: 0.5px;
}
.login-btn {
  width: 100%;
  margin-top: 6px;
  letter-spacing: 6px;
  font-weight: 600;
}
.login-tip {
  margin-top: 18px;
  text-align: center;
  font-size: 12px;
  color: #9aa3b2;
}
</style>
