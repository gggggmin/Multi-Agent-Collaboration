# Spree 需求文档使用说明

本目录 `experiments/requirements_spree` 是为正式 Spree Commerce 实验重新整理的需求文档，不再使用旧的自研 Flask 电商演示系统需求。

## 文件结构

- `product_requirements.md`：商品首页、商品目录、商品详情、变体、多区域路径
- `search_requirements.md`：关键词搜索、分类筛选、价格筛选、库存筛选、排序、清除筛选
- `cart_requirements.md`：加入购物车、数量修改、删除、空购物车、进入结算
- `checkout_requirements.md`：游客/登录结算、地址、配送、优惠码、支付、订单创建
- `account_requirements.md`：注册、登录、订单历史、订单详情、地址簿
- `../ground_truth_spree.json`：对应需求点标注集，共 47 个需求点

## 来源说明

这些需求基于以下来源整理：

1. Spree Storefront README 中列出的官方功能：Product Catalog、Product Details、Shopping Cart、One-page Checkout、Customer Account、Multi-Region Support。
2. 本地 Spree 项目结构：`my-store/apps/storefront/src/components/products`、`cart`、`checkout`、`account`、`addresses`、`search` 等目录。
3. Spree Storefront 默认路径设计：`/us/en` 及多区域 URL 结构。

## 注意

正式实验前必须完成一次人工校准：

- 启动本地 Spree 后端和 storefront。
- 检查 sample data 中实际商品名称、分类、筛选项、优惠码和支付方式。
- 根据页面实际文案和选择器修正测试步骤。
- 不要把这套文档写成 Spree 官方原始需求文档，它是“基于 Spree 功能整理的实验需求文档”。

论文中建议表述：

> Based on the official Spree Storefront features and the locally scaffolded project structure, this study reconstructs a requirement document set for product browsing, search/filtering, cart management, checkout, and customer account workflows. The reconstructed requirements are used as the experimental requirement corpus and ground-truth set for test generation evaluation.
