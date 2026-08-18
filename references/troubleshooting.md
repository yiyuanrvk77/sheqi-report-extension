# 12377 涉企举报：踩坑与排查手册（实战沉淀）

> 本文档沉淀自真实批量提交实战中遇到的各类问题与解决方案，按类别分门别类。遇到问题时先按此手册排查。
>
> **v1.10.0 重要修订**：1.2/1.3 节纠正 v1.5.0 的错误结论——验证码抓图**必须用 `el.screenshot()`**（`page.request` 重新下载会导致验证码不同步、永远"验证码错误"）；新增五.7 节"无效长度url"（服务端 URL 总长限制约 480，前端 500 是误导）。
>
> **v1.15.0 边界调整**：应需求将 URL 拼接总长上限由 480 放宽为 **500**（`url_max` 三处默认值统一 500）。⚠️ 注意：实测 495 曾被服务端拒（安全线 ~481~494），塞满到 481~500 之间的组存在「无效长度url」风险；若批量时遇到该报错，将 `url_max` 调回 480/494 即可。

## 一、验证码识别（最核心，最容易踩坑）

### 1.1 两类验证码要分清

12377 有**两个不同的验证码**，识别方式完全不同：

| 验证码 | 出现位置 | 形态 | 识别方式 |
|---|---|---|---|
| **云盾保护页验证码** | 进入表单前的拦截页 | `#cap-img` + `#ans` + `#submit`，**形态多样**：数学算式 / 字母 / 中文词语 | `pass_captcha_protection()`：算式→填计算结果；字母/中文→填原文 |
| **表单页验证码** | 真实表单 `sqjb.html` | `#verifycode_id` + `#verify_code`，**数学算式**（如 `7+6=?`、`4×6=?`） | `ocr_captcha()` → `parse_math()` 解析算式 |

**关键1：表单页验证码是「数学加减乘除算式」，不是汉字、不是滑块。** 若 OCR 识别出汉字（如"已"、"电脑"、"竣"），说明图片抓错了（抓到了别的图）。

**关键2：保护页验证码形态多样（算式/字母/中文都有），必须全形态兼容：**
- 算式型（`4×6=?`）→ **填计算结果 `24`**，不能填算式原文！
- 字母型（`JcDhy`）→ 填原文
- 中文型（`街道`）→ 填原文
- 识别顺序：`ocr_captcha_protect()` 取文本 → `parse_math()` 解析算式 → 多路 OCR 兜底算式 → 否则填原文

### 1.2 抓图方式决定成败（最重要教训，v1.10.0 纠正）

**必须用 `el.screenshot()` 截取页面当前显示的验证码图，严禁用 `page.request.get(src)` 重新下载！**

- ❌ `page.request.get(el.src)` → **服务端每次请求都会生成新验证码**，识别结果与页面提交校验的验证码不是同一张 → **永远"验证码错误"**（实测 4/4 张图 md5 完全不同；表现为 OCR 识别全对、提交必失败）
- ✅ `el.screenshot()` → 截取页面当前渲染的验证码图（130×48），与提交绑定的验证码**严格一致** → 修复后实测 20 组提交全部一次通过

> ⚠️ **历史教训**：v1.5.0 曾误判为「screenshot 是小图识别率低、request 下载原图识别率高」，据此把 `get_captcha_bytes` 改为优先 `page.request`——该结论只验证了"识别率"，没验证"图是否与提交绑定一致"，导致连续多版永远"验证码错误"。**验证码识别的正确性判断标准：识别结果 + 服务端是否接受（出现查询码），缺一不可；只验证识别率不验证提交通过率，会得出完全相反的结论。**

`get_captcha_bytes()` v1.10.0 已改为「**优先 el.screenshot()，page.request 下载仅作最后兜底**」。

### 1.3 表单页验证码抓取方式（实测结论）

```python
el = page.query_selector("#verifycode_id")
img_bytes = el.screenshot()  # 截取页面当前显示的验证码图（与提交绑定一致）
```

实测抓取方式对比（关键看"提交是否通过"）：
- `el.screenshot()`：页面当前图 → 与提交校验一致 → **提交通过** ✅
- `page.request.get(src)`：重新请求生成**新图** → 与提交校验不一致 → **提交必败** ❌
- 页面内 `fetch(src).dataURL`：同样会触发服务端生成新图 → 提交必败 ❌（且会碰到加速乐 JSL HTTP 521）

**判断抓图方式是否正确的唯一标准：填识别结果后能否拿到查询码。识别率再高，图对不上提交校验就是白搭。**

### 1.4 PaddleOCR 返回结构

`ocr_captcha()` 返回：
```python
{'answer': 13, 'expr': '7+6=13', 'votes': 1, 'total': 1, 'raws': [...]}
```
`parse_math()` 支持 `+ - × x X * / ÷`，注意：
- `a÷b` 不整除 → 视为识别失败
- `a,b>20` 且两位数是 OCR 拼字 → 自动取首字符
- 识别失败 → 刷新验证码重试，最多 4 次

### 1.5 验证码刷新

```python
def refresh_captcha(page):
    # 给 src 加时间戳强制刷新
    el.src = base + '?' + Date.now()
```
刷新后等 1.2 秒再抓图。

## 二、环境变量 / OCR 凭据

### 2.1 401 Unauthorized 的根因：token 缺失或失效

**症状**：PaddleOCR 在线 API 报 `401 Unauthorized`（`AuthError` / `Authentication failed`）。
**根因**：token 未配置、为空或已失效。
**解决**：
1. `_paddle_token()` **仅从环境变量 `PADDLEOCR_ACCESS_TOKEN` 读取**（不落文件）；
2. token 失效时，去 AI Studio（https://aistudio.baidu.com/paddleocr）重新申请并更新环境变量；
3. 确认环境变量已正确设置（`os.environ.get("PADDLEOCR_ACCESS_TOKEN")` 非空）。

### 2.2 凭据配置说明

`_paddle_token()` **仅从环境变量 `PADDLEOCR_ACCESS_TOKEN` 读取**。
识别走 PaddleOCR 在线 API（PP-OCRv6），**本机不安装识别模型**；识别失败转人工输入。

## 三、进程管理（Windows）

### 3.1 Start-Process 重定向报错

**症状**：`Start-Process` 重定向 stdout/stderr 报 `Input redirection is not supported, exiting the process immediately`。
**根因**：Windows 系统级问题（PowerShell Start-Process 不支持输入重定向）。
**解决**：改用 Python `subprocess.Popen` 启动器，显式指定 stdout/stderr 到日志文件。

### 3.2 venv python.exe 会 spawn 系统 Python 子进程

**症状**：杀掉 venv python 主进程后，还有系统 Python 进程在跑（如 PID 14804/17888）。
**关键**：**这是正常现象，勿杀！** venv 的 python.exe 只是启动器，会派生真正的 Python 解释器进程。杀掉真进程会导致任务中断。

### 3.3 Python stdout 块缓冲致日志 0 字节

**症状**：日志文件一直是 0 字节，看不到输出。
**根因**：Python stdout 默认块缓冲，重定向到文件时不实时 flush。
**解决**：启动时加 `-u` 参数（无缓冲），或代码里 `print(..., flush=True)`。

### 3.4 前后台启动流程（推荐）

```python
# 后台运行
proc = subprocess.Popen([python, "-u", script, ...],
                        stdout=open(log, "w"), stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
# 前台可见（调试验证码时用）
proc = subprocess.Popen([python, "-u", script, ...])  # 不加 CREATE_NO_WINDOW
```

## 四、表单进入流程（sql_web → sqjb）

### 4.1 页面跳转链路

```
sql_web.html（入口/须知页）
  → 勾选 #isee + 真实鼠标点击 #agree（JS .click() 不触发跳转！）
  → 约 1 秒后自动跳转 sqjb.html（真实表单页）
```

**必须从 sql_web.html 进入**，直接访问首页 `https://www.12377.cn/` 或表单页 URL 会卡在等待 `#isee`（15 秒超时 × 3 次）。

### 4.2 多标签页陷阱

**症状**：第一次尝试超时后遗留旧标签页（如 `index.html` + `sql_web.html`），第二次成功才打开新标签（`sqjb.html`）。用户看到的是旧标签页，误以为没进去。
**排查**：检查 `page.context.pages` 的 URL 列表，确认 `sqjb` 页存在；`open_form()` 会自动切换到 sqjb 标签页。

### 4.3 超时重试

`open_form()` 最多重试 3 次；每次先清掉 `__jsl_clearance_s` 相关状态重新 goto。若连续失败，检查：
1. 是否从 sql_web.html 进入
2. 加速乐 JS 挑战是否自动通过（HTTP 521 → 自动生成 cookie）
3. 云盾保护页是否 OCR 通过

## 五、12377 防护机制（三层）

1. **加速乐 JS 挑战**：`HTTP 521`，自动执行 JS 生成 `__jsl_clearance_s` cookie（约 1 小时有效）
2. **云盾验证码保护页**：「本站开启了验证码保护」→ `#cap-img` 图验证码 + `#ans` 输入 + `#submit` 提交，OCR 通过后进入真实页面
3. **表单页数学算式验证码**：见「一、验证码识别」

**cookie 有效期约 1 小时**：长时间批量任务中若失败，先检查 cookie 是否过期，重新 open_form。

## 五.5、合并分组策略（默认始终合并）

**日期降序（新→旧），同一天内按 URL 长度升序（短→长），贪心塞满 500 字符**。合并为默认行为，无需 `--merge` 参数；从最短 URL 开始尽量往链接框塞，URL 拼接总长超过 500 字符即封组另起一组，**不跨日期**（同一天塞满后剩余仍在同一天，绝不与别的日期混拼）。

- 字段长度限制：
  - 举报网站名称（#targetName）≤ **50 字**
  - 举报账号名称（#targetAccount）≤ **50 字**
  - 详细举报网址（#targetUrl 多行）总长前端校验 ≤ **500 字符**，但**服务端更严**：实测拼接总长 495 被拒（"无效长度url"）、481 通过，代码按 **500 上限**贪心封组（⚠️ v1.15.0 放宽后，481~500 区间存在被拒风险）
  - 具体举报内容（#content）≤ **500 字**（CONTENT_MAX 截断）
- 验证命令：`sheqi.py run --subject X --dry-run`（只填表不提交，可验证分组与 URL 长度）

## 五.6、验证码风控与自适应降频（v1.7.0）

**症状**：连续多组提交返回 `code 3104 验证码错误`，但 OCR 识别结果全对（`9+8=17`、`5×4=20`），重试 4 次仍失败。
**判断**：不是识别问题，是**提交频率过高触发服务端验证码风控**（连续 12 组约 8 分钟、每组 37 秒后出现）。
**对策（已内置自适应降频）**：
- 连续 3 次 `captcha_error`（提交返回 3104）→ 自动将组间隔翻倍（60→120→240…上限 600 秒）+ 冷却 2 倍间隔
- 成功一次即清零风控计数；无需人工干预
- 建议正式跑用 `--interval 60` 起步，遇风控自动降频
- 冷却 20 分钟以上风控才会解除（实测 20 分钟仍可能中招，需配合降频）
- 若持续失败：先停 30 分钟+再低频重跑，或检查 IP/账号是否被临时限制

## 五.7、"无效长度url"（服务端 URL 总长限制，v1.10.0 实测）

**症状**：OCR 识别正确、验证码通过，但提交后服务端返回 `无效长度url`（`alert(data["msg"])`）。
**误判陷阱**：前端校验文案是"不能超过500字符"（`HARMTEXT_MAXSIZE=500`），但**服务端限制比前端更严**。实测：
- 拼接总长 **495**（8 条）→ 被拒"无效长度url"
- 拼接总长 **481**（6 条）→ 通过
- 单条 URL 长度无关（成功组有 178 字符的单条）

**根因**：组内 URL 拼接总长逼近/超过服务端 ~480 字符实际上限。
**修复**（v1.11.0 已内置）：
- 合并改为**默认始终开启**，贪心塞满 500：日期降序 + 同一天 URL 短→长 + 不跨日期
- URL 总长上限 **500**（`group_records_by_date` 贪心封组，超出即另起一组）
- 已失败的组重置为 pending 后，次日重跑自动按新策略重新分组

**排查**：失败记录 error 为"无效长度url"时，检查该组 URL 拼接总长（`sum(len(u)+1 for u in urls)`，+1 为换行符）；极端单条 URL 本身 >500 字符会单独成组（无法拆分），需人工处理该链接。

## 六、每日提交上限

- 服务端返回 `今日举报次数已达上限`（code 5000 / 弹窗含"超出当天/举报次数"）→ **自动停止剩余队列**
- 本地记录可能显示"今日成功 0 条"，但服务端已限额（**可能因为之前测试/调试消耗了配额**）
- 处理：剩余记录保持 pending，**次日直接重跑** `python sheqi.py run --headless`
- 可用 `--daily N` 设置本地软限制，避免一天内耗尽

## 六.5、最后一步：导出今日提交 Excel（含审核码）

批量跑完后**最后一步归档**：导出当天已提交记录为 Excel，供对账与存档。命令与列定义见 SKILL.md 工作流第 10 步，这里只保留排查要点：

- 当天无记录时回退导出全部含查询码记录（用于补导出）；完全无则提示「没有找到」
- 对账校验：`records.json` 中 submitted 条数应等于 Excel 数据行数；查询码去重数应等于 results.json 中成功投递数

## 七、截图与诊断

### 7.1 常见截图 bug

| 症状 | 根因 | 解决 |
|---|---|---|
| 文件名变成字面 `%02d` | `screenshot(path="..._%02d.png")` 未格式化 | 用 `"%02d" % i` 或 f-string |
| `clip.width: expected float, got undefined` | 元素 `getBoundingClientRect()` 返回空/undefined | 先判空再传 clip，或滚动到元素可见后再截 |
| OCR 报 `image format error` / 图片损坏 | 抓到的字节不是完整 PNG | 检查 `len(body)>100`，用 `Image.open` 验证 |

### 7.2 验证码截图诊断脚本

```python
# 快速验证抓到的验证码能否识别（尺寸 130×48 或渲染图均可，关键是"与页面显示一致"）
from PIL import Image
import io
im = Image.open(io.BytesIO(img_bytes))
print(im.size)
# 真正的验证标准：el.screenshot() 的图 vs 页面 img 显示一致；
# 再用 lib.ocr_captcha(img_bytes) 识别，最后以"提交拿到查询码"为准
```

**验证码正确性三步验证**（缺一不可）：
1. 抓图方式：必须 `el.screenshot()`（与提交绑定一致），不能用 `page.request` 重新下载（新图≠页面图）
2. 识别：`lib.ocr_captcha()` 能解析算式（如 `7+6=?` → 13）
3. 提交：填答案后服务端返回查询码（唯一硬标准）

## 八、快速排查 Checklist

遇到「提交失败」按顺序排查：

1. [ ] 是否从 `sql_web.html` 进入？（直接访问首页会卡 #isee）
2. [ ] 验证码抓的是 **el.screenshot() 页面当前图**（与提交绑定一致）还是 `page.request` 重新下载的新图？（后者必败，见 1.2）
3. [ ] PaddleOCR token 是否缺失/失效（401）？（检查环境变量 `PADDLEOCR_ACCESS_TOKEN`）
4. [ ] 云盾保护页是否通过？（`#cap-img` 是否还存在）
5. [ ] 服务端是否已限每日配额？（`今日举报次数已达上限`）
6. [ ] `__jsl_clearance_s` cookie 是否过期？（超过 1 小时）
7. [ ] 日志是否 0 字节？（启动加 `-u`）
8. [ ] 是否误杀了 venv spawn 的真 Python 子进程？
