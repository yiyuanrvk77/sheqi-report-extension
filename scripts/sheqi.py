#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheqi-report CLI 入口（通用涉企侵权举报批量提交工具）。
核心逻辑在 sheqi_lib.py；本文件只负责命令行参数解析与命令分发。

快速上手:
  python sheqi.py setup
  python sheqi.py subject add --name <主体名> --company-name <企业全称> \\
      --industry I003 --license 执照.jpg --id-front 正面.png --id-back 反面.png --auth 授权.png
  python sheqi.py import --file <表格.xlsx|csv|json> --subject <主体名>
  python sheqi.py run --dry-run          # 试运行（不提交）
  python sheqi.py run --headless         # 正式批量提交
  python sheqi.py export                 # 导出今日已提交结果（含查询码）Excel
"""
import argparse
import os
import sys
from collections import Counter

# 确保同目录 sheqi_lib 可被导入（sheqi.py 与 sheqi_lib.py 同处 scripts/ 下）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sheqi_lib as S


# ---------------------------------------------------------------- 工具函数
def _gather_fields(args):
    """从 argparse 结果里收集非 None 的文本字段（subject add/set 共用）。"""
    fields = {}
    for key, _opt, _label in SUBJECT_FIELDS:
        v = getattr(args, key, None)
        if v is not None and str(v).strip() != "":
            fields[key] = str(v).strip()
    return fields


def _gather_files(args):
    """从 argparse 结果里收集非空文件路径（subject add/set 共用）。"""
    files = {}
    for key, _opt, _label in SUBJECT_FILES:
        v = getattr(args, key, None)
        if v:
            files[key] = v
    return files


def _print_subject(sub):
    if not sub:
        print("（无）")
        return
    for key, _opt, label in SUBJECT_FIELDS:
        v = sub.get(key)
        if v:
            print("  %-10s: %s" % (label, v))
    files = sub.get("files") or {}
    if files:
        print("  %-10s: %s" % ("材料槽位", "、".join(sorted(files))))
    missing = S.subject_missing_files(sub)
    if missing:
        print("  ⚠ 缺失材料: %s" % "、".join(missing))


# ---------------------------------------------------------------- 子命令实现
def cmd_setup(args):
    py = S.run_setup(python=args.python)
    print("环境就绪，后续命令可用: %s" % py)


def cmd_subject_add(args):
    if not args.name:
        raise SystemExit("缺少 --name（主体名）")
    sub = S.add_subject(args.name, fields=_gather_fields(args), files=_gather_files(args))
    print("已添加/更新主体: %s" % sub.get("name"))
    _print_subject(sub)


def cmd_subject_set(args):
    if not S.get_subject(args.name):
        raise SystemExit("主体不存在: %s（现有: %s）" % (args.name, ", ".join(S.subject_names()) or "无"))
    sub = S.add_subject(args.name, fields=_gather_fields(args), files=_gather_files(args))
    print("已更新主体: %s" % sub.get("name"))
    _print_subject(sub)


def cmd_subject_list(args):
    data = S.load_subjects()
    subs = data.get("subjects", {})
    cur = data.get("current")
    if not subs:
        print("（尚无主体）")
        return
    for name in subs:
        print("%s%s" % ("* " if name == cur else "  ", name))


def cmd_subject_select(args):
    print("已切换当前主体: %s" % S.set_current(args.name))


def cmd_subject_show(args):
    sub = S.get_subject(args.name)
    if not sub:
        raise SystemExit("主体不存在: %s" % (args.name or "（未指定，且当前无主体）"))
    _print_subject(sub)


def cmd_subject_rm(args):
    if not S.remove_subject(args.name):
        raise SystemExit("主体不存在: %s" % args.name)
    print("已删除主体: %s" % args.name)


def cmd_import(args):
    r = S.import_records(args.file, args.subject, limit=args.limit, is_path=True)
    print("导入完成: 新增 %d 条" % r["included"])
    skipped = r.get("skipped") or []
    if skipped:
        print("跳过 %d 条:" % len(skipped))
        for url, reason in skipped[:20]:
            print("  - %s (%s)" % (str(url)[:60], reason))
        if len(skipped) > 20:
            print("  ... 共 %d 条" % len(skipped))


def cmd_records(args):
    records = S.load_records()
    if not records:
        print("（无记录）")
        return
    c = Counter(r.get("status") for r in records)
    print("总数: %d" % len(records))
    for st, n in c.most_common():
        print("  %-12s: %d" % (st or "(空)", n))
    pend = S.pending_records(records)
    if args.detail and pend:
        print("\n待提交 %d 条:" % len(pend))
        for r in pend[:args.detail]:
            print("  %s | %s | %s" % (r.get("id"), r.get("platform"), (r.get("url") or "")[:60]))


def cmd_recover(args):
    S.recover_stuck(subject=args.subject)

def cmd_letter(args):
    subject = S.get_subject(args.subject)
    if not subject:
        raise SystemExit("没有可用主体，请先: python sheqi.py subject add --name <名称>")
    rec = next((r for r in S.load_records() if r.get("id") == args.id), None)
    if not rec:
        raise SystemExit("记录不存在: %s" % args.id)
    path = S.generate_letter(subject, rec, out_dir=args.out)
    print("举报信函已生成: %s" % path)


def cmd_ocr(args):
    for p in args.images:
        txt = S.ocr_image(p)
        print("==== %s" % p)
        print(txt if txt else "（识别失败或无文字）")
        print()


def cmd_export(args):
    path, n = S.export_today_excel(subject=args.subject, date=args.date)
    if not path:
        print("（指定日期内无已提交记录）")
        return
    print("已导出 %d 条: %s" % (n, path))


def cmd_run(args):
    S.run_batch(
        subject_name=args.subject,
        dry_run=args.dry_run,
        headless=args.headless or (not args.headed),
        limit=args.limit,
        from_idx=args.from_idx,
        daily=args.daily,
        interval=args.interval,
        manual=args.manual,
        ocr_enabled=not args.no_ocr,
        record_ids=args.ids,
        base_url=args.base_url,
        cool_every=args.cool_every,
        cool_seconds=args.cool_seconds,
        content_file=args.content,
    )


def cmd_serve(args):
    S.serve_fixtures(port=args.port, dirpath=args.dir)


# ---------------------------------------------------------------- 参数定义
# 主体文本字段: (存储字段名, 说明)
SUBJECT_FIELDS = [
    ("company_name", "企业全称"),
    ("company_type", "企业类型（如 MINYINGQIYE）"),
    ("company_nature", "企业性质（如 QITAQIYE）"),
    ("industry", "行业分类（如 I003=制造业）"),
    ("contact_type", "联系人类型（如 QITARENYUAN）"),
    ("contact_name", "联系人姓名"),
    ("contact_phone", "联系电话"),
    ("contact_email", "联系邮箱"),
    ("content_tail", "自定义侵权定性尾句（可选，优先于内置模板）"),
]
# 主体材料文件: (存储字段名, 说明)
SUBJECT_FILES = [
    ("license", "营业执照"),
    ("id_front", "身份证正面"),
    ("id_back", "身份证反面"),
    ("auth", "授权委托书"),
    ("hand_id", "手持身份证"),
    ("work_proof", "在职证明"),
    ("letter", "举报信函"),
    ("letter_dup", "举报信函(副本)"),
    ("letter2", "举报信函2"),
    ("letter3", "举报信函3"),
]


def _add_subject_args(p):
    p.add_argument("--name", help="主体名（内部标识）")
    for key, label in SUBJECT_FIELDS:
        p.add_argument("--" + key.replace("_", "-"), dest=key, help=label)
    for key, label in SUBJECT_FILES:
        p.add_argument("--" + key.replace("_", "-"), dest=key, help=label + "（文件路径）")


def build_parser():
    ap = argparse.ArgumentParser(
        prog="sheqi.py",
        description="涉企侵权举报批量提交工具（12377.cn）",
    )
    sub = ap.add_subparsers(dest="command")

    p = sub.add_parser("setup", help="创建虚拟环境并安装依赖")
    p.add_argument("--python", help="指定 Python 解释器（默认当前）")
    p.set_defaults(func=cmd_setup)

    sp = sub.add_parser("subject", help="多主体管理")
    ss = sp.add_subparsers(dest="sub_cmd")
    a = ss.add_parser("add", help="新增/更新主体（含材料文件注册）")
    _add_subject_args(a)
    a.set_defaults(func=cmd_subject_add)
    a = ss.add_parser("set", help="更新已有主体字段/材料")
    _add_subject_args(a)
    a.set_defaults(func=cmd_subject_set)
    a = ss.add_parser("list", help="列出全部主体")
    a.set_defaults(func=cmd_subject_list)
    a = ss.add_parser("select", help="切换当前主体")
    a.add_argument("--name", required=True, help="主体名")
    a.set_defaults(func=cmd_subject_select)
    a = ss.add_parser("show", help="查看主体详情")
    a.add_argument("--name", help="主体名（默认当前）")
    a.set_defaults(func=cmd_subject_show)
    a = ss.add_parser("rm", help="删除主体")
    a.add_argument("--name", required=True, help="主体名")
    a.set_defaults(func=cmd_subject_rm)

    p = sub.add_parser("import", help="导入举报记录（xlsx/csv/json，自动识别表头）")
    p.add_argument("--file", required=True, help="表格或 JSON 文件路径")
    p.add_argument("--subject", help="主体名（默认当前）")
    p.add_argument("--limit", type=int, default=0, help="最多导入条数（0=全部）")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("records", help="查看记录状态统计")
    p.add_argument("--detail", type=int, default=0, help="列出前 N 条待提交明细")
    p.set_defaults(func=cmd_records)

    p = sub.add_parser("recover", help="回滚卡死在 submitting 的记录为 pending")
    p.add_argument("--subject", help="仅处理指定主体")
    p.set_defaults(func=cmd_recover)

    p = sub.add_parser("letter", help="生成举报信函（docx）")
    p.add_argument("--id", required=True, help="记录 ID")
    p.add_argument("--subject", help="主体名（默认当前）")
    p.add_argument("--out", help="输出目录（默认 sheqi_data/output）")
    p.set_defaults(func=cmd_letter)

    p = sub.add_parser("run", help="批量填表提交（核心）")
    p.add_argument("--subject", help="主体名（默认当前）")
    p.add_argument("--dry-run", action="store_true", help="试运行：填表+上传但不提交")
    p.add_argument("--headed", action="store_true", help="可见浏览器（默认无头）")
    p.add_argument("--headless", action="store_true", help="无头浏览器（默认即无头，显式声明用）")
    p.add_argument("--limit", type=int, default=0, help="本次最多投递次数（0=全部）")
    p.add_argument("--from", dest="from_idx", type=int, default=0, help="从队列第 N 个开始")
    p.add_argument("--daily", type=int, default=0, help="本地每日上限（0=不限，以服务端为准）")
    p.add_argument("--interval", type=int, default=0, help="每次投递间隔秒数（默认 15）")
    p.add_argument("--manual", action="store_true", help="验证码人工输入（默认 PaddleOCR 自动识别）")
    p.add_argument("--no-ocr", action="store_true", help="关闭 OCR（强制刷新/人工）")
    p.add_argument("--id", dest="ids", action="append", help="指定记录 ID（可多次）")
    p.add_argument("--base-url", default=S.DEFAULT_REPORT_URL, help="表单页 URL（离线自测用 http://127.0.0.1:8765/form_test.html）")
    p.add_argument("--cool-every", type=int, default=10, help="每投 N 组主动冷却一次（0=关闭，默认 10）")
    p.add_argument("--cool-seconds", type=int, default=300, help="主动冷却秒数（默认 300=5 分钟）")
    p.add_argument("--content", help="自定义举报内容模板文件（≤500字）")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("ocr", help="识别图片/材料文字（投诉函、营业执照、身份证等，PaddleOCR 在线）")
    p.add_argument("images", nargs="+", help="图片文件路径（可多个）")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("export", help="导出指定日期已提交记录 Excel（含查询码）")
    p.add_argument("--subject", help="主体名（默认全部）")
    p.add_argument("--date", help="日期 YYYY-MM-DD（默认今天）")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("serve", help="启动内置离线模拟表单（自测用）")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--dir", help="fixtures 目录（默认脚本同目录 fixtures）")
    p.set_defaults(func=cmd_serve)

    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
