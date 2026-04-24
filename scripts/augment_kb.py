# -*- coding: utf-8 -*-
"""
知识库文档骨架补齐脚本
功能：
  - 针对 05_special / 06_case / 00_meta / relationship_knowledge / _templates 五类文档
    按规定骨架补齐缺失章节；保留 YAML frontmatter 与原有正文，不新增/删除文件。
  - 幂等执行：若章节已存在（按一级/二级标题匹配）则跳过。
"""
import re
from pathlib import Path

# 知识库根路径
KB = Path(r"C:/Users/33185/Desktop/ai-love/docs/knowledge_base")

# 五类骨架（二级标题 + 默认中文占位内容）
SKELETON_SPECIAL = [
    ("概念与定义", "本专题聚焦该关系形态的核心内涵、典型边界与常见误识，帮助读者在进入策略层前先建立共识。\n\n- 核心定义：梳理本专题所指向的关系类型边界。\n- 适用人群：明确该专题可迁移到的恋爱阶段与人群画像。\n- 非目标：与之易混淆但不属于本专题讨论的范围。"),
    ("核心挑战与机遇", "- 主要挑战：距离、身份、认知落差、舆论压力等典型风险点。\n- 特有机遇：深度对话、边界锻炼、自我觉察、关系韧性提升。\n- 机会成本：若处理不当，可能付出的时间、情感与现实代价。"),
    ("关键知识要点", "| 维度 | 要点 | 关联理论 |\n|------|------|----------|\n| 心理 | 依恋类型识别与调节 | 依恋理论 |\n| 沟通 | 高密度、低误解的表达原则 | 非暴力沟通 |\n| 边界 | 自我边界与对方边界的区分 | 人际边界理论 |\n| 决策 | 理性评估与情绪隔离 | 认知行为 |"),
    ("话术模板", "> 表达需求：\"我希望我们可以……，你方便吗？\"\n> 化解冲突：\"我理解你的感受，我们一起想办法。\"\n> 明确承诺：\"我愿意为我们的关系做到……\"\n> 设定边界：\"这件事让我不舒服，我需要……\"\n\n注：话术以原句意图为锚，不可机械套用，需根据关系阶段与对方状态微调。"),
    ("常见误区", "- ❌ 以牺牲自我为代价换取关系稳定\n- ❌ 用控制代替信任、用审问代替沟通\n- ❌ 将焦虑情绪投射为对方的过错\n- ❌ 忽略现实条件，只谈感情不谈规划"),
    ("红线提示", "- 🚫 禁止 PUA、贬低、冷暴力式操控\n- 🚫 禁止以爱之名的跟踪、监控、骚扰\n- 🚫 涉及家暴、诈骗、违法行为，立即引导报警或专业机构\n- 🚫 出现自伤/极端情绪信号，优先安全兜底"),
    ("延伸阅读", "- [[relationship_knowledge/06_冲突处理与关系修复]]\n- [[relationship_knowledge/09_情绪安抚与支持表达]]\n- [[relationship_knowledge/11_安全红线与禁忌话术]]\n- [[06_case/成功案例/01_异地恋修成正果]]"),
]

SKELETON_CASE = [
    ("案例背景", "补充本案例发生的社会背景、关系阶段与触发事件。"),
    ("当事人", "- 男方：年龄 / 职业 / 性格 / 依恋类型\n- 女方：年龄 / 职业 / 性格 / 依恋类型\n- 关键他人：父母、朋友、竞争者等对关系的影响。"),
    ("关键时间线", "| 时间 | 事件 | 关系影响 |\n|------|------|----------|\n| T0 | 相识 | 建立初步好感 |\n| T1 | 关键节点 | 出现决定性转折 |\n| T2 | 结果 | 关系走向定型 |"),
    ("冲突与决策", "- 核心冲突：价值观 / 距离 / 家庭 / 信任。\n- 决策节点：在哪些节点上做出了关键选择，为什么。\n- 替代方案：若当时选择不同，可能的走向。"),
    ("结果", "描述关系最终走向（结婚 / 分手 / 稳定 / 恶化），并给出量化指标（时长、满意度自评等）。"),
    ("可迁移原则", "- 原则一：把信任建立在可验证的行为上。\n- 原则二：承诺要与现实规划同步。\n- 原则三：冲突必须以修复为目标，而非胜负。"),
    ("理论分析", "关联 `01_foundation` 中的：\n- 依恋理论：解释双方在压力下的行为模式。\n- 社会交换理论：解释投入—回报失衡导致的关系走向。\n- 沟通理论：解释高/低语境表达带来的误解。"),
    ("延伸阅读", "- [[05_special/01_异地关系]]\n- [[relationship_knowledge/06_冲突处理与关系修复]]\n- [[relationship_knowledge/10_分手_复联_降温策略]]"),
]

SKELETON_META = [
    ("索引表", "| 字段 | 含义 | 示例 |\n|------|------|------|\n| title | 文档标题 | 异地关系 |\n| category | 所属分类 | 05_special |\n| tags | 标签数组 | [异地恋, 信任] |\n| difficulty | 难度等级 | beginner/intermediate/advanced |"),
    ("字段定义", "- `title`：文档主标题，唯一，不含路径。\n- `description`：一句话摘要，≤100字。\n- `tags`：用于检索与过滤的标签数组，遵循 `01_标签体系.md`。\n- `related_docs`：显式声明的强关联文档路径。\n- `confidence_level`：high/medium/low，标记内容的可信度。"),
    ("使用示例", "```yaml\n---\ntitle: 异地关系\ncategory: 05_special\ntags: [异地恋, 信任建立]\ndifficulty: advanced\nconfidence_level: high\n---\n```\n\n- 新增文档：复制 `_templates/` 下对应模板。\n- 修订文档：保留原 frontmatter，按本规范补齐缺失字段。"),
]

SKELETON_REL = [
    ("场景分类", "- 按关系阶段：陌生 / 破冰 / 暧昧 / 确定 / 稳定 / 降温 / 分手。\n- 按情绪状态：平稳 / 焦虑 / 愤怒 / 低落 / 危机。\n- 按沟通介质：文字 / 语音 / 视频 / 线下。"),
    ("触发信号", "- 行为信号：回复节奏变化、主动性下降、话题深度变化。\n- 语言信号：出现\"随便\"\"都行\"\"没事\"等低能量词。\n- 情绪信号：突然冷淡、突然粘人、情绪波动剧烈。"),
    ("话术模板矩阵", "| 原句（常见表达） | 优化句（建议话术） | 优化点 |\n|------------------|---------------------|--------|\n| \"你怎么还不回我\" | \"刚刚看到你没回，是不是在忙？\" | 把指责换成关心 |\n| \"随便你\" | \"我现在有点情绪，等我缓一下再聊好吗\" | 把冷暴力换成边界表达 |\n| \"你根本不在乎我\" | \"我最近有点没安全感，我需要你多回应一点\" | 把评判换成需求 |\n| \"算了不说了\" | \"这件事我还没想清楚，我们晚点再聊\" | 把关闭换成延后 |"),
    ("使用注意", "- 话术需匹配关系阶段与双方熟悉度，避免越位。\n- 不要把模板句作为\"标准答案\"机械使用。\n- 情绪高峰期优先降温，不要在愤怒中输出关键决策。"),
    ("红线", "- 禁止贬低、羞辱、人格攻击类表达。\n- 禁止以分手/冷战作为操控手段。\n- 涉及安全风险，跳转 `11_安全红线与禁忌话术.md`。"),
    ("延伸阅读", "- [[relationship_knowledge/11_安全红线与禁忌话术]]\n- [[relationship_knowledge/12_高频表达改写示例库]]\n- [[05_special/01_异地关系]]"),
]

SKELETON_TEMPLATE_NOTES = [
    ("占位符说明", "本模板中的占位符采用双大括号语法，复制模板后请统一替换：\n\n- `{{title}}`：文档标题\n- `{{description}}`：一句话摘要（≤100字）\n- `{{category}}`：所属分类路径\n- `{{tags}}`：标签数组，遵循 `00_meta/01_标签体系.md`\n- `{{author}}`：作者或团队\n- `{{created_at}}` / `{{updated_at}}`：日期，格式 `YYYY-MM-DD`\n- `{{body}}`：正文主体，按下方结构逐节填写"),
    ("使用说明", "<!--\n1. 复制本模板到目标目录，重命名为实际文件名（中文可用）。\n2. 保留并填写 YAML frontmatter，缺失字段需补齐。\n3. 正文遵循既定骨架，小节顺序不可随意调换。\n4. 完成后运行知识库校验脚本，确认标签/链接有效。\n-->"),
]


def has_heading(text: str, title: str) -> bool:
    """判断文档是否已存在指定二级标题。"""
    pattern = re.compile(r"^#{1,6}\s+" + re.escape(title), re.MULTILINE)
    return bool(pattern.search(text))


def append_sections(path: Path, skeleton):
    """向文件追加缺失的二级标题小节。"""
    text = path.read_text(encoding="utf-8")
    additions = []
    for title, body in skeleton:
        if not has_heading(text, title):
            additions.append(f"\n## {title}\n\n{body}\n")
    if not additions:
        return False
    # 追加到文件末尾，前置一条分隔线与补齐说明（仅首次追加）
    prefix = ""
    if "<!-- 知识库骨架补齐 -->" not in text:
        prefix = "\n\n---\n\n<!-- 知识库骨架补齐 -->\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(prefix + "".join(additions))
    return True


def process_dir(dir_path: Path, skeleton, recursive=False):
    """批量处理目录下 .md 文件（排除 README.md）。"""
    it = dir_path.rglob("*.md") if recursive else dir_path.glob("*.md")
    changed = []
    for p in it:
        if p.name.lower() == "readme.md":
            continue
        if append_sections(p, skeleton):
            changed.append(str(p))
    return changed


def main():
    changed = []
    # 05_special 根目录（非递归，排除子目录下 README）
    changed += process_dir(KB / "05_special", SKELETON_SPECIAL, recursive=False)
    # 06_case
    changed += process_dir(KB / "06_case" / "成功案例", SKELETON_CASE)
    changed += process_dir(KB / "06_case" / "失败案例", SKELETON_CASE)
    # 00_meta
    changed += process_dir(KB / "00_meta", SKELETON_META)
    # relationship_knowledge
    changed += process_dir(KB / "relationship_knowledge", SKELETON_REL)
    # _templates
    changed += process_dir(KB / "_templates", SKELETON_TEMPLATE_NOTES)
    print(f"共更新 {len(changed)} 个文件")
    for c in changed:
        print(" -", c)


if __name__ == "__main__":
    main()
