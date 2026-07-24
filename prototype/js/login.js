    function handleLogin(event) {
      event.preventDefault();
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      const remember = document.getElementById('remember').checked;

      // 原型演示：显示登录信息
      alert(`登录信息：\n账号：${username}\n记住我：${remember ? '是' : '否'}\n\n（原型演示，实际需调用后端 API）`);

      // 实际登录逻辑（示例）
      // fetch('/api/auth/login', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ username, password, remember })
      // }).then(res => res.json()).then(data => {
      //   if (data.success) {
      //     window.location.href = '/index.html';
      //   } else {
      //     alert(data.message || '登录失败');
      //   }
      // });
    }

    function handleSSO() {
      alert('企业 SSO 登录（原型演示）\n\n实际实现将跳转到企业统一认证页面');
      // window.location.href = '/api/auth/sso/redirect';
    }

    // 键盘快捷键支持
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') {
        document.querySelector('form').requestSubmit();
      }
    });
