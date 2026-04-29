<template>
  <div class="admin-forbidden">
    <section>
      <span>403</span>
      <h1>没有后台权限</h1>
      <p>当前账号没有 `admin:access` 权限，请使用管理员账号登录。</p>
      <RouterLink to="/chat">返回聊天</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.admin-forbidden {
  display: grid;
  place-items: center;
  width: 100%;
  min-height: 100dvh;
  background: #eef1f4;
}

section {
  width: min(460px, calc(100% - 32px));
  padding: 28px;
  border: 1px solid #d8dee5;
  border-radius: 8px;
  background: #ffffff;
}

span {
  color: #9d3441;
  font-weight: 800;
}

h1 {
  margin: 8px 0;
}

a {
  display: inline-flex;
  margin-top: 16px;
  border-radius: 8px;
  padding: 10px 14px;
  background: #17202a;
  color: #ffffff;
}
</style>
