# 12377 涉企举报表单指南

## 页面流程

1. 打开举报须知页：`https://www.12377.cn/jbxzxq/sql_web.html`
2. 勾选 `#isee`，**真实鼠标点击** `#agree`（JS 直接 `.click()` 不触发跳转），约 1 秒后进入表单页 `sqjb.html`。
3. 表单字段就绪后逐项填写、上传、识别验证码、调用 `submitreportinfo()` 提交。

## 表单字段

| 字段 ID | 内容 | 说明 |
|---|---|---|
| `#entName` | 企业名称 | 文本 |
| `#entType` | 企业类型 | nice-select 单选 |
| `#entNature` | 企业性质 | nice-select 单选 |
| `#entIndustry` | 行业分类 | nice-select 单选 |
| `#entContactType` | 举报人类型 | nice-select 单选 |
| `#reportor_realname` | 联系人姓名 | 文本（存在才填） |
| `#reportor_telephone` | 联系电话 | 文本（存在才填） |
| `#reportor_email` | 电子邮箱 | 文本（存在才填） |
| `#targetName` | 被举报平台名称 | 文本（存在才填） |
| `#targetAccount` | 被举报账号名称 | 文本 |
| `#targetUrl` | 举报网址 | 文本，http(s) |
| `#content` | 举报内容 | ≤500 字 |
| `#entProofType` | 证据种类 | nice-select 多选，P001~P008 |
| `#verifycode_id` | 验证码图片 | 点击可刷新 |
| `#verify_code` | 验证码答案 | 文本 |

## 下拉选项值

- `entType`：`GUOYOUQIYE` 国有企业、`MINYINGQIYE` 民营企业、`WAIZIQIYE` 外资企业、`QITAQIYE` 其他企业
- `entNature`：`SHANGSHIQIYE` 上市企业、`NISHANGSHIQIYE` 拟上市企业、`QITAQIYE` 其他企业
- `entIndustry`：`I001`~`I00x` 行业代码（制造业 `I003`）
- `entContactType`：`LAWYER` 企业法务或委托律师、`QITARENYUAN` 企业其他工作人员
- `entProofType`：`P001`~`P008`（企业自行收集 `P008` 常用）

## 上传槽位（fileMap1~4）

| 槽位 | 材料 | 数量 |
|---|---|---|
| `#upload_file1` | 营业执照 | 1 |
| `#upload_file2` | 身份证正面 + 身份证反面 + 授权委托书 + 在职证明 | 多文件 |
| `#upload_file3` | 举报信（优先放入） | 多文件 |
| `#upload_file4` | 多份举报信（letter2/letter3） | 多文件 |

> ⚠️ **12377 提交校验要求 4 个槽位全部非空**（`submitreportinfo()` 检查 `showfilelist1~4` 均有文件，任一为空 alert "附件不能为空" 并中止提交）。无多余举报信时，须复制 letter 为 letter2 填满卡槽4（`copy` 后 `subject add --file letter2=...` 注册）。

上传后等待页面 `fileMap1~4.size` 与文件数一致再提交。

## 验证码 OCR

- 验证码为数学表达式（如 `9+9=?`）。先抓取 `#verifycode_id` 当前显示的图（`el.screenshot()`，与提交绑定一致）。
- 识别：PaddleOCR 在线 API（PP-OCRv6），token 优先读环境变量 `PADDLEOCR_ACCESS_TOKEN`，未设置时回退到内嵌共享 token（开箱即用）。**本机不安装本地识别模型**。
- 注意：`a÷b` 不整除视为识别失败；`a,b>20` 且两位数是 OCR 拼字，取首字符。
- 识别失败：点击验证码刷新重试，最多 4 次；仍失败转人工输入。

## 提交结果判定

- 覆盖 `window.alert/confirm` 捕获弹窗，监听 POST 响应（`addsq`/`submit` 关键字）与 URL 跳转（`jbhz.html`）。
- 成功：弹窗/响应/页面出现“查询码”+ 一串编码，正则提取。
- 验证码错误：弹窗含“验证码”→ 刷新重试。
- 每日上限：响应 code `5000` 或弹窗含“超出当天/举报次数”→ 停止剩余队列。
- 超时未判定：按失败记录，可重跑续传。

## 离线测试（不消耗真实额度）

skill 自带模拟表单 `scripts/fixtures/form_test.html`（换电脑后无需旧插件目录）（固定验证码答案 `7`、成功查询码 `XTEST12345678`）。用法：

```bat
cd <skill目录>\scripts\fixtures
python -m http.server 8765 --bind 127.0.0.1
```

```bat
python sheqi.py run --dry-run --headless --limit 1 --base-url http://127.0.0.1:8765/form_test.html
```

fixture 校验：URL 必须 http(s)、内容 ≤500 字、卡槽 1-3 各至少 1 个文件（卡槽 4 可选）、验证码答案固定 `7`。
