# sheqi-report · 12377 涉企侵权举报批量提交助手

一个用于在 **12377.cn（中央网信办违法和不良信息举报中心）** 批量提交「涉企侵权」举报的 Halo Skill。

批量/自动完成涉企举报：多主体档案管理、舆情表格/链接批量导入、Playwright 自动填表、PaddleOCR 在线验证码识别（含风控自适应降频）、举报信函生成、今日提交结果 Excel 导出（含审核码）。

## 功能

- **多主体管理**：维护多个被侵权企业（主体），切换主体批量处理
- **批量导入**：xlsx / csv / tsv / json / 粘贴文本，自动识别表头与列名别名，自动去重与状态过滤
- **自动填表提交**：Playwright 驱动真实浏览器，自动填表 + 上传材料 + 提交
- **验证码识别**：PaddleOCR 在线 API（PP-OCRv6），无本地模型依赖；识别失败自动转人工输入
- **材料图片 OCR**：`python sheqi.py ocr 图片.jpg` 直接识别投诉函、营业执照、身份证等材料文字，开箱即用
- **风控自适应降频**：连续验证码错误自动拉长间隔 + 冷却，遇服务端「今日上限」自动停止剩余队列
- **结果导出**：导出当日已提交记录 Excel（含查询码/审核码），生成举报信函 docx

## 目录结构

```
sheqi-report/
├── SKILL.md              # 技能入口（触发词 / 命令 / 硬约束）
├── marketplace.json      # 发布元数据（含 secret 环境变量声明）
├── references/           # 深度文档
│   ├── form-guide.md     # 表单字段 / 上传槽位 / 验证码
│   ├── import-guide.md   # 导入格式 / 列名别名 / 去重规则
│   └── troubleshooting.md# 踩坑排查手册
└── scripts/              # 核心代码
    ├── sheqi.py          # CLI 入口
    ├── sheqi_lib.py      # 核心库
    ├── requirements.txt  # 依赖
    └── fixtures/         # 离线模拟表单（自测用）
```

## 快速开始

```bash
cd scripts
python sheqi.py setup          # 首次：创建虚拟环境并安装依赖
python sheqi.py subject add --name 客户A --company-name "XX有限公司" \
    --company-type MINYINGQIYE --company-nature QITAQIYE --industry I003 \
    --contact-type QITARENYUAN --contact-name 张三 --contact-phone 13800000000 \
    --contact-email a@b.com --license 执照.jpg --id-front 正面.png \
    --id-back 反面.png --auth 授权.png --work-proof 在职证明.jpg
python sheqi.py import --file 舆情表.xlsx --subject 客户A
python sheqi.py run --dry-run      # 试运行（不提交）
python sheqi.py run --headless     # 正式提交
python sheqi.py export             # 导出今日已提交 Excel
```

## 验证码识别（PaddleOCR 在线 API）

识别走 **PaddleOCR 在线 API（PP-OCRv6）**，本机不安装识别模型。token 读取优先级：

1. **环境变量 `PADDLEOCR_ACCESS_TOKEN`**（最高优先级）：自行配置即可覆盖默认值；
2. **内嵌默认 token**：skill 已内置一个共享 token 随代码分发，未配置环境变量时自动回退使用，**开箱即用**（所有市场用户共享该 token，消耗其所有者的 AI Studio 额度）。

识别失败时自动转人工输入。

> 自备 token：在 [AI Studio PaddleOCR](https://aistudio.baidu.com/paddleocr) 申请，然后设置环境变量 `PADDLEOCR_ACCESS_TOKEN=<你的 token>`。

## 材料图片 OCR（投诉函 / 营业执照 / 身份证等）

读取材料图片文字（投诉函、营业执照、身份证、授权委托书、截图等）直接用内置 `ocr` 命令：

```bash
cd scripts
python sheqi.py ocr 投诉函.jpg 营业执照.png ...
```

内置共享 token 直连 PaddleOCR 在线 API，开箱即用；返回纯文本供整理举报内容 / 核对主体信息。

## 硬约束

- 实名信息必须真实，严禁编造
- 材料（营业执照、身份证、授权委托书）仅限本人/本公司合法持有并授权使用
- 首次或换主体务必先 `--dry-run` 核对表单字段
- 不批量硬刷、不伪造浏览器特征规避验证码、不绕过风控
- 破坏性操作前先备份 `sheqi_data/`

> 完整说明见 [SKILL.md](./SKILL.md)。
