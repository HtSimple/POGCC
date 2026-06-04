import type { HealthResponse, ModelInfoResponse, OutlineResponse } from './types'

const delay = (ms = 450) => new Promise((resolve) => window.setTimeout(resolve, ms))

function pickTopic(topic: string) {
  return topic.trim() || '人工智能在教育中的应用'
}

function getTitleFromNode(outlineNode: Record<string, unknown>) {
  const title = outlineNode.title
  return typeof title === 'string' && title.trim() ? title.trim() : '未命名页面'
}

export async function mockGetHealth(): Promise<HealthResponse> {
  await delay(180)
  return {
    status: 'healthy',
    version: 'mock'
  }
}

export async function mockGetModelInfo(): Promise<ModelInfoResponse> {
  await delay(180)
  return {
    current_provider: 'mock-deepseek',
    available_providers: ['mock-deepseek', 'mock-qwen']
  }
}

export async function mockSwitchModel(provider: string) {
  await delay(260)
  return {
    success: true,
    current_provider: provider,
    message: `Mock 模式：已切换到 ${provider}`
  }
}

export async function mockUploadDocument(filePath: string) {
  await delay(520)
  return {
    success: true,
    doc_id: `mock-doc-${Date.now()}`,
    message: `Mock 模式：已模拟入库 ${filePath}`
  }
}

export async function mockGenerateOutline(topic: string, requirements: string) {
  await delay(800)
  const resolvedTopic = pickTopic(topic)
  const outline: OutlineResponse = {
    title: resolvedTopic,
    sections: [
      {
        title: '1. 项目背景与目标',
        subsections: [
          {
            title: `${resolvedTopic}的背景与问题`,
            goal: '阐明主题背景与待解决的核心问题',
            bullets: ['行业背景', '痛点分析', '问题定义']
          },
          {
            title: '汇报目标与受众关注点',
            goal: '明确汇报目的与听众关切',
            bullets: ['汇报目标', '受众画像', '关键诉求']
          }
        ]
      },
      {
        title: '2. 核心内容分析',
        subsections: [
          {
            title: '关键概念与技术路线',
            goal: '解释核心概念并给出技术路径',
            bullets: ['核心概念', '技术架构', '实施路线']
          },
          {
            title: '典型应用场景',
            goal: '展示代表性应用场景与价值',
            bullets: ['场景一', '场景二', '应用成效']
          },
          {
            title: '方案价值与可行性',
            goal: '论证方案价值与落地可行性',
            bullets: ['价值主张', '资源需求', '可行性分析']
          }
        ]
      },
      {
        title: '3. 实施路径与总结',
        subsections: [
          {
            title: '落地流程与资源需求',
            goal: '说明实施步骤与所需资源',
            bullets: ['阶段划分', '关键里程碑', '资源清单']
          },
          {
            title: '风险控制与质量评估',
            goal: '识别风险并给出质量保障措施',
            bullets: ['主要风险', '应对策略', '质量指标']
          },
          {
            title: '总结与后续展望',
            goal: '归纳结论并展望未来工作',
            bullets: ['核心结论', '后续计划', '开放问题']
          }
        ]
      }
    ]
  }

  if (/商务|路演|客户/.test(requirements)) {
    outline.sections?.splice(2, 0, {
      title: '3. 商业价值',
      subsections: [
        {
          title: '收益分析与成本估算',
          goal: '量化收益与成本结构',
          bullets: ['收益来源', '成本构成', '投资回报']
        },
        {
          title: '竞争优势与推广策略',
          goal: '说明差异化优势与市场推广路径',
          bullets: ['竞争优势', '目标市场', '推广策略']
        }
      ]
    })
  }

  return {
    success: true,
    outline,
    message: 'Mock 模式：大纲生成成功'
  }
}

export async function mockSearchKnowledgeBatch(
  items: Array<{ index: number; id?: string; query: string }>,
  _refineKnowledge = false
) {
  await delay(800)
  const results = await Promise.all(
    items.map(async (item) => {
      const single = await mockSearchKnowledge(item.query)
      return {
        index: item.index,
        id: item.id,
        success: single.success,
        knowledge: single.knowledge,
        has_sources: true,
        message: single.message
      }
    })
  )
  return {
    success: results.every((r) => r.success),
    results,
    message: `Mock 模式：批量检索完成（${results.length} 页）`,
    elapsed_sec: 0.8
  }
}

export async function mockSearchKnowledge(topic: string) {
  await delay(700)
  const lines = topic.split('\n').filter(Boolean)
  const title = lines[lines.length - 2] || lines[lines.length - 1] || '当前页面'
  return {
    success: true,
    knowledge: [
      `【本地资料摘要】${title} 需要围绕主题目标、应用价值和可执行路径展开。`,
      '【来源 1】Mock 文档《项目章程》：强调任务目标、受众需求和交付物完整性。',
      '【来源 2】Mock 文档《流程设计》：建议按照大纲、知识补充、正文、备注、事实检查的顺序生成。',
      '【外部知识补充】可结合行业案例、实践数据和风险控制建议增强说服力。'
    ].join('\n'),
    message: 'Mock 模式：知识检索完成'
  }
}

export async function mockQueryRag(query: string) {
  await delay(620)
  const hasContent = query.length > 30
  return {
    success: true,
    answer: hasContent
      ? '通过：当前内容在 mock 检索摘要中有基本证据支撑。建议正式接入后端后继续补充真实来源页码，并人工复核关键数据。'
      : '需人工确认：输入内容较少，无法进行充分事实一致性判断。',
    message: 'Mock 模式：事实检查完成'
  }
}

export async function mockExpandContentBatch(
  items: Array<{ index: number; id?: string; outline_node: Record<string, unknown>; context?: string }>,
  context?: string
) {
  await delay(900)
  const results = await Promise.all(
    items.map(async (item) => {
      const pageContext = item.context ?? context ?? ''
      const single = await mockExpandContent(item.outline_node, pageContext)
      return {
        index: item.index,
        id: item.id,
        success: single.success,
        content: single.content,
        message: single.message
      }
    })
  )
  return {
    success: results.every((r) => r.success),
    results,
    message: `Mock 模式：批量生成完成（${results.length} 页）`,
    elapsed_sec: 0.9
  }
}

export async function mockExpandContent(outlineNode: Record<string, unknown>, context: string) {
  await delay(760)
  const title = getTitleFromNode(outlineNode)
  const isNotes = /备注|演讲/.test(title) || /演讲者|口头表达/.test(context)

  return {
    success: true,
    content: isNotes
      ? [
          `本页讲解时可以先用一句话引出“${title.replace(' 演讲备注', '')}”的背景。`,
          '随后解释为什么这一页对整体汇报重要，并结合前面检索到的资料说明依据。',
          '最后用过渡句连接到下一页，提醒听众关注后续方案或结论。'
        ].join('\n')
      : [
          `- ${title}是本页的核心讨论对象，需要先明确其背景和关键问题。`,
          '- 结合已有资料，可以从目标、方法、价值和风险四个角度展开。',
          '- 建议在幻灯片中保留 3 到 5 条要点，详细解释放入演讲备注。',
          '- 该页结论应服务于整体 PPT 的主线，避免出现无来源的扩展断言。'
        ].join('\n'),
    message: 'Mock 模式：内容生成完成'
  }
}

export async function mockReviseContent(payload: {
  outline_node: Record<string, unknown>
  current_content: string
  revision_suggestion: string
}) {
  await delay(420)
  const title = getTitleFromNode(payload.outline_node)
  const suggestion = payload.revision_suggestion.trim()
  return {
    success: true,
    content: [
      `【已按建议修订：${suggestion.slice(0, 48)}${suggestion.length > 48 ? '…' : ''}】`,
      `- ${title}：在保留原意基础上调整了表述。`,
      '- 要点更精炼，语气更适合幻灯片展示。',
      '- 未引入正文之外的新事实或数据。'
    ].join('\n'),
    message: 'Mock 模式：正文轻量修订完成'
  }
}

export async function mockGenerateNotes(payload: {
  slide_title: string
  slide_content: string
  knowledge_evidence?: string
  style_requirement?: string
}) {
  await delay(500)
  const title = payload.slide_title || '当前页面'
  const evidence = payload.knowledge_evidence?.trim()
  return {
    success: true,
    notes: evidence
      ? `讲到“${title}”这一页时，可以先用一句话承接前文，再解释页面正文中的核心判断。这里的补充说明应围绕已有证据展开，强调这些信息如何支持页面观点，同时提醒听众关注结论背后的适用边界。`
      : `讲到“${title}”这一页时，可以先概括页面想解决的问题，再把正文内容转化成更自然的口头表达。由于当前没有额外证据，备注只围绕页面已有内容展开，不补充新的事实或数字。`,
    message: 'Mock speaker notes generated'
  }
}
