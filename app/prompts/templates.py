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
你正在生成 PPT 叙事大纲。仅返回一个合法的 JSON 对象。

JSON 必须遵循 protocolVersion "ppt-narrative-outline.v1"。
必需的顶层字段：
- protocolVersion: "ppt-narrative-outline.v1"
- language: "zh-CN"
- presentationTitle: string
- targetSlideCount: 3 到 50 的整数
- sections: array

每个 section 必须包含：
- sectionId: "sec-01", "sec-02", ...
- sectionTitle
- sectionObjective
- slideRange: {"start": number, "end": number}
- slides

每个 slide 必须包含：
- slideId: "slide-001", "slide-002", ...
- slideNumber
- slideRole: 取 cover, toc, transition, content, case-study, summary, qa, appendix 之一
- slideTitle
- keyPoints: 2 到 5 个字符串
- notes: 可选的简短规划备注

规则：
- 当用户提供了目标页数时，所有 section 中的 slide 总数必须等于 targetSlideCount。
- slide 必须连续且从 1 开始：slideNumber 必须是 1, 2, 3 ... targetSlideCount，不得缺号。
- slideId 必须与 slideNumber 严格对应：slideNumber 1 对应 slide-001，slideNumber 2 对应 slide-002，以此类推。
- section 的 slideRange 必须对应该 section 内第一个和最后一个 slideNumber。
- 除非用户明确要求其他语言，否则内容使用中文。
- 当提供了 reference context 时，以其作为主要事实依据。
- 若提供了 reference context，应在 sectionTitle、slideTitle 和 keyPoints 中体现其具体概念。
- 将 audience/target audience 视为演示的接收者，而非汇报人身份。
- 除非用户明确提供了汇报人身份，否则不要创建「汇报人」「我是...」「由...进行汇报」等汇报人身份字段。
- 不要输出 Markdown、注释或代码围栏。

主题：
{topic}

要求：
{requirements}

参考资料：
{reference_context}
""".strip()


PAGE_CONTENT_JSON_TEMPLATE = """
你正在将一页 PPT 扩写为结构化页面内容。仅返回一个合法的 JSON 对象。

JSON 必须遵循 protocolVersion "ppt-page-content.v1"。
必需的顶层字段：
- protocolVersion: "ppt-page-content.v1"
- language: "zh-CN"
- presentationTitle
- researchPolicy
- slides: 仅包含一页 slide 的数组

researchPolicy 必须包含：
- triggerReason: 取 user_requested, insufficient_input, fact_verification 之一
- depthLevel: 取 light, standard, deep 之一
- sourcePriority: 从 local_document, official_sites, government_reports, academic_sources, authoritative_media, industry_reports 中取 1 到 5 个值
- maxSourcesPerSlide: 可选，1 到 8 的整数

slide 必须包含：
- slideId: 若未提供 slide id，则使用 "slide-001"
- slideNumber: 1 到 50 的整数
- slideRole: 取 cover, toc, transition, content, case-study, summary, qa, appendix 之一
- pageGoal
- slideTitle
- coreMessage
- displayBullets: 3 到 5 个字符串
- keyData: 数组，可为空；若不为空，每项必须包含 label, value, unit, year, sourceRefId
- evidencePack: 数组，若无可靠来源可为空；若不为空，每项必须严格包含 sourceRefId, claim, sourceTitle, sourceType, url, publishDate, credibility, quote
- actionableTakeaway
- speakerNotes

正文内容规则：
- coreMessage、displayBullets、actionableTakeaway 三者不得重复表达同一句话。
- displayBullets 必须是页面上可展示的具体要点，不要写“学术汇报”“课程讲师”“受众对象”等任务元信息。
- displayBullets 不要直接复制 coreMessage 或 actionableTakeaway。
- actionableTakeaway 应是一个简短结论或行动启示，不要重复 coreMessage。
- speakerNotes 必须是演讲者可直接朗读的口播稿，不是“本页应该怎么讲”的说明。
- speakerNotes 不要使用“本页可以先说明”“讲解时可...”等建议式表达；应直接写成汇报现场会说的话。

evidencePack 每项字段规则：
- sourceRefId: "src-001", "src-002", ...
- claim: 该来源支持的具体事实主张
- sourceTitle: 来源标题；本地上传资料可写文件名或“本地参考资料”
- sourceType: 取 local_document, official_sites, government_reports, academic_sources, authoritative_media, industry_reports 之一
- url: 若是本地资料且没有 URL，使用空字符串 ""
- publishDate: YYYY-MM-DD；若本地资料没有发布日期，使用当前生成日期或检索日期
- credibility: 取 high 或 medium
- quote: 可为空字符串，但字段必须存在

不要使用 sourceDescription、keyClaim、retrievedAt 等非协议字段。
不要编造虚假来源。若 context 中没有可靠来源，请使用 evidencePack: [] 和 keyData: []。
将 audience/target audience 视为演示的接收者，而非汇报人身份。
除非用户明确提供了汇报人身份，否则不要写「汇报人」「我是...」「由课程讲师进行」等类似汇报人身份的表述。
若受众是「课程讲师」，内容应面向课程讲师讲述，而不是以课程讲师身份进行汇报。
不要输出 Markdown、注释或代码围栏。

大纲节点：
{outline_node}

参考资料：
{context}
""".strip()


SPEAKER_NOTES_JSON_TEMPLATE = """
你正在为一页 PPT 生成演讲备注。仅返回一个合法的 JSON 对象。

必需的 JSON 结构：
{
  "notes": "string"
}

规则：
- 除非 style requirement 明确要求其他语言，否则使用中文撰写。
- 备注应适合口头讲述，不要照搬幻灯片正文。
- 在有助于理解时，可补充背景说明、概念澄清以及与前后文的过渡。
- 仅以 slide content 和提供的 knowledge evidence 作为事实依据。
- 不要引入无来源的事实、虚假数字、虚假引用或虚假来源名称。
- 将目标受众视为听众，而非演讲者。不要说「我是课程讲师」或声称演讲者就是受众，除非已明确提供。
- 备注必须是演讲者可直接朗读的口播稿，不是讲解建议。
- 不要使用「本页可以先说明」「讲解时可」「这一页要」等建议式表达。
- 可以使用「各位老师好，接下来我们看到...」「这里想强调的是...」「这也引出了后面的...」等自然口播表达，但不要虚构具体姓名或身份。
- 若 evidence 较弱或为空，备注应谨慎，仅围绕 slide content 进行解释性表述。
- 除非 style requirement 另有说明，备注长度控制在 160 到 360 个汉字之间。
- 不要输出 Markdown、注释、代码围栏或 bullet 列表。

项目 id：
{project_id}

Slide id：
{slide_id}

页面标题：
{slide_title}

页面正文：
{slide_content}

知识证据：
{knowledge_evidence}

风格要求：
{style_requirement}
""".strip()
