# Spree Commerce 本地启动手册

本文档记录 `D:\测试智能体\my-store` 这个 Spree Commerce 项目的启动、访问和常见问题处理流程。

## 1. 当前项目位置

项目已经创建完成，路径是：

```powershell
D:\测试智能体\my-store
```

不要再重复执行：

```powershell
npx create-spree-app@latest my-store
```

这个命令只用于创建项目，已经创建过就别再跑。再次运行会提示：

```text
Directory my-store is not empty.
```

意思是 `my-store` 目录已经有内容了，不是报错崩了。

## 2. 启动 Spree 后端 / API / Admin

打开一个 PowerShell 窗口，执行：

```powershell
cd D:\测试智能体\my-store
npx spree dev
```

第一次启动可能比较慢，因为它会：

- 拉取 Docker 镜像
- 启动数据库等服务
- 初始化数据库
- 加载 sample data
- 配置 API key

这个窗口不要关，关了后端服务可能就停了。

## 3. 打开后台 Admin

后端启动后，浏览器访问：

```text
http://localhost:3000/admin
```

后台账号：

```text
Email: spree@example.com
Password: spree123
```

Store API 地址：

```text
http://localhost:3000/api/v3/store
```

商品 API 可尝试：

```text
http://localhost:3000/api/v3/store/products
```

## 4. 启动前端 Storefront

再打开一个新的 PowerShell 窗口，执行：

```powershell
cd D:\测试智能体\my-store\apps\storefront
npm run dev
```

注意是：

```powershell
npm run dev
```

不是：

```powershell
npm run de
```

少打一个 `v` 会报：

```text
npm error Missing script: "de"
```

前端启动后，浏览器访问：

```text
http://localhost:3001
```

## 5. 端口说明

默认端口：

| 服务 | 地址 |
|---|---|
| Spree Admin / API | http://localhost:3000 |
| Storefront 前端 | http://localhost:3001 |

如果看到：

```text
Port 3000 is in use
```

意思是 3000 端口已经被占用，可能是 Spree 后端已经启动，也可能是其他程序占用了。

先访问：

```text
http://localhost:3000/admin
```

如果能打开后台，就不用管这个提示。

如果前端提示 3001 被占用，可以改用 3002：

```powershell
cd D:\测试智能体\my-store\apps\storefront
npm run dev -- -p 3002
```

然后访问：

```text
http://localhost:3002
```

## 6. 停止服务

停止前端：

在运行 `npm run dev` 的窗口按：

```text
Ctrl + C
```

停止后端：

在运行 `npx spree dev` 的窗口按：

```text
Ctrl + C
```

或者在项目根目录执行：

```powershell
cd D:\测试智能体\my-store
npx spree stop
```

如果要停止并删除 Docker 容器网络等资源，可以执行：

```powershell
cd D:\测试智能体\my-store
docker compose down
```

## 7. 常用检查命令

查看项目根目录脚本：

```powershell
cd D:\测试智能体\my-store
npm run
```

查看前端脚本：

```powershell
cd D:\测试智能体\my-store\apps\storefront
npm run
```

查看 3000 / 3001 端口是否被占用：

```powershell
netstat -ano | Select-String ':3000|:3001'
```

## 8. 论文实验中怎么写

论文里可以写：

> 本文选取 Spree Commerce 作为开源被测电商平台。实验环境采用本地固定版本部署，后端 Admin/API 服务运行于 `http://localhost:3000`，前端 Storefront 运行于 `http://localhost:3001`。测试流程覆盖商品浏览、商品搜索、购物车、结算和用户账户等典型电商业务场景。

## 9. 最短启动流程

以后你只需要记住这个：

第一个 PowerShell：

```powershell
cd D:\测试智能体\my-store
npx spree dev
```

第二个 PowerShell：

```powershell
cd D:\测试智能体\my-store\apps\storefront
npm run dev
```

浏览器打开：

```text
http://localhost:3000/admin
http://localhost:3001
```
