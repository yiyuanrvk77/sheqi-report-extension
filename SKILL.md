---
name: sheqi-report-extension
description: 12377.cn 涉企侵权举报批量自动提交助手。批量/自动完成涉企举报、导入舆情表格或链接、多主体管理、验证码自动识别提交（含风控自适应降频）、生成举报信函、导出今日提交Excel（含审核码）。触发词："sheqi-report"、"涉企举报"、"12377 涉企"、"批量举报"、"企业侵权举报"、"涉企侵权举报"、"我要举报某企业"。
scope: user
is_public: true
version: 1.16.0
---

# sheqi-report 涉企侵权举报批量提交助手

## 何时使用

当用户需要在 **12377.cn（中央网信办违法和不良信息举报中心）** 批量提交「涉企侵权」举报时使用本技能，典型场景：

- 批量举报针对某企业的诽谤诋毁、侮辱谩骂、商业信誉/商品声誉侵害等网络信息
- 导入舆情表格（xlsx/csv）或链接清单，自动整理并批量填表提交
- 管理多个被侵权主体（企业），切换主体批量处理
- 自动识别 12377 验证码（PaddleOCR 在线 API）并提交，遇风控自动降频
- 生成举报信函（docx）、导出当日提交结果 Excel（含查询码/审核码）

触发词：`sheqi-report`、`涉企举报`、`12377 涉企`、`批量举报`、`企业侵权举报`、`涉企侵权举报`。

## 架构与数据隔离

- **代码与数据分离**：技能代码（`scripts/`）是**通用**的，不含任何客户/主体数据。
- **数据目录**：运行时数据默认落在当前工作目录的 `sheqi_data/`，可用环境变量 `SHEQI_DATA_DIR` 覆盖。每次任务在独立会话目录下运行，互不污染。
- 数据目录包含：`subjects.json`（主体）、`records.json`（举报记录）、`results.json`/`results.xlsx`（提交结果）、`documents/<主体>/`（材料文件）、`reports/`（归档 Excel）。

## 环境准备

```bash
# 首次使用：创建虚拟环境并安装依赖（playwright/openpyxl/python-docx/pillow）
python sheqi.py setup

# 若脚本目录下没有 Python，可用 uv：
#   uv run --with playwright,openpyxl,python-docx,pillow sheqi.py setup
```

验证码识别走 **PaddleOCR 在线 API**（PP-OCRv6），本机不安装识别模型。token 读取优先级：

1. **环境变量 `PADDLEOCR_ACCESS_TOKEN`**（最高优先级）：用户可在本机自行配置覆盖；
2. **内嵌默认 token**：skill 已内置一个共享 token 随代码分发，未配置环境变量时自动回退使用，**开箱即用**（所有市场用户共享该 token，消耗其所有者的 AI Studio 额度）。

识别失败时自动转人工输入。

## 材料/文档图片 OCR（识别投诉函、营业执照、身份证等文字）

当需要读取用户上传的**材料图片文字**（投诉函、营业执照、身份证、授权委托书、截图等）时，**直接用内置 `ocr` 命令**：

```bash
python sheqi.py ocr 图片1.jpg 图片2.png ...
```

- 内置共享 token 直连 PaddleOCR 在线 API（`paddleocr.aistudio-app.com`），**开箱即用，无需任何配置**。
- `paddleocr` MCP 工具与内置 `ocr` 命令调用的是同一个 PaddleOCR 后端，但 MCP 需在系统设置单独填引擎+Token（配置文件 `~/.halo/kb-ocr-config.json`）；若未配置会报「OCR 未配置」，此时直接用内置 `ocr` 命令即可。
- **不要**用图片分析 SubAgent（`Task` + `imagePaths`）——它依赖独立视觉模型 API key，通常未配置会报 `AI_LoadAPIKeyError`。
- 识别结果直接打印，供整理举报内容/核对主体信息用。

## 命令用法

> 所有命令在 `scripts/` 目录下运行：`python sheqi.py <子命令>`
>
> 深度文档：`references/import-guide.md`（导入格式/列名别名）、`references/form-guide.md`（表单字段/上传槽位/验证码）、`references/troubleshooting.md`（踩坑排查手册）。

### 1. 主体管理

```bash
# 新增主体（含材料文件注册，扩展名自动识别）
python sheqi.py subject add --name 客户A \
    --company-name "XX有限公司" \
    --company-type MINYINGQIYE \
    --company-nature QITAQIYE \
    --industry I003 \
    --contact-type QITARENYUAN \
    --contact-name 张三 --contact-phone 13800000000 --contact-email a@b.com \
    --license 执照.jpg --id-front 正面.png --id-back 反面.png \
    --auth 授权委托书.png --work-proof 在职证明.jpg

python sheqi.py subject list      # 列出全部主体（* 为当前）
python sheqi.py subject select --name 客户A   # 切换当前主体
python sheqi.py subject show [--name 客户A]   # 查看详情（含材料是否齐全）
python sheqi.py subject set --name 客户A --industry I003   # 更新字段/材料
python sheqi.py subject rm --name 客户A        # 删除主体
```

必填字段说明（12377 表单校验必需）：

| 字段 | 含义 | 示例 |
|------|------|------|
| company_type | 企业类型 | MINYINGQIYE（民营）等 |
| company_nature | 企业性质 | QITAQIYE / SHANGSHIQIYE / NISHANGSHIQIYE |
| industry | 行业分类 | I003（制造业）等 |
| contact_type | 联系人类型 | QITARENYUAN（其他人员）等 |

材料槽位：`license`(营业执照)、`id_front`/`id_back`(身份证正反面)、`auth`(授权委托书)、`work_proof`(在职证明)、`hand_id`(手持身份证)、`letter*`(举报信函)。

### 2. 导入举报记录

> 详细格式/列名别名/去重规则见 `references/import-guide.md`。

```bash
# 支持 xlsx / csv / json，自动识别表头（链接/网址、标题、正文、平台、账号、日期、状态等）
python sheqi.py import --file 舆情表.xlsx --subject 客户A [--limit 20]
```

- 自动去重（按 URL）、跳过非 http(s) 链接、跳过「转发/已删除/已失效」状态。
- 自动整合举报内容（≤500 字），或用自定义模板：`python sheqi.py run --content 模板.txt`（模板写入 `sheqi_data/content_template.txt`）。

### 3. 批量提交（核心）

> 表单字段/上传槽位见 `references/form-guide.md`；验证码抓图方式、风控降频、URL 长度限制等踩坑见 `references/troubleshooting.md`。

```bash
python sheqi.py run --dry-run        # 试运行：填表+上传，不提交（先跑这个核对字段）
python sheqi.py run --headless       # 正式提交（无头浏览器）
python sheqi.py run --headed         # 可见浏览器（调试）
python sheqi.py run --daily 50       # 本地每日软上限 50 条
python sheqi.py run --cool-every 10 --cool-seconds 300   # 每投 10 组主动冷却 5 分钟（默认已开启，可调/可关）
python sheqi.py run --id CMP-... --id CMP-...   # 只提交指定记录
python sheqi.py recover              # 中断后回滚卡死的 submitting 记录
```

- 合并投递（默认开启，无需额外参数）：记录按日期降序（新→旧）、同一天内按 URL 长度升序（短→长）排序，贪心合并——从最短开始尽量往链接框塞，URL 拼接总长超过 500 字符即封组，不跨日期。
- 验证码：默认 PaddleOCR 在线 API 自动识别；`--manual` 转人工输入，`--no-ocr` 关闭 OCR。
- 风控自适应降频：连续验证码错误自动拉长提交间隔并冷却，不硬刚风控。
- 主动冷却（预防风控）：默认每成功投递 10 组主动歇 5 分钟，抢在服务端风控前降速；`--cool-every 0` 关闭，`--cool-every N --cool-seconds M` 自定义。
- 服务端返回「今日举报次数已达上限」时自动停止剩余队列，剩余记录保持 pending 次日可续跑。

### 4. 结果导出

```bash
python sheqi.py records              # 记录状态统计（submitted/failed/pending）
python sheqi.py export               # 导出今日已提交记录 Excel（含查询码/审核码）
python sheqi.py export --date 2026-08-14
python sheqi.py letter --id CMP-...  # 生成单条举报信函 docx
```

## 硬约束

1. **实名信息必须真实**：联系人姓名、电话、邮箱、企业主体均为真实信息，**严禁编造**。
2. **材料合法**：营业执照、身份证、授权委托书等仅限本人/本公司合法持有并授权使用。
3. **先 dry-run 再正式提交**：首次或换主体务必 `--dry-run` 核对表单字段（尤其企业类型/性质/行业/联系人类型四个必填 select）。
4. **不绕过风控**：不批量硬刷、不伪造浏览器特征规避验证码；遇服务端上限即停。
5. **破坏性操作前备份**：删除主体、覆盖数据前先备份 `sheqi_data/`。
