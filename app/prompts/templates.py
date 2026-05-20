# 大纲生成提示词
OUTLINE_TEMPLATE = """
你是一个专业的PPT大纲生成专家。请根据以下主题生成一个结构清晰、逻辑连贯的PPT大纲。
严格按照输出格式输出，不要输出多余内容。
主题：{topic}

{requirements}

要求：
1. 大纲应包含 PPT 总标题、至少 3 个主要章节，每章至少 2 个小节
2. 每个小节必须同时给出：小节标题、核心目标、要点（2～4 条）
3. 核心目标用一句话说明本页要达成的表达目的（15～40 字）
4. 要点为可上屏的短语，每条 8～20 字，用中文分号「；」分隔写在同一行
5. 请使用中文；严禁输出格式示例、解释性文字或 Markdown 代码块

输出格式（必须严格遵守，不得增删字段名或层级）：

- <PPT总标题>

- 1. <第一章节标题>
   a. <第一小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
   b. <第二小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
- 2. <第二章节标题>
   a. <第一小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
   b. <第二小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
- 3. <第三章节标题>
   a. <第一小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
   b. <第二小节标题>
      核心目标：<本页核心目标>
      要点：<要点1>；<要点2>；<要点3>
"""

# 内容补全提示词
CONTENT_TEMPLATE = """
你是 PPT 单页正文撰写助手。根据大纲节点与上下文，只输出可直接贴在幻灯片上的正文。

【本页大纲】
章节：{section}
页面标题：{node_title}
核心目标：{goal}
要点：
{bullets}

【上下文信息】（检索材料或任务要求，可能为空）
{context}

【输出要求】必须全部遵守：
1. 只输出本页幻灯片正文（标题、要点、短句、表格等），使用中文。
2. 禁止输出：设计说明、版式建议、字数统计、制作备注、引用来源标注、对提示词的回应、「以下是为PPT设计的…」等元话语。
3. 禁止输出 Markdown 代码块围栏（不要 ```）。
4. 不要写「左栏/右栏」「实际PPT中可…」「设计说明」「注：」等解释性文字。
5. 内容紧扣本页大纲；有上下文时优先依据上下文，无上下文时基于常识撰写，勿编造具体文献或网址出处。
6. 篇幅适合单页 PPT：精炼，总字数建议 150～250 字以内（除非上下文明确要求更长）。
"""

# RAG检索提示词
RAG_TEMPLATE = """
你是一个PPT大纲智能生成与内容补全系统的助手。

用户的问题是：{{query}}

相关文档信息：
{{relevant_docs}}

请根据上述信息，生成详细的回答。
"""

SEARCH_PLAN_PROMPT = """
你是一个知识检索规划专家。用户需要制作一个关于"{topic}"的PPT，你需要分析这个主题，规划出需要从外部搜索哪些知识才能生成高质量的大纲。

请分析主题，输出你需要搜索的关键词列表。要求：
1. 每个关键词应该是一个具体的、可搜索的查询词
2. 关键词应该覆盖主题的不同方面（背景、核心概念、应用、案例、趋势等）
3. 关键词数量在2-5个之间
4. 每个关键词尽量具体，避免过于宽泛

请严格按照以下JSON格式输出，不要输出其他内容：
{{"search_queries": ["关键词1", "关键词2", "关键词3"]}}
"""







SEARCH_EVALUATE_PROMPT = """
你是一个知识充分性评估专家。

用户主题：{topic}

已收集到的知识摘要：
{collected_knowledge}

请评估当前收集到的知识是否足够支撑生成一个高质量的PPT大纲。要求：
1. 知识是否覆盖了主题的核心概念
2. 知识是否包含具体案例或数据
3. 知识是否覆盖了不同角度和维度

请严格按照以下JSON格式输出，不要输出其他内容：
{{"sufficient": true/false, "reason": "评估理由", "additional_queries": ["需要补充搜索的关键词"]}}
如果知识已充分，additional_queries为空列表。
"""

SEARCH_SUMMARIZE_PROMPT = """
你是一个知识整理专家。请将以下搜索到的多条信息整理成一份结构化的知识摘要，用于后续生成PPT大纲。

主题：{topic}

搜索结果：
{search_results}

要求：
1. 提取每条搜索结果中的关键信息和核心观点
2. 去除重复内容
3. 按主题相关性组织信息
4. 保留重要的数据、案例和引用
5. 使用中文输出
"""


OUTLINE_JSON_TEMPLATE = """
You are generating a PPT narrative outline. Return only one valid JSON object.

The JSON must follow protocolVersion "ppt-narrative-outline.v1".
Required top-level fields:
- protocolVersion: "ppt-narrative-outline.v1"
- language: "zh-CN"
- presentationTitle: string
- targetSlideCount: integer from 3 to 50
- sections: array

Each section must contain:
- sectionId: "sec-01", "sec-02", ...
- sectionTitle
- sectionObjective
- slideRange: {"start": number, "end": number}
- slides

Each slide must contain:
- slideId: "slide-001", "slide-002", ...
- slideNumber
- slideRole: one of cover, toc, transition, content, case-study, summary, qa, appendix
- slideTitle
- keyPoints: 2 to 5 strings
- notes: optional short planning notes

Rules:
- The number of slides across all sections must equal targetSlideCount when the user provides a target page count.
- Slides must be continuous and start from 1: slideNumber must be 1, 2, 3 ... targetSlideCount with no missing numbers.
- slideId must match slideNumber exactly: slide-001 for slideNumber 1, slide-002 for slideNumber 2, etc.
- section slideRange must match the first and last slideNumber inside that section.
- Use Chinese content unless the user explicitly requests another language.
- Use the reference context as the primary factual basis when it is provided.
- If reference context is provided, reflect its concrete concepts in sectionTitle, slideTitle, and keyPoints.
- Treat audience/target audience as the people receiving the presentation, never as the presenter identity.
- Do not create presenter identity fields such as "汇报人", "我是...", or "由...进行汇报" unless the user explicitly provides a presenter identity.
- Do not output Markdown, comments, or code fences.

Topic:
{topic}

Requirements:
{requirements}

Reference context:
{reference_context}
""".strip()


PAGE_CONTENT_JSON_TEMPLATE = """
You are expanding one PPT slide into structured page content. Return only one valid JSON object.

The JSON must follow protocolVersion "ppt-page-content.v1".
Required top-level fields:
- protocolVersion: "ppt-page-content.v1"
- language: "zh-CN"
- presentationTitle
- researchPolicy
- slides: array with exactly one slide

researchPolicy must contain:
- triggerReason: one of user_requested, insufficient_input, fact_verification
- depthLevel: one of light, standard, deep
- sourcePriority: one to five values from official_sites, government_reports, academic_sources, authoritative_media, industry_reports
- maxSourcesPerSlide: optional integer from 1 to 8

The slide must contain:
- slideId: "slide-001" if no slide id is provided
- slideNumber: integer from 1 to 50
- slideRole: one of cover, toc, transition, content, case-study, summary, qa, appendix
- pageGoal
- slideTitle
- coreMessage
- displayBullets: 3 to 5 strings
- keyData: array, may be empty
- evidencePack: array, may be empty if no reliable sources are available
- actionableTakeaway
- speakerNotes

Do not invent fake sources. If the context has no reliable source, use evidencePack: [] and keyData: [].
Treat audience/target audience as the people receiving the presentation, never as the presenter identity.
Do not write "汇报人", "我是...", "由课程讲师进行", or similar presenter identity statements unless the user explicitly provides a presenter identity.
If the audience is "课程讲师", write content as being addressed to course instructors, not as being presented by a course instructor.
Do not output Markdown, comments, or code fences.

Outline node:
{outline_node}

Reference context:
{context}
""".strip()


SPEAKER_NOTES_JSON_TEMPLATE = """
You are generating speaker notes for one PPT slide. Return only one valid JSON object.

Required JSON shape:
{
  "notes": "string"
}

Rules:
- Write in Chinese unless the style requirement explicitly asks for another language.
- The notes must be suitable for oral delivery, not a copy of the slide body.
- Add background explanation, concept clarification, and transitions to nearby context when useful.
- Use only the slide content and the provided knowledge evidence as factual basis.
- Do not introduce unsourced facts, fake numbers, fake citations, or fake source names.
- Treat the target audience as listeners, not as the speaker. Do not say "我是课程讲师" or claim the speaker is the audience unless explicitly provided.
- Prefer neutral opening phrases such as "本页可以先说明..." instead of inventing a speaker identity.
- If evidence is weak or empty, keep the notes cautious and phrase them as explanation of the slide content.
- Keep the notes between 120 and 260 Chinese characters unless the style requirement says otherwise.
- Do not output Markdown, comments, code fences, or bullet lists.

Project id:
{project_id}

Slide id:
{slide_id}

Slide title:
{slide_title}

Slide content:
{slide_content}

Knowledge evidence:
{knowledge_evidence}

Style requirement:
{style_requirement}
""".strip()
