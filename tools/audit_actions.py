# -*- coding: utf-8 -*-
"""自检：动作类描述在「纯 tag 映射」下的失真情况。

这个工具只做「中文词 -> Danbooru tag」的单点映射，不理解句法。
本脚本量化由此产生的三类问题，用于在 README 里如实说明边界。

用法：
    python tools/audit_actions.py
    python tools/audit_actions.py --ext         # 带上扩展词库
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anima_prompt as ap  # noqa: E402

# 典型动作描述：动词 + 宾语 + 修饰，考察工具能保住多少语义
CASES = [
    "她握着剑柄缓缓抽出长剑",
    "女孩打开冰箱拿出牛奶",
    "他一边走路一边看手机",
    "男孩跳起来伸手去够树枝",
    "她轻轻地叹了口气然后转身离开",
    "他把书放到架子上",
    "她推开窗户探出头",
    "男人点起一根烟",
    "她用手指拨了拨头发",
    "他蹲下身系鞋带",
    "女孩把头发扎成马尾",
    "她单手撑着脸颊看书",
    "他把杯子递给我",
    "她戴上耳机开始跑步",
    "男孩把球踢向球门",
    "她伸手接住落下的花瓣",
    "他解开衬衫最上面的扣子",
    "女孩把钥匙插进锁孔",
    "她转身背对着我",
    "他抬头看向天花板",
]

# 纯名词/状态描述：这类应该表现良好，作为对照
CONTRAST = [
    "一个女孩坐在教室窗边",
    "双马尾少女穿着和服",
    "银发红瞳的少女站在雨中",
    "逆光下的长发女孩",
]


def run(text: str, use_ext: bool) -> dict:
    return ap.convert(text, use_ext=use_ext)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ext", action="store_true", help="启用扩展词库")
    args = parser.parse_args()

    ap.load_user_dict()

    def summarize(title: str, cases: list[str]) -> None:
        print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")
        n_hit = n_miss = n_chars_hit = n_chars_all = 0
        for text in cases:
            r = run(text, args.ext)
            tags = ap.all_tags(r)
            miss = r["misses"]
            n_hit += len(tags)
            n_miss += len(miss)
            n_chars_all += len(text)
            # 被「未命中」吞掉的原文字数，粗略代表语义丢失
            n_chars_hit += sum(len(m) for m in miss)
            flag = "  <-- 无任何命中" if not tags else ""
            print(f"\n输入：{text}")
            print(f"  tag  ：{', '.join(tags) if tags else '（空）'}")
            if miss:
                print(f"  丢失 ：{'、'.join(miss)}")
            if flag:
                print(flag)

        print(f"\n{'-' * 66}")
        print(f"用例数 {len(cases)}   产出 tag {n_hit} 个   未消化片段 {n_miss} 个")
        if n_chars_all:
            print(f"被丢弃的原文字符占比：{n_chars_hit / n_chars_all * 100:.0f}%")

    summarize("动作类描述（含动词、宾语、结果）", CASES)
    summarize("名词 / 状态描述（对照组）", CONTRAST)

    print("\n结论提示：")
    print("  - 动作类：动词普遍无 tag 可映射，只有宾语/状态被抽出，动作本身丢失")
    print("  - 名词类：命中率高，这是本工具的设计适用范围")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
