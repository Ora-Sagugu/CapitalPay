# 项目启动与 GitHub 推送说明

适用环境：Windows PowerShell。本地使用 **SQLite**，无需 Docker / PostgreSQL / Redis / Celery。

远程仓库：https://github.com/Ora-Sagugu/B2B-payment-system.git  
（本机已配置 `origin` 指向该地址。）

---

## 一、日常启动

### 1. 进入项目并激活虚拟环境

```powershell
cd d:\ProgramData\b2b_payment_system
.\.venv\Scripts\Activate.ps1
```

若提示无法执行脚本，可先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. 终端 1 — 启动后端（端口 8001）

```powershell
cd d:\ProgramData\b2b_payment_system
.\.venv\Scripts\Activate.ps1
python manage.py runserver 8001
```

### 3. 终端 2 — 运营后台（端口 9000）

```powershell
cd d:\ProgramData\b2b_payment_system\frontend\client_portal
npm run dev
```

### 4. 终端 3（可选）— 客户端门户（端口 9001）

```powershell
cd d:\ProgramData\b2b_payment_system\frontend\customer_portal
npm run dev
```

### 访问地址

| 地址 | 说明 |
|------|------|
| http://localhost:9000/ | 运营后台 |
| http://localhost:9001/ | 客户端门户 |
| http://127.0.0.1:8001/admin/ | Django Admin |
| http://127.0.0.1:8001/api/docs/ | Swagger UI |

---

## 二、首次安装 / 换电脑时

```powershell
cd d:\ProgramData\b2b_payment_system

# Python 3.11 或 3.12
# python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data
# 需要清空重灌：python manage.py seed_data --reset
# 需要管理员：python manage.py createsuperuser

cd frontend\client_portal
npm install

cd ..\customer_portal
npm install
```

定时任务（可选）：

```powershell
python manage.py run_scheduled_jobs --all
# 或单个：python manage.py run_scheduled_jobs --job close_expired_orders
```

---

## 三、推送到 GitHub

仓库：https://github.com/Ora-Sagugu/B2B-payment-system.git

### 首次推送（当前机器一般已配好 origin）

```powershell
cd d:\ProgramData\b2b_payment_system
git status
git add .
git commit -m "Initial commit: B2B payment system (SQLite MVP)"
git push -u origin main
```

### 若尚未添加远程

```powershell
git remote add origin https://github.com/Ora-Sagugu/B2B-payment-system.git
git push -u origin main
```

### 认证说明

- 浏览器登录 GitHub，或使用 Personal Access Token（HTTPS）
- 也可：`gh auth login` 后再 `git push`

### 不要提交的内容（已由根目录 `.gitignore` 排除）

- `.venv/`、`node_modules/`、`dist/`
- `db.sqlite3`、`.env`、本地上传的 `media/`

### 以后日常推送

```powershell
git add .
git commit -m "简述本次改动"
git push
```
