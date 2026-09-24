#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial regression tests for the transactional daily briefing pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_briefing_config import audit, audit_ranking_delivery
from briefing_contract import concept_identity, normalize_briefing_config
from briefing_to_feedback_html import render_html
from config_to_news_feedback import export_feedback
from daily_pipeline import cmd_finalize, cmd_run, verify_artifacts
from lean_html import apply_design_system, design_audit_issues
from news_delta import render_markdown, transform_config, upsert_index
from rank_briefing_candidates import DEFAULT_RANKING_POLICY, rank_briefing_config


def item(item_id: str = "N001", *, concept: str = "QSVT", url: str = "https://example.org/story") -> dict:
    return {
        "id": item_id,
        "story_id": item_id.lower(),
        "title": "Research item",
        "category": "AI product",
        "facts": "A source-grounded fact.",
        "judgment": "A separated judgment.",
        "source_title": "Official source",
        "source_url": url,
        "source_excerpt": "Evidence excerpt.",
        "evidence_level": "official source",
        "concepts": [concept],
    }


def opening_story() -> dict:
    return {
        "version": 3,
        "title": "两座钟塔",
        "paragraphs": [
            "山谷里有两座钟塔。守钟人必须在巡夜结束前判断两路钟声是否已经错开 1 rad；若判断过早，两个仍然混在一起的节拍会让值夜人打开错误的山门。",
            "校准册写着，两座塔对应的能量刻度相差 0.2 meV，而把这个刻度差换成等待时间时要使用 0.658 meV·ps 的换算尺。铜轮只能按册中的规则做除法并显示结果。",
            "守钟人把 0.658 除以 0.2。铜轮先核对 0.2 乘以 3 等于 0.6，还剩 0.058；再核对 0.2 乘以 0.29 正好等于 0.058，因此把两段等待相加成 3.29 ps。到这一刻，两路钟声的相对错位才达到约定的 1 rad，山门上的判别灯第一次分开亮起。",
            "为了核对原因，他把能量刻度差改为 0.4 meV，再做同一操作：0.658 除以 0.4，得到约 1.65 ps。若其余条件不变，刻度差加倍后，达到同一判别线所需的等待时间约减半。",
            "两次记录放在一起后，守钟人才把可观察差异说清：0.2 meV 时要等约 3.29 ps，0.4 meV 时只需约 1.65 ps。决定等待尺度的是两种节拍之间的间距，而不是故事里某一座塔单独转得有多快。",
        ],
        "concept_name": "spectral gap",
        "concept_aliases": ["谱隙"],
        "concept_definition": "谱隙是指定算符相邻关键特征值之间的差，它控制某些动力学或算法区分、混合与收敛所需的尺度。",
        "logic_chain": "特征值间隔缩小 → 模态更难区分 → 相位或概率差积累更慢 → 所需演化时间增长。",
        "analogy_boundary": "钟塔把模态画成了独立声源，但现实中的特征向量、简并和耦合结构可能共同影响动力学。",
        "misleading_risk": "不能据此认为谱隙越大一切算法都越快；结论依赖具体算符、初态、观测量和复杂度模型。",
        "worked_example": mathematical_worked_example(),
        "grounding_kind": "learner_profile",
        "source_story_ids": [],
    }


def mathematical_worked_example() -> dict:
    return {
        "kind": "mathematical",
        "title": "两能级系统中的相位分辨",
        "question": "为什么较小的能级差需要更长时间才能积累可分辨的相对相位？",
        "scenario": "制备一个两能级系统，取能级差 Δ=0.2 meV，并把可分辨阈值固定为相对相位达到 1 rad。",
        "inputs": [
            {"name": "能级差 Δ", "value": "0.2 meV", "role": "决定两个分量积累相对相位的速率"},
            {"name": "约化普朗克常数 ℏ", "value": "0.658 meV·ps", "role": "把能量差换算成时间尺度"},
            {"name": "分辨阈值", "value": "1 rad", "role": "给出本例要达到的可观察判据"},
        ],
        "observable": "记录相对相位首次达到 1 rad 所需的演化时间，并与 Δ 加倍后的时间比较。",
        "assumptions": ["哈密顿量不随时间变化，初态在两个正交本征态上具有非零振幅。"],
        "objects": [
            {"name": "H", "kind": "厄米算符", "role": "生成系统的时间演化", "units": "energy"},
            {"name": "Δ", "kind": "实数标量", "role": "两个相关本征值之差", "units": "energy"},
            {"name": "t", "kind": "实数标量", "role": "系统演化时间", "units": "time"},
        ],
        "steps": [
            {
                "action": "让两个本征态分量在同一哈密顿量下演化。",
                "formula": "|\\psi(t)\\rangle=e^{-iHt/\\hbar}|\\psi(0)\\rangle",
                "rule": "时间无关薛定谔演化",
                "explanation": "每个本征态保持方向，并按自己的本征值积累相位。",
            },
            {
                "action": "消去共同的全局相位，只保留两分量之间的相对相位。",
                "formula": "\\phi(t)=\\Delta t/\\hbar",
                "rule": "全局相位不改变测量概率",
                "explanation": "两个相位指数相除后，公共能量项抵消，只剩本征值差。",
            },
            {
                "action": "要求相对相位达到一个数量级为一的分辨阈值。",
                "formula": "t_{\\mathrm{resolve}}=\\hbar/\\Delta=0.658/0.2\\;\\mathrm{ps}=3.29\\;\\mathrm{ps}",
                "rule": "由 |\\phi|\\sim1 解出演化时间尺度",
                "explanation": "相位积累速率为 Δ/ℏ，因此较小的 Δ 需要更长时间。",
            },
        ],
        "result": "本例达到 1 rad 相对相位需要约 3.29 ps；若 Δ 加倍为 0.4 meV，时间缩短为约 1.65 ps。",
        "interpretation": "谱隙缩小时两个模态的相位速率更接近，需要更长观察时间才能区分。",
        "checks": ["ℏ/Δ 的量纲是时间；Δ 加倍时达到相同相位所需时间减半。"],
        "non_conclusion": "不能由此断言所有含谱隙的算法运行时间都严格等于 ℏ/Δ。",
    }


def carleman_truncation_story() -> dict:
    return {
        "version": 3,
        "title": "被拿走的第三张输入卡",
        "paragraphs": [
            "预测台必须在下一次采样前交付一个局部变化率，验收员只接受能从输入卡逐步复算的结果；少算的输入会在参考结果中直接显示为差值。",
            "桌上的计算器只会把卡片上的数乘以固定倍率再相加。完整计算需要三张输入卡，但便携盒只能保留前两张；盒子的明确规则是第三张卡缺席时把它的输入当作 0。",
            "这次第一张卡的状态值是 1/2，由同一状态得到的第二张卡是 1/4，第三张卡是 1/8。操作员把三个数逐项报出，因此没有用“后面的影响”代替实际输入。",
            "计算第二张卡对应的完整变化率时，操作员把 1/4 乘以 2，得到 1/2；再把 1/8 乘以 2，得到 1/4；最后把 1/2 与 1/4 相加，结果是 3/4。",
            "改用便携盒时，操作员拿走第三张输入卡，并按规则把缺失输入设为 0，所以只保留 2 乘以 1/4，得到 1/2。用完整结果 3/4 减去便携结果 1/2，可观察到遗漏量正好是 1/4。",
            "验收员现在可以直接复核：原来参与结果的是 1/4 与 1/8，拿走的是第三张卡，替代规则是设为 0，完整结果与简化结果之差是 1/4。",
        ],
        "concept_name": "Carleman linearization truncation",
        "concept_aliases": ["Carleman 截断", "卡莱曼线性化截断"],
        "concept_definition": "把无限升维线性系统限制到有限阶时，闭合规则会舍去高阶坐标对保留坐标的耦合，并由此引入可计算的截断误差。",
        "logic_chain": "无限升维中的精确耦合 → 在第二页后采用零闭合 → 第三页贡献被设为零 → 第二页变化率少算 1/4。",
        "analogy_boundary": "账页是同一标量状态的单项式坐标，不是新的独立河流；一次局部变化率差也不等同于完整时间区间的全局解误差。",
        "misleading_risk": "不能把封掉的页理解为真实动力学中高阶项已经消失，也不能由多保留一页就断言误差必然按固定比例下降。",
        "worked_example": carleman_truncation_worked_example(),
        "grounding_kind": "learner_profile",
        "source_story_ids": [],
    }


def carleman_truncation_worked_example() -> dict:
    return {
        "kind": "mathematical",
        "title": "二阶零闭合遗漏的三阶贡献",
        "question": "在 x=1/2 时，把升维系统截到第二页会在 z₂ 的变化率中遗漏多少？",
        "scenario": "对标量模型 x'=x+x²，只检查 x=1/2 这一时刻，并比较完整三页局部关系与二阶零闭合。",
        "inputs": [
            {"name": "x", "value": "1/2", "role": "给出本例的当前标量状态"},
            {"name": "z₂=x²", "value": "1/4", "role": "给出保留到二阶时的第二个升维坐标"},
            {"name": "z₃=x³", "value": "1/8", "role": "给出被二阶零闭合舍去的三阶坐标"},
        ],
        "observable": "比较完整 z₂ 变化率、二阶零闭合变化率及二者差值。",
        "assumptions": ["只比较当前时刻的局部变化率；二阶有限模型采用 z₃=0 的零闭合。"],
        "objects": [
            {"name": "x", "kind": "实数状态", "role": "原非线性系统的状态", "units": "dimensionless"},
            {"name": "z₂", "kind": "单项式坐标", "role": "记录 x²", "units": "dimensionless"},
            {"name": "z₃", "kind": "单项式坐标", "role": "记录 x³", "units": "dimensionless"},
        ],
        "steps": [
            {
                "action": "由同一个 x=1/2 计算第二、第三个单项式坐标。",
                "formula": "z_2=x^2=1/4,\\quad z_3=x^3=1/8",
                "rule": "升维坐标定义",
                "explanation": "这些坐标由同一物理状态确定，不是新的独立自由度。",
            },
            {
                "action": "保留第三阶耦合，计算第二坐标的完整局部变化率。",
                "formula": "z_2'=2z_2+2z_3=2(1/4)+2(1/8)=3/4",
                "rule": "对 z₂=x² 使用链式法则并代入 x'=x+x²",
                "explanation": "第二页自身给出 1/2，第三页再给出 1/4。",
            },
            {
                "action": "采用二阶零闭合，把 z₃ 的贡献设为零。",
                "formula": "\\widehat z_2'=2z_2=2(1/4)=1/2",
                "rule": "K=2 零闭合",
                "explanation": "有限系统不再接收第三坐标的 1/4 贡献。",
            },
            {
                "action": "用完整局部变化率减去截断后的局部变化率。",
                "formula": "3/4-1/2=1/4",
                "rule": "同一时刻、同一坐标的差值比较",
                "explanation": "本例可直接复算的遗漏量是 1/4。",
            },
        ],
        "result": "完整局部变化率为 3/4，二阶零闭合给出 1/2，因此当前时刻遗漏 1/4。",
        "interpretation": "有限截断不是与无限升维系统精确等价；误差从被闭合掉的高阶耦合进入。",
        "checks": ["2(1/4)+2(1/8)=3/4；3/4-1/2=1/4。"],
        "non_conclusion": "这个局部差值不证明任意时间、任意初值或任意闭合下的全局误差都等于 1/4。",
    }


def operational_worked_example() -> dict:
    return {
        "kind": "operational",
        "title": "双人审批队列",
        "question": "为什么增加独立复核会改变错误进入发布阶段的路径？",
        "scenario": "候选记录 Claim-17 声称模型准确率为 92%，但原始报告只写了 82%；系统必须决定它能否进入今日发布队列。",
        "inputs": [
            {"name": "候选记录 Claim-17", "value": "准确率 92%", "role": "提供待验证且可能错误的声明"},
            {"name": "原始报告", "value": "准确率 82%", "role": "作为独立复核时的事实基准"},
        ],
        "observable": "观察 Claim-17 最终停留在哪个队列，以及系统记录的退回原因。",
        "assumptions": ["提交者与复核者独立工作，只有通过复核的记录才能发布。"],
        "objects": [
            {"name": "候选记录", "kind": "待验证对象", "role": "携带尚未确认的声明", "units": ""},
            {"name": "复核者", "kind": "独立检查角色", "role": "检查来源与声明是否一致", "units": ""},
        ],
        "steps": [
            {
                "action": "提交者写入候选记录，但记录仍停留在候选队列。",
                "formula": "",
                "rule": "候选状态不能直接发布",
                "explanation": "首次提交只建立待检对象，并不提供独立确认。",
            },
            {
                "action": "复核者对照来源；不一致的记录被退回，一致的记录进入发布队列。",
                "formula": "",
                "rule": "独立复核门槛",
                "explanation": "第二条独立检查路径改变了错误记录能够到达的状态。",
            },
        ],
        "result": "复核者发现 92% 与原始报告的 82% 不一致，Claim-17 被退回候选队列，未进入发布队列。",
        "interpretation": "关键机制是状态门槛和独立检查，而不是增加形式化步骤本身。",
        "checks": ["移除复核门槛后，同一错误可以从候选队列直接进入发布队列。"],
        "non_conclusion": "双人复核不能保证零错误，也不能替代高质量来源。",
    }


def config(items: list[dict] | None = None) -> dict:
    return {
        "briefing_title": "Test briefing",
        "date_range": "2026-07-10",
        "story_delivery": {
            "required": True,
            "worked_example_required": True,
            "position": "before_briefing",
        },
        "opening_story": opening_story(),
        "sections": [{"title": "Today", "items": items or [item()]}],
        "academic_delivery": {"required": False, "no_signal_reason": "non-academic unit-test fixture"},
        "analysis_language": "en",
    }


def with_fields(value: dict, **fields: object) -> dict:
    result = dict(value)
    result.update(fields)
    return result


def ranked_candidate(
    item_id: str,
    *,
    url: str,
    source_class: str,
    organization: str,
    topic: str,
    published_at: str = "2026-07-10",
) -> dict:
    return {
        "id": item_id,
        "story_id": item_id.lower(),
        "title": f"Ranked candidate {item_id}",
        "category": topic,
        "facts": "Verified release with 42 measured results and a concrete deployment.",
        "judgment": "The evidence is specific enough to compare with prior work.",
        "relevance": "Relevant to quantum dynamics, error correction, or agent infrastructure.",
        "source_title": f"Source {item_id}",
        "source_url": url,
        "source_excerpt": "Primary evidence excerpt with quantitative details.",
        "evidence_level": "peer-reviewed venue" if "arxiv.org" not in url else "arXiv preprint",
        "evidence_fingerprint": f"fingerprint-{item_id.lower()}",
        "published_at": published_at,
        "venue_sweep_note": "Official academic venues were checked; this item remains labeled as an arXiv preprint." if "arxiv.org" in url else "",
        "source_class": source_class,
        "organization": organization,
        "topic": topic,
        "corroborating_source_count": 2,
        "concepts": [topic, item_id],
    }


def ranking_fixture() -> tuple[dict, list[dict]]:
    academic: list[dict] = []
    for index in range(1, 11):
        if index <= 3:
            url = f"https://www.nature.com/articles/ranking-{index}"
            source_class = "formal_academic"
        else:
            url = f"https://arxiv.org/abs/2607.{14000 + index}"
            source_class = "arxiv_preprint"
        candidate = ranked_candidate(
            f"A{index:03d}",
            url=url,
            source_class=source_class,
            organization="",
            topic=f"academic-topic-{index % 5}",
        )
        candidate["ranking_signals"] = {
            "technical_contribution": 1.0 if index == 1 else 0.45,
            "specificity": 1.0 if index == 1 else 0.55,
            "relevance": 1.0 if index == 1 else 0.60,
            "reproducibility": 1.0 if index == 1 else 0.40,
        }
        academic.append(candidate)
    social_classes = ["reputable_media"] * 4 + ["official_primary"] * 4 + ["official_company_social"] * 6
    social = [
        ranked_candidate(
            f"S{index:03d}",
            url=f"https://social-{index}.example.org/story",
            source_class=source_class,
            organization=f"organization-{index}",
            topic=f"social-topic-{index % 6}",
        )
        for index, source_class in enumerate(social_classes, start=1)
    ]
    raw = {
        "briefing_title": "Ranked daily briefing",
        "date_range": "2026-07-10",
        "story_delivery": {
            "required": True,
            "worked_example_required": True,
            "position": "before_briefing",
        },
        "opening_story": {
            **opening_story(),
            "grounding_kind": "briefing_items",
            "source_story_ids": ["a001"],
        },
        "sections": [
            {"title": "Academic research", "items": academic},
            {"title": "Social news", "items": social},
        ],
        "academic_delivery": {
            "required": True,
            "minimum_items": 7,
            "target_items": 8,
            "maximum_items": 8,
            "minimum_new_items": 4,
            "maximum_new_items": 6,
            "minimum_non_arxiv_items": 2,
            "maximum_continuing_items": 3,
        },
        "social_delivery": {
            "minimum_items": 10,
            "target_items": 12,
            "maximum_items": 14,
            "minimum_new_or_material_update": 7,
            "maximum_continuing_items": 3,
            "minimum_reputable_media_items": 3,
            "minimum_primary_official_items": 3,
            "minimum_source_classes": 3,
            "maximum_items_per_organization": 2,
            "maximum_items_per_topic": 3,
        },
        "ranking_policy": DEFAULT_RANKING_POLICY,
        "analysis_language": "en",
    }
    venues = ["aps-prl", "aps-pra", "aps-prx", "nature", "science", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"]
    raw["academic_search"] = {
        "required_venues": venues,
        "topics": [{"term": "quantum ranking test", "checked_venues": venues, "primary_hits": [{"venue": "nature", "url": academic[0]["source_url"]}], "status": "evidenced"}],
        "rows": [
            {
                "term": "quantum ranking test",
                "venue": venue,
                "result": "checked",
                "url": academic[0]["source_url"] if venue == "nature" else "",
                "evidence": {
                    "query_url": f"https://{venue}.example.org/search",
                    "retrieved_at": "2026-07-10T00:00:00Z",
                    "status_code": 200,
                    "final_url": f"https://{venue}.example.org/search",
                    "response_hash": (venue.replace("-", "") + "0" * 64)[:64],
                },
            }
            for venue in venues
        ],
    }
    raw["social_candidate_pool"] = {
        "required_source_classes": ["ai_hot", "reputable_media", "official_company_social", "executive_social"],
        "checked_at": "2026-07-10T00:00:00Z",
        "ai_hot_artifact": "aihot_candidates_2026-07-10.json",
    }
    prior = [
        {
            "story_id": academic[index]["story_id"],
            "last_seen": "2026-07-09",
            "source_url": academic[index]["source_url"],
            "summary": academic[index]["facts"],
            "evidence_fingerprint": academic[index]["evidence_fingerprint"],
        }
        for index in (8, 9)
    ]
    return raw, prior


class DailyPipelineTests(unittest.TestCase):
    def test_daily_pipeline_requires_an_opening_story_before_creating_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = config()
            raw.pop("opening_story")
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(root / "story_index.jsonl"), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            with self.assertRaisesRegex(ValueError, "requires opening_story"):
                cmd_run(args)
            self.assertFalse((root / "news" / "2026-07-10" / ".staging").exists())

    def test_story_cannot_reveal_concept_before_the_debrief(self) -> None:
        raw = config()
        raw["opening_story"]["paragraphs"][0] += " This is the spectral gap."
        with self.assertRaisesRegex(ValueError, "reveals the concept"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_story_concept_leak_after_character_900_is_still_rejected(self) -> None:
        raw = config()
        original = raw["opening_story"]["paragraphs"]
        raw["opening_story"]["paragraphs"] = [
            "甲" * 950 + " spectral gap",
            " ".join(original),
        ]
        with self.assertRaisesRegex(ValueError, "reveals the concept"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_story_paragraph_count_has_no_upper_bound(self) -> None:
        raw = config()
        original = raw["opening_story"]["paragraphs"]
        raw["opening_story"]["paragraphs"] = [
            " ".join(original[:3]),
            " ".join(original[3:]),
        ]
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(len(canonical["opening_story"]["paragraphs"]), 2)

        raw = config()
        raw["opening_story"]["paragraphs"].extend(
            [
                "第六段只补充可观察的交付条件，不改变前述运算或引入第二个机制。",
                "第七段记录复核者能够沿着同一组输入重新得到两个等待时间。",
            ]
        )
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(len(canonical["opening_story"]["paragraphs"]), 7)

    def test_story_paragraph_normalization_does_not_drop_duplicates(self) -> None:
        raw = config()
        repeated = raw["opening_story"]["paragraphs"][-1]
        raw["opening_story"]["paragraphs"].extend([repeated, repeated])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(len(canonical["opening_story"]["paragraphs"]), 7)
        self.assertEqual(canonical["opening_story"]["paragraphs"].count(repeated), 3)

    def test_story_rejects_fewer_than_two_paragraphs(self) -> None:
        raw = config()
        raw["opening_story"]["paragraphs"] = [
            " ".join(raw["opening_story"]["paragraphs"])
        ]
        with self.assertRaisesRegex(ValueError, "at least 2 story paragraphs"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_story_paragraph_limit_is_fail_closed_without_truncation(self) -> None:
        raw = config()
        original = raw["opening_story"]["paragraphs"]
        raw["opening_story"]["paragraphs"] = ["甲" * 2000, " ".join(original)]
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(len(canonical["opening_story"]["paragraphs"][0]), 2000)

        raw = config()
        overlong = "甲" * 2001
        raw["opening_story"]["paragraphs"] = [overlong, " ".join(raw["opening_story"]["paragraphs"])]
        with self.assertRaisesRegex(ValueError, "exceeds 2000 characters.*split"):
            normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(raw["opening_story"]["paragraphs"][0], overlong)

    def test_carleman_story_runs_the_reproducible_truncation_case(self) -> None:
        raw = config()
        raw["opening_story"] = carleman_truncation_story()
        canonical = normalize_briefing_config(raw, require_source_url=True)
        story_text = " ".join(canonical["opening_story"]["paragraphs"])
        for fragment in (
            "1/2",
            "1/4",
            "1/8",
            "1/4 乘以 2",
            "3/4",
            "缺失输入设为 0",
            "3/4 减去便携结果 1/2",
            "遗漏量正好是 1/4",
        ):
            self.assertIn(fragment, story_text)

    def test_vague_carleman_story_without_values_fails(self) -> None:
        raw = config()
        raw["opening_story"] = carleman_truncation_story()
        raw["opening_story"]["paragraphs"] = [
            "预测台必须在下一次采样前交付一个可复核的局部变化率，少算输入会让结果偏离参考值。",
            "桌上计算器只会把输入乘以固定倍率再相加，便携盒只能保留前两个输入，缺失输入按 0 处理。",
            "操作员说当前状态已经写在三张卡上，但没有报出每张卡的实际数值。",
            "他把完整计算描述成多算一个输入，把简化计算描述成少算一个输入，却没有展示乘法、中间结果或差值。",
            "验收员因此无法从故事独立复算完整结果、简化结果与遗漏量。",
        ]
        with self.assertRaisesRegex(ValueError, "must reuse the worked-example input values"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_daily_pipeline_requires_a_worked_example_before_creating_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = config()
            raw["opening_story"].pop("worked_example")
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(root / "story_index.jsonl"), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            with self.assertRaisesRegex(ValueError, "requires worked_example"):
                cmd_run(args)
            self.assertFalse((root / "news" / "2026-07-10" / ".staging").exists())

    def test_nonmathematical_worked_example_requires_no_formula(self) -> None:
        raw = config()
        raw["opening_story"]["worked_example"] = operational_worked_example()
        raw["opening_story"]["paragraphs"] = [
            "发布站今晚只剩一个名额，记录 Claim-17 声称准确率为 92%。值班员必须在关站前决定它进入发布队列还是退回复核队列，错误发布会直接出现在明早的公开页面。",
            "复核员打开原始报告，看到同一项结果写的是准确率 82%。规则要求来源数字与候选记录一致才能放行，因此他把候选的 92% 与原文的 82% 逐项比较，并把不一致标成可观察的失败状态。",
            "Claim-17 最终没有进入发布队列，而是停在复核队列并记录“候选值 92% 与来源值 82% 不一致”。整个过程只使用对象、状态、比较和队列迁移，没有为装饰而加入公式。",
        ]
        canonical = normalize_briefing_config(raw, require_source_url=True)
        example = canonical["opening_story"]["worked_example"]
        self.assertEqual(example["kind"], "operational")
        self.assertFalse(any(step["formula"] for step in example["steps"]))
        html = render_html(canonical)
        self.assertIn("展开完整例子", html)
        self.assertNotIn('id="MathJax-script"', html)

    def test_legacy_story_without_example_remains_readable_outside_new_daily_contract(self) -> None:
        raw = config()
        raw["story_delivery"].pop("worked_example_required")
        raw["opening_story"].pop("worked_example")
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(canonical["opening_story"]["version"], 1)
        self.assertEqual(canonical["opening_story"]["worked_example"], {})
        self.assertNotIn('data-story-example="true"', render_html(canonical))

    def test_mathematical_worked_example_requires_a_formula_step(self) -> None:
        raw = config()
        for step in raw["opening_story"]["worked_example"]["steps"]:
            step["formula"] = ""
        with self.assertRaisesRegex(ValueError, "requires at least one formula step"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_worked_example_step_requires_rule_and_explanation(self) -> None:
        raw = config()
        raw["opening_story"]["worked_example"]["steps"][0]["explanation"] = ""
        with self.assertRaisesRegex(ValueError, "missing required field: explanation"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_worked_example_rejects_logic_only_without_a_concrete_case(self) -> None:
        for missing_field in ("scenario", "inputs", "observable"):
            with self.subTest(missing_field=missing_field):
                raw = config()
                raw["opening_story"]["worked_example"].pop(missing_field)
                with self.assertRaisesRegex(ValueError, f"worked_example.*{missing_field}"):
                    normalize_briefing_config(raw, require_source_url=True)

    def test_worked_example_rejects_an_abstract_scenario_label(self) -> None:
        raw = config()
        raw["opening_story"]["worked_example"]["scenario"] = "一般情况"
        with self.assertRaisesRegex(ValueError, "bounded concrete case"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_worked_example_rejects_placeholder_input_values(self) -> None:
        raw = config()
        raw["opening_story"]["worked_example"]["inputs"][0]["value"] = "待填写"
        with self.assertRaisesRegex(ValueError, "actual value, state, label, or condition"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_story_renders_before_briefing_in_html_and_markdown(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        self.assertEqual(canonical["opening_story"]["version"], 3)
        self.assertEqual(
            canonical["opening_story"]["logic_chain"],
            opening_story()["logic_chain"],
        )
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]})
        markdown = render_markdown(canonical)
        self.assertLess(html.index('data-opening-story="true"'), html.index('data-briefing-body="true"'))
        self.assertLess(html.index('data-opening-story="true"'), html.index('data-story-example="true"'))
        self.assertLess(html.index('data-story-example="true"'), html.index('data-briefing-body="true"'))
        details_tag = html[html.index('<details class="story-worked-example"'):html.index(">", html.index('<details class="story-worked-example"'))]
        self.assertNotIn(" open", details_tag)
        self.assertIn("展开完整例子与公式推导", html)
        self.assertIn('id="MathJax-script"', html)
        self.assertIn('class="example-scenario"', html)
        self.assertIn('class="example-input-table"', html)
        self.assertIn('class="example-observable"', html)
        self.assertLess(markdown.index("## 开篇故事"), markdown.index("## 日报正文"))
        self.assertLess(markdown.index("### 完整例子"), markdown.index("## 日报正文"))
        self.assertIn("t_{\\mathrm{resolve}}=\\hbar/\\Delta", markdown)
        self.assertIn("**具体场景：**", markdown)
        self.assertIn("**本例输入**", markdown)
        debrief_labels = [
            "1. 概念名称与一句话定义",
            "2. 故事元素与现实对应",
            "3. 这个类比没有覆盖的边界",
            "4. 它可能误导你的地方",
        ]
        self.assertEqual(
            [label for _, label in sorted((html.index(label), label) for label in debrief_labels)],
            debrief_labels,
        )
        self.assertEqual(
            [label for _, label in sorted((markdown.index(label), label) for label in debrief_labels)],
            debrief_labels,
        )
        self.assertLess(html.index(debrief_labels[-1]), html.index('data-story-example="true"'))
        self.assertLess(markdown.index(debrief_labels[-1]), markdown.index("### 完整例子"))
        self.assertEqual(len(feedback["items"]), 1)
        self.assertFalse(any(entry["concept"] == "spectral gap" for entry in feedback["items"]))

    def test_html_and_markdown_preserve_more_than_six_story_paragraphs_in_order(self) -> None:
        raw = config()
        markers = [f"段落顺序标记{i}" for i in range(1, 8)]
        original = raw["opening_story"]["paragraphs"]
        raw["opening_story"]["paragraphs"] = [
            f"{markers[index]}：{paragraph}"
            for index, paragraph in enumerate(
                [
                    *original,
                    "复核者保留同一组输入和运算规则。",
                    "交付者确认两个结果及其可观察差异。",
                ]
            )
        ]
        canonical = normalize_briefing_config(raw, require_source_url=True)
        html = render_html(canonical)
        markdown = render_markdown(canonical)
        self.assertEqual(len(canonical["opening_story"]["paragraphs"]), 7)
        self.assertEqual([html.index(marker) for marker in markers], sorted(html.index(marker) for marker in markers))
        self.assertEqual(
            [markdown.index(marker) for marker in markers],
            sorted(markdown.index(marker) for marker in markers),
        )

    def test_story_and_example_surfaces_use_theme_tokens(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        html = render_html(canonical)
        required_declarations = (
            "background: var(--story-surface);",
            "background: var(--story-panel);",
            "background: var(--story-subtle);",
            "background: var(--story-warning-surface);",
            "background: var(--table-surface);",
            "color: var(--ink);",
        )
        for declaration in required_declarations:
            self.assertIn(declaration, html)
        story_css = html[html.index(".opening-story {"):html.index(".briefing-body > h2 {")]
        for fixed_surface in (
            "background: rgba(255, 255, 255, 0.72);",
            "background: rgba(255, 255, 255, 0.78);",
            "background: rgba(238, 247, 246, 0.76);",
            "background: #fff;",
        ):
            self.assertNotIn(fixed_surface, story_css)

    def test_story_palette_and_component_contract_passes_design_audit(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        html = apply_design_system(render_html(canonical), "cosmic", "light")
        self.assertEqual(design_audit_issues(html), [])
        self.assertIn(
            'html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(table)',
            html,
        )

    def test_design_audit_rejects_low_contrast_or_fixed_story_surfaces(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        html = apply_design_system(render_html(canonical), "cosmic", "light")
        low_contrast = html.replace("--story-panel:#101A35;", "--story-panel:#FFFFFF;", 1)
        self.assertTrue(
            any("cosmic story contrast --ink/--story-panel" in issue for issue in design_audit_issues(low_contrast))
        )
        fixed_surface = html.replace(
            "background: var(--story-warning-surface);",
            "background: #fff7ed;",
            1,
        )
        self.assertTrue(
            any(".example-non-conclusion" in issue for issue in design_audit_issues(fixed_surface))
        )

    def test_worked_example_content_is_html_escaped(self) -> None:
        raw = config()
        raw["opening_story"]["worked_example"]["steps"][0]["action"] = '<img src=x onerror="alert(1)">'
        canonical = normalize_briefing_config(raw, require_source_url=True)
        html = render_html(canonical)
        example_html = html[
            html.index('<details class="story-worked-example"'):
            html.index("</details>", html.index('<details class="story-worked-example"'))
        ]
        self.assertNotIn('<img src=x onerror="alert(1)">', example_html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", example_html)
        self.assertIn("具体场景", example_html)
        self.assertIn("本例输入", example_html)

    def test_briefing_grounded_story_must_reference_a_published_story(self) -> None:
        raw = config()
        raw["opening_story"]["grounding_kind"] = "briefing_items"
        raw["opening_story"]["source_story_ids"] = ["not-published"]
        with self.assertRaisesRegex(ValueError, "unpublished story IDs"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_ranker_selects_eight_academic_and_twelve_social_items_deterministically(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        repeated = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        self.assertEqual(ranked["ranking_manifest"], repeated["ranking_manifest"])
        self.assertEqual(ranked["ranking_manifest"]["selected_counts"], {"academic": 8, "social": 12})
        self.assertEqual([len(section["items"]) for section in ranked["sections"]], [8, 12])
        academic_items = ranked["sections"][0]["items"]
        self.assertEqual(
            [item["ranking"]["rank"] for item in academic_items],
            list(range(1, len(academic_items) + 1)),
        )
        self.assertEqual(
            [item["ranking"]["base_score"] for item in academic_items],
            sorted((item["ranking"]["base_score"] for item in academic_items), reverse=True),
        )
        canonical = normalize_briefing_config(ranked, require_source_url=True)
        self.assertEqual(
            canonical["opening_story"]["source_story_ids"][0],
            academic_items[0]["story_id"],
        )
        self.assertEqual(audit_ranking_delivery(ranked), [])

    def test_ranked_daily_story_rejects_a_non_top_academic_default(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ranked["opening_story"]["source_story_ids"] = [ranked["sections"][0]["items"][1]["story_id"]]
        with self.assertRaisesRegex(ValueError, "rank-1 highest-impact academic story_id"):
            normalize_briefing_config(ranked, require_source_url=True)

    def test_ranked_daily_story_accepts_custom_academic_source_classes(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        for item in ranked["sections"][0]["items"]:
            item["source_class"] = "peer_reviewed"
            item["ranking"]["source_class"] = "peer_reviewed"
        canonical = normalize_briefing_config(ranked, require_source_url=True)
        self.assertEqual(
            canonical["opening_story"]["source_story_ids"][0],
            ranked["sections"][0]["items"][0]["story_id"],
        )

    def test_ranked_daily_story_allows_an_explicit_auditable_override(self) -> None:
        raw, prior = ranking_fixture()
        raw["story_delivery"]["selection_basis"] = "explicit_override"
        raw["story_delivery"]["override_reason"] = "用户明确要求沿用上一期的谱隙学习主题。"
        raw["opening_story"]["grounding_kind"] = "learner_profile"
        raw["opening_story"]["source_story_ids"] = []
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        canonical = normalize_briefing_config(ranked, require_source_url=True)
        self.assertEqual(canonical["story_delivery"]["selection_basis"], "explicit_override")

    def test_explicit_story_override_requires_a_reason(self) -> None:
        raw = config()
        raw["story_delivery"]["selection_basis"] = "explicit_override"
        with self.assertRaisesRegex(ValueError, "explicit_override requires override_reason"):
            normalize_briefing_config(raw, require_source_url=True)

    def test_ranking_audit_rejects_academic_display_order_tampering(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ranked["sections"][0]["items"] = list(reversed(ranked["sections"][0]["items"]))
        failures = audit_ranking_delivery(ranked)
        self.assertIn("academic section must be displayed in rank order", failures)
        self.assertIn("academic section must be ordered by descending impact score", failures)

    def test_ranking_audit_reports_an_invalid_rank_without_crashing(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ranked["sections"][0]["items"][0]["ranking"]["rank"] = "invalid"
        failures = audit_ranking_delivery(ranked)
        self.assertTrue(any("ranking score or rank is invalid" in failure for failure in failures))
        self.assertIn("academic ranking must use contiguous ranks starting at 1", failures)

    def test_strict_audit_rejects_attempts_to_weaken_delivery_quotas(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ranked["delta_policy"] = {"mode": "delta_first"}
        ranked["academic_delivery"].update({
            "minimum_items": 1,
            "minimum_new_items": 1,
            "minimum_non_arxiv_items": 1,
            "maximum_continuing_items": 9,
        })
        ranked["social_delivery"].update({
            "minimum_items": 1,
            "maximum_items": 99,
            "minimum_new_or_material_update": 1,
            "maximum_items_per_organization": 99,
        })
        result = audit(ranked)
        self.assertEqual(result["status"], "fail")
        for expected in (
            "academic_delivery.minimum_items must be at least 7",
            "academic_delivery.minimum_new_items must be at least 4",
            "academic_delivery.minimum_non_arxiv_items must be at least 2",
            "academic_delivery.maximum_continuing_items must be at most 3",
            "social_delivery.minimum_items must be at least 10",
            "social_delivery publication range must stay within 10-14 items",
            "social_delivery.minimum_new_or_material_update must be at least 7",
            "social_delivery.maximum_items_per_organization must be at most 2",
        ):
            self.assertIn(expected, result["failures"])

    def test_ranker_rejects_candidate_only_evidence_before_scoring_selection(self) -> None:
        raw, prior = ranking_fixture()
        raw["sections"][1]["items"][0]["evidence_level"] = "AI HOT API candidate"
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ledger = ranked["ranking_manifest"]["candidate_ledger"]
        rejected = next(row for row in ledger if row["story_id"] == "s001")
        self.assertFalse(rejected["eligible"])
        self.assertFalse(rejected["selected"])
        self.assertIn("candidate_or_unverified_evidence", rejected["exclusion_reasons"])

    def test_ranker_deduplicates_story_identity_before_selection(self) -> None:
        raw, prior = ranking_fixture()
        duplicate = dict(raw["sections"][1]["items"][0])
        duplicate["id"] = "S999"
        duplicate["evidence_fingerprint"] = "duplicate-fingerprint"
        raw["sections"][1]["items"].append(duplicate)
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        duplicates = [
            row for row in ranked["ranking_manifest"]["candidate_ledger"]
            if row["story_id"] == duplicate["story_id"]
        ]
        self.assertEqual(sum(row["selected"] for row in duplicates), 1)
        self.assertTrue(any("duplicate_candidate" in row["exclusion_reasons"] for row in duplicates))

    def test_ranked_daily_pipeline_passes_run_verify_finalize_verify(self) -> None:
        raw, prior = ranking_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            index_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in prior), encoding="utf-8")
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            staged_verification = verify_artifacts(run_dir, strict=True)
            self.assertEqual(staged_verification["status"], "pass", json.dumps(staged_verification, ensure_ascii=False, indent=2))
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(run_dir), strict=True)), 0)
            self.assertEqual(verify_artifacts(root / "news" / "2026-07-10", strict=True)["status"], "pass")

    def test_normalizer_preserves_ranking_evidence(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        canonical = normalize_briefing_config(ranked, require_source_url=True)
        self.assertEqual(canonical["ranking_policy"]["algorithm_version"], "news-ranker-v1")
        self.assertEqual(canonical["ranking_manifest"]["selected_counts"]["academic"], 8)
        self.assertEqual(canonical["sections"][0]["items"][0]["ranking"]["rank"], 1)

    def test_lossy_question_mark_text_is_blocking(self) -> None:
        broken = config([with_fields(item(), facts="中文事实???????")])
        with self.assertRaisesRegex(ValueError, "encoding-corrupted"):
            normalize_briefing_config(broken, require_source_url=True)

    def test_unicode_survives_html_render(self) -> None:
        raw = config([with_fields(item(), title="今日量子日报", facts="中文事实", judgment="中文判断", concepts=["量子纠错"])])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]})
        self.assertIn("今日量子日报", html)
        self.assertIn("中文事实", html)
        self.assertIn("charset=\"utf-8\"", html)
        self.assertNotIn("\ufffd", html)

    def test_unsafe_url_is_blocking(self) -> None:
        bad = config([item(url="javascript:alert(1)")])
        result = audit(bad)
        self.assertEqual(result["status"], "fail")

    def test_duplicate_concept_is_normalized_once_for_html_and_feedback(self) -> None:
        raw = config([with_fields(item(concept="QSVT"), concepts=["QSVT", "qsvt", "LUCI"])])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertEqual(html.count('class="concept-chip"'), len(feedback["items"]))
        self.assertEqual({concept_identity(x["block_id"], x["concept"]) for x in feedback["items"]}, {"N001::qsvt", "N001::luci"})

    def test_html_initializes_all_unrated_feedback_without_legacy_top_level_items(self) -> None:
        canonical = normalize_briefing_config(config([with_fields(item(), concepts=["QSVT", "LUCI"])]), require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]})
        self.assertIn('"items":[{', html)
        self.assertIn("const BRIEFING_ITEMS", html)
        self.assertNotIn("const itemMap = new Map(CONFIG.items.map", html)
        self.assertIn("const INITIAL_BY_ID", html)
        self.assertIn("...(initial || {})", html)

    def test_required_academic_delivery_needs_formal_item_and_section(self) -> None:
        raw = config([item()])
        raw["academic_delivery"] = {"required": True, "minimum_items": 5}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("academic_delivery requires" in message for message in result["failures"]))

    def test_chinese_analysis_contract_blocks_english_facts_judgment_and_relevance(self) -> None:
        raw = config([with_fields(item(), relevance="English-only relevance")])
        raw["analysis_language"] = "zh-CN"
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("must include Chinese analysis text" in message for message in result["failures"]))

    def test_academic_item_is_preserved_in_dedicated_delta_section(self) -> None:
        raw = config([with_fields(item(url="https://journals.aps.org/prxquantum/abstract/10.1103/example"), category="Quantum research")])
        raw["academic_delivery"] = {"required": False, "no_signal_reason": "section routing test"}
        transformed, _, _ = transform_config(raw, [], __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(transformed["sections"][0]["title"], "Academic research and venue evidence")

    def test_final_delta_cannot_weaken_four_to_six_new_academic_floor(self) -> None:
        raw = config([
            with_fields(item(f"A{index:03d}", url=f"https://arxiv.org/abs/2607.00{index:03d}"), category="Quantum research", novelty="continuing")
            for index in range(1, 6)
        ])
        raw["sections"] = [{"title": "Academic research and venue evidence", "items": raw["sections"][0]["items"]}]
        raw["academic_delivery"] = {"required": True, "minimum_items": 5, "minimum_new_items": 3, "maximum_new_items": 4}
        raw["delta_policy"] = {"mode": "delta_first"}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertIn("academic_delivery.minimum_items must be at least 7", result["failures"])
        self.assertIn("academic_delivery.minimum_new_items must be at least 4", result["failures"])
        self.assertTrue(any("4-4 new academic paper items; found 0" in message for message in result["failures"]))

    def test_normalizer_preserves_delta_policy(self) -> None:
        raw = config()
        raw["delta_policy"] = {"mode": "delta_first", "continuing_mode": "one-line"}
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(canonical["delta_policy"], raw["delta_policy"])

    def test_existing_story_cannot_be_forced_new(self) -> None:
        raw = config([with_fields(item(), novelty="new")])
        prior = [{"story_id": "n001", "last_seen": "2026-07-09", "source_url": "https://example.org/story", "summary": "old"}]
        _, manifest, _ = transform_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(manifest["counts"]["new"], 0)
        self.assertEqual(manifest["counts"]["continuing"], 1)

    def test_corrupt_prior_summary_does_not_leak_into_html(self) -> None:
        raw = config([item()])
        prior = [{"story_id": "n001", "last_seen": "2026-07-09", "source_url": "https://example.org/story", "summary": "??? permutation tree?coined quantum walks ? color-ordered amplitudes ???????"}]
        transformed, _, _ = transform_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7, "one-line")
        facts = transformed["sections"][0]["items"][0]["facts"]
        self.assertIn("历史编码损坏", facts)
        self.assertNotIn("????????", facts)

    def test_index_upsert_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "story_index.jsonl"
            record = {"story_id": "same", "last_seen": "2026-07-10", "status": "new"}
            upsert_index(path, [record])
            upsert_index(path, [record])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_staging_failure_does_not_touch_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(config(), ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            html_path = run_dir / "briefing_reader_2026-07-10.html"
            html_path.write_text("broken", encoding="utf-8")
            result = verify_artifacts(run_dir, strict=True)
            self.assertEqual(result["status"], "fail")
            self.assertFalse(index_path.exists())

    def test_run_verify_finalize_verify_is_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(config(), ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            self.assertEqual(verify_artifacts(run_dir, strict=True)["status"], "pass")
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(run_dir), strict=True)), 0)
            final_root = root / "news" / "2026-07-10"
            self.assertEqual(verify_artifacts(final_root, strict=True)["status"], "pass")
            self.assertEqual(len(index_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_local_storage_contract_is_versioned_and_stale_entries_are_filtered(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertIn("CONFIG.config_fingerprint", html)
        self.assertIn("const initialIds = new Set", html)
        self.assertIn("entry.annotation_kind === 'news_freeform'", html)

    def test_run_does_not_mutate_learner_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "knowledge_profile.json"
            profile.write_text('{"sentinel": true}', encoding="utf-8")
            raw = config()
            raw["profile_path"] = str(profile)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            before = profile.read_bytes()
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(root / "story_index.jsonl"), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            self.assertEqual(profile.read_bytes(), before)

    def test_venue_ledger_without_http_evidence_fails(self) -> None:
        academic = config([with_fields(item(url="https://arxiv.org/abs/2607.00001"), category="Quantum research", evidence_level="arXiv preprint")])
        academic["academic_search"] = {"required_venues": ["aps-prl"], "rows": [{"venue": "aps-prl", "result": "checked_no_hit"}]}
        result = audit(academic)
        self.assertEqual(result["status"], "fail")

    def test_evidenced_arxiv_only_coverage_is_blocked(self) -> None:
        venues = ["aps-prl", "aps-pra", "aps-prx", "nature", "science", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"]
        rows = []
        for venue in venues:
            rows.append({
                "term": "quantum error suppression", "venue": venue, "result": "checked", "url": "",
                "evidence": {
                    "query_url": f"https://{venue}.example/search", "retrieved_at": "2026-07-10T00:00:00Z",
                    "status_code": 200, "final_url": f"https://{venue}.example/search", "response_hash": "a" * 64,
                    "result_count": 0,
                },
            })
        academic = config([with_fields(item(url="https://arxiv.org/abs/2607.00001"), category="Quantum research", evidence_level="arXiv preprint", venue_sweep_note="Official venue endpoints checked; no stronger venue page found.")])
        academic["academic_delivery"] = {"required": True, "minimum_items": 1}
        academic["academic_search"] = {"required_venues": venues, "topics": [{"term": "quantum error suppression", "checked_venues": venues, "primary_hits": [], "status": "evidenced"}], "rows": rows}
        result = audit(academic)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("non-arXiv formal venue paper" in message for message in result["failures"]))

    def test_required_daily_delivery_needs_distinct_social_section(self) -> None:
        raw = config([with_fields(item(url="https://journals.aps.org/prl/abstract/10.1103/example"), category="Quantum research")])
        raw["academic_delivery"] = {"required": True, "minimum_items": 1}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertIn("daily briefing requires a dedicated social news section", result["failures"])

    def test_required_daily_delivery_needs_social_candidate_pool_coverage(self) -> None:
        social = with_fields(item("S001", url="https://example.org/social"), published_at="2026-07-10", evidence_fingerprint="social-v1")
        raw = config([social])
        raw["sections"] = [
            {"title": "Academic research", "items": [with_fields(item(url="https://journals.aps.org/prl/abstract/10.1103/example"), category="Quantum research")]},
            {"title": "Social news", "items": [social]},
        ]
        raw["academic_delivery"] = {"required": True, "minimum_items": 1}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("social_candidate_pool" in message for message in result["failures"]))

    def test_normalizer_preserves_social_candidate_pool(self) -> None:
        raw = config()
        raw["social_candidate_pool"] = {"required_source_classes": ["ai_hot"], "checked_at": "2026-07-10T00:00:00Z"}
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(canonical["social_candidate_pool"], raw["social_candidate_pool"])

    def test_social_section_is_preserved_by_delta(self) -> None:
        raw = config([item()])
        raw["sections"] = [{"title": "Social news", "items": [item()]}]
        transformed, _, _ = transform_config(raw, [], __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(transformed["sections"][0]["title"], "社会新闻")

    def test_social_research_announcement_is_not_counted_as_academic_paper(self) -> None:
        social = with_fields(
            item("S001", url="https://alignment.anthropic.com/2026/example"),
            title="Anthropic 发布智能体安全研究",
            category="AI 安全研究与社会影响",
            evidence_level="official research publication",
            source_title="Anthropic Alignment Science Blog - Research update",
        )
        raw = config([social])
        raw["sections"] = [{"title": "社会新闻", "items": [social]}]
        result = audit(raw)
        self.assertEqual(result["academic_items"], 0)

    def test_68_concepts_remain_unrated_and_interactive(self) -> None:
        concepts = [f"concept-{index:02d}" for index in range(68)]
        raw = config([with_fields(item(concept=concepts[0]), concepts=concepts)])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertEqual(len(feedback["items"]), 68)
        self.assertTrue(all(entry["status"] == "unrated" for entry in feedback["items"]))
        self.assertEqual(html.count('class="concept-chip"'), 68)
        self.assertIn("Download JSON", html)
        self.assertIn('data-lean-bg-option="cosmic"', html)
        self.assertNotIn("lean-html-feedback-dock", html)
        self.assertIn("PaperTraceFeedbackUX", html)
        self.assertIn('id="newsSelectionToolbar"', html)
        self.assertIn("createAutosave", html)
        self.assertIn("autosave.schedule('status-change')", html)
        self.assertNotIn("Save mark", html)
        self.assertNotIn('id="saveBtn"', html)



class EverydayOpeningTests(unittest.TestCase):
    """In-memory contract/render tests, not a substitute for teaching review."""

    def raw(self) -> dict:
        value = config()
        value["opening_story"].update(
            version=4,
            title="并排走路",
            paragraphs=["两个人从同一条线并排走。脚步越接近，短时间里越难看出谁走得快；多看一会儿，差距才逐渐显出来。"],
        )
        return value

    def normalize(self, value: dict) -> dict:
        return normalize_briefing_config(value, require_source_url=True)

    def test_v4_accepts_one_short_scene_without_example_numbers(self) -> None:
        raw = self.raw()
        canonical = self.normalize(raw)
        story = canonical["opening_story"]
        self.assertEqual(story["version"], 4)
        self.assertEqual(story["paragraphs"], raw["opening_story"]["paragraphs"])
        self.assertEqual(story["worked_example"], self.normalize(config())["opening_story"]["worked_example"])
        self.assertNotIn("0.658", " ".join(story["paragraphs"]))
        self.assertEqual(self.normalize(canonical), canonical)

    def test_v4_has_no_total_length_or_paragraph_ceiling(self) -> None:
        raw = self.raw()
        # Transport stress case, not a recommended teaching draft.
        paragraphs = [f"第 {n} 段。" + "仍需保留的文字。" * 50 for n in range(12)]
        raw["opening_story"]["paragraphs"] = paragraphs
        canonical = self.normalize(raw)
        self.assertEqual(canonical["opening_story"]["paragraphs"], paragraphs)
        html, markdown = render_html(canonical), render_markdown(canonical)
        for paragraph in paragraphs:
            self.assertIn(paragraph, html)
            self.assertIn(paragraph, markdown)

    def test_v4_preserves_duplicates_and_transport_boundary(self) -> None:
        raw = self.raw()
        raw["opening_story"]["paragraphs"] = ["甲" * 2000] * 2
        self.assertEqual(self.normalize(raw)["opening_story"]["paragraphs"], ["甲" * 2000] * 2)
        raw["opening_story"]["paragraphs"][0] += "乙"
        with self.assertRaisesRegex(ValueError, "exceeds 2000"):
            self.normalize(raw)
        self.assertEqual(len(raw["opening_story"]["paragraphs"][0]), 2001)

    def test_v4_rejects_empty_or_nontext_scene(self) -> None:
        for paragraphs in ([], ["   "], [123], [{"text": "scene"}]):
            with self.subTest(paragraphs=paragraphs), self.assertRaises(ValueError):
                raw = self.raw()
                raw["opening_story"]["paragraphs"] = paragraphs
                self.normalize(raw)

    def test_v4_factual_and_example_overflow_fails_without_clipping(self) -> None:
        for field, limit in (("title", 160), ("concept_definition", 800), ("logic_chain", 800)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "exceeds"):
                raw = self.raw()
                raw["opening_story"][field] = "甲" * (limit + 1)
                self.normalize(raw)
        raw = self.raw()
        raw["opening_story"]["worked_example"]["steps"][0]["explanation"] = "甲" * 1601
        with self.assertRaisesRegex(ValueError, "exceeds 1600"):
            self.normalize(raw)

    def test_versions_are_explicit_and_legacy_inference_is_unchanged(self) -> None:
        for version in (None, True, False, "4", 4.0, 0, 5, 99):
            raw = self.raw()
            raw["opening_story"]["version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "supported integer"):
                self.normalize(raw)
        for version in (1, 2, 3):
            raw = config()
            raw["opening_story"]["version"] = version
            self.assertEqual(self.normalize(raw)["opening_story"]["version"], 3)
        raw = config()
        raw["opening_story"].pop("version")
        self.assertEqual(self.normalize(raw)["opening_story"]["version"], 3)
        raw["opening_story"].pop("worked_example")
        raw["story_delivery"]["worked_example_required"] = False
        self.assertEqual(self.normalize(raw)["opening_story"]["version"], 1)

    def test_v3_numerical_contract_is_not_weakened(self) -> None:
        raw = self.raw()
        raw["opening_story"]["version"] = 3
        with self.assertRaises(ValueError):
            self.normalize(raw)
        self.assertEqual(self.normalize(config())["opening_story"]["version"], 3)

    def test_v4_still_requires_a_complete_example(self) -> None:
        for field in ("worked_example",):
            raw = self.raw()
            raw["opening_story"].pop(field)
            raw["story_delivery"]["worked_example_required"] = False
            with self.assertRaisesRegex(ValueError, "worked_example"):
                self.normalize(raw)
        for field in ("scenario", "inputs", "observable"):
            raw = self.raw()
            raw["opening_story"]["worked_example"].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.normalize(raw)

    def test_v4_full_text_concealment_and_source_checks_remain(self) -> None:
        raw = self.raw()
        raw["opening_story"]["paragraphs"] = ["普通场景。" * 220 + "谱隙"]
        with self.assertRaisesRegex(ValueError, "reveals the concept"):
            self.normalize(raw)
        raw = self.raw()
        raw["opening_story"].update(grounding_kind="briefing_items", source_story_ids=["not-published"])
        with self.assertRaisesRegex(ValueError, "unpublished"):
            self.normalize(raw)

    def test_v4_render_order_escaping_and_feedback_parity(self) -> None:
        raw = self.raw()
        raw["opening_story"]["title"] = "<script>not executable</script>"
        canonical = self.normalize(raw)
        html, markdown = render_html(canonical), render_markdown(canonical)
        for output in (html, markdown):
            labels = ["这里真正要理解的是", "对应真实概念", "这个比喻没有覆盖", "不能由此推出"]
            positions = [output.index(label) for label in labels]
            self.assertEqual(positions, sorted(positions))
            self.assertNotIn("1. 概念名称与一句话定义", output)
        self.assertIn("&lt;script&gt;", html)
        from html.parser import HTMLParser

        class Tags(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.scripts = []
                self.details = []

            def handle_starttag(self, tag, attrs):
                if tag == "script":
                    self.scripts.append(dict(attrs))
                if tag == "details" and "story-worked-example" in dict(attrs).get("class", ""):
                    self.details.append(dict(attrs))

        parsed, baseline = Tags(), Tags()
        parsed.feed(html)
        baseline.feed(render_html(self.normalize(self.raw())))
        # Serialized JSON may contain literal "<script>" text, but must not
        # create an extra executable HTML element or close its data container.
        self.assertEqual(parsed.scripts, baseline.scripts)
        self.assertEqual(len(parsed.details), 1)
        self.assertNotIn("open", parsed.details[0])
        self.assertEqual(
            export_feedback(canonical, Path("config.json"), "unrated", "none"),
            export_feedback(self.normalize(config()), Path("config.json"), "unrated", "none"),
        )

    def test_v4_synthetic_release_round_trip(self) -> None:
        # Isolated fixture only: never use the repository's news or profile data.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps(self.raw(), ensure_ascii=False), encoding="utf-8")
            output = root / "news" / "2026-07-10"
            index = root / "story_index.jsonl"
            args = Namespace(
                config=str(candidate), output_dir=str(output), index=str(index),
                date="2026-07-10", days=7, continuing_mode="one-line",
                design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((output / ".staging").iterdir())
            self.assertEqual(verify_artifacts(run_dir, strict=True)["status"], "pass")
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(run_dir), strict=True)), 0)
            self.assertEqual(verify_artifacts(output, strict=True)["status"], "pass")
            saved = json.loads((output / "news_feedback_config_delta_2026-07-10.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["opening_story"]["version"], 4)


if __name__ == "__main__":
    unittest.main()
