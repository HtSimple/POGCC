<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-title">
        <p class="eyebrow">POGCC</p>
        <h1>PPT 大纲智能生成与内容补全系统</h1>
      </div>
      <div class="mode-tabs" aria-label="主流程切换">
        <button type="button" :class="{ active: activeMode === 'generate' }" @click="activeMode = 'generate'">
          <WandSparkles :size="18" />
          生成 PPT
        </button>
        <button type="button" :class="{ active: activeMode === 'history' }" @click="openHistoryFlow">
          <History :size="18" />
          查看历史记录
        </button>
        <button type="button" :class="{ active: activeMode === 'cost' }" @click="openCostControl">
          <Gauge :size="18" />
          API 成本控制
        </button>
      </div>
      <div class="topbar-actions">
        <span class="status-pill" :class="healthOk ? 'status-ok' : 'status-warn'">
          <Activity :size="16" />
          {{ healthLabel }}
        </span>
        <label class="select-shell">
          <span>模型</span>
          <select v-model="selectedProvider" :disabled="modelLoading" @change="handleModelSwitch">
            <option v-for="provider in availableProviders" :key="provider" :value="provider">
              {{ provider }}
            </option>
          </select>
        </label>
        <button class="icon-button" type="button" title="刷新状态" @click="loadServiceState">
          <RefreshCw :size="18" />
        </button>
      </div>
    </header>

    <main class="main-panel">
      <section v-if="activeMode === 'generate'" class="panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Linear Workflow</p>
            <h2>生成 PPT 大纲及内容补充</h2>
          </div>
          <div class="button-row">
            <button class="secondary-button" type="button" @click="startNewProject">
              <Plus :size="18" />
              新建 PPT
            </button>
            <button class="primary-button" type="button" @click="() => saveCurrentRecord()">
              <Save :size="18" />
              保存进度
            </button>
          </div>
        </div>

        <ol class="stepper">
          <li v-for="(step, index) in generationSteps" :key="step.key"
            :class="{ active: generationStepIndex === index, done: generationStepIndex > index, locked: generationStepIndex < index }">
            <span class="step-index">{{ index + 1 }}</span>
            <span>
              <strong>{{ step.label }}</strong>
              <small>{{ step.summary }}</small>
            </span>
          </li>
        </ol>

        <div class="step-body">
          <section v-if="generationStep === 'task'" class="step-section">
            <div class="section-title">
              <p class="eyebrow">Step 1</p>
              <h3>任务信息</h3>
            </div>
            <div class="form-grid">
              <label>
                <span>PPT 主题</span>
                <input v-model.trim="form.topic" type="text" placeholder="例如：人工智能在教育中的应用" />
              </label>
              <label>
                <span>使用场景</span>
                <select v-model="form.scene">
                  <option>学术汇报</option>
                  <option>商务汇报</option>
                  <option>咨询分析</option>
                  <option>课程展示</option>
                  <option>项目路演</option>
                </select>
              </label>
              <label>
                <span>目标页数</span>
                <input v-model.number="form.pageCount" min="1" max="80" type="number" />
              </label>
              <label>
                <span>受众对象</span>
                <input v-model.trim="form.audience" type="text" placeholder="例如：课程教师、项目评委、企业客户" />
              </label>
              <label class="full-row">
                <span>额外要求</span>
                <textarea v-model.trim="form.requirements" rows="5" placeholder="结构、风格、重点内容、引用偏好等" />
              </label>
            </div>
          </section>

          <section v-else-if="generationStep === 'references'" class="step-section">
            <div class="section-title with-action">
              <div>
                <p class="eyebrow">Step 2</p>
                <h3>参考资料入库</h3>
                <p class="section-hint">支持 PDF、Word、TXT、Markdown。选择文件后自动解析入库，无需手动填写路径。</p>
              </div>
              <button class="secondary-button" type="button" @click="openUploadDialog">
                <Plus :size="18" />
                添加资料
              </button>
            </div>

            <div v-if="references.length === 0" class="sub-empty">尚未添加参考资料，可跳过此步直接进入大纲生成。</div>
            <div v-else class="doc-list">
              <article v-for="doc in references" :key="doc.id" class="doc-row readonly-row">
                <div class="doc-file-meta">
                  <strong>{{ doc.filePath || '未命名文件' }}</strong>
                  <p v-if="doc.message" class="row-message">{{ doc.message }}</p>
                </div>
                <div class="row-actions inline-row-actions">
                  <span class="status-pill small" :class="docStatusClass(doc.status)">
                    {{ docStatusText(doc.status) }}
                  </span>
                  <button class="ghost-button danger" type="button" title="删除资料" @click="removeReference(doc.id)">
                    <Trash2 :size="18" />
                  </button>
                </div>
              </article>
            </div>
          </section>

          <section v-else-if="generationStep === 'outline'" class="step-section">
            <div class="section-title with-action">
              <div>
                <p class="eyebrow">Step 3</p>
                <h3>结构化大纲编辑</h3>
              </div>
              <div class="button-row">
                <button
                  class="primary-button"
                  type="button"
                  :disabled="isGenerating || !form.topic.trim()"
                  @click="handleOneClickPipelineFromOutline"
                >
                  <FileText :size="18" />
                  {{ pipelineLoading ? '流程执行中' : '一键生成正文' }}
                </button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="outlineLoading || isGenerating || !form.topic.trim()"
                  @click="handleGenerateOutline"
                >
                  <WandSparkles :size="18" />
                  {{ outlineLoading ? '生成中' : '仅生成大纲' }}
                </button>
              </div>
            </div>

            <div v-if="outlineProtocolMeta" class="protocol-strip">
              <div>
                <span>协议</span>
                <strong>{{ outlineProtocolMeta.protocolVersion }}</strong>
              </div>
              <div>
                <span>标题</span>
                <strong>{{ outlineProtocolMeta.presentationTitle }}</strong>
              </div>
              <div>
                <span>语言</span>
                <strong>{{ outlineProtocolMeta.language }}</strong>
              </div>
              <div>
                <span>目标页数</span>
                <strong>{{ outlineProtocolMeta.targetSlideCount }}</strong>
              </div>
            </div>

            <div v-if="slides.length === 0" class="empty-state">填写主题后点击「一键生成正文」，或仅生成大纲后再编辑</div>
            <div v-else class="outline-protocol-board">
              <section v-for="section in outlineSectionGroups" :key="section.key" class="outline-section-block">
                <div class="outline-section-head">
                  <div class="outline-section-head-main">
                    <p class="eyebrow">
                      {{ section.sectionId || `sec-${String(section.index + 1).padStart(2, '0')}` }}
                      · slides {{ section.start }}-{{ section.end }}
                    </p>
                    <input
                      class="outline-section-title-input"
                      :value="section.title"
                      type="text"
                      placeholder="章节标题"
                      @change="renameSectionGroup(section, ($event.target as HTMLInputElement).value)"
                    />
                  </div>
                  <div class="outline-section-actions">
                    <div class="outline-section-action-buttons">
                      <button
                        class="secondary-button outline-section-btn"
                        type="button"
                        title="在本章末尾插入一页"
                        @click="addSlideInSection(section)"
                      >
                        <Plus :size="18" />
                        本章内插入
                      </button>
                      <button
                        class="secondary-button outline-section-btn"
                        type="button"
                        title="在本章后新建章节"
                        @click="addSectionAfter(section)"
                      >
                        <Plus :size="18" />
                        本章后新章
                      </button>
                    </div>
                  </div>
                </div>

                <article v-for="slide in section.slides" :key="slide.id" class="slide-editor protocol-slide-editor">
                  <div class="slide-editor-head">
                    <div class="slide-meta-title">
                      <strong>{{ slide.protocolSlideId || `slide-${String(getSlideIndex(slide) + 1).padStart(3, '0')}` }}</strong>
                      <span>第 {{ getSlideIndex(slide) + 1 }} 页</span>
                    </div>
                    <div class="button-row compact">
                      <button class="ghost-button" type="button" title="上移" :disabled="getSlideIndex(slide) === 0"
                        @click="moveSlide(getSlideIndex(slide), -1)">
                        <ArrowUp :size="17" />
                      </button>
                      <button class="ghost-button" type="button" title="下移" :disabled="getSlideIndex(slide) === slides.length - 1"
                        @click="moveSlide(getSlideIndex(slide), 1)">
                        <ArrowDown :size="17" />
                      </button>
                      <button class="ghost-button danger" type="button" title="删除页面" @click="removeSlide(slide.id)">
                        <Trash2 :size="17" />
                      </button>
                    </div>
                  </div>
                  <div class="form-grid compact-grid">
                    <label>
                      <span>所属章节</span>
                      <select
                        :value="slide.sectionId || ''"
                        @change="handleSlideSectionChange(slide.id, ($event.target as HTMLSelectElement).value)"
                      >
                        <option v-for="option in outlineSectionCatalog" :key="option.sectionId" :value="option.sectionId">
                          {{ option.label }}
                        </option>
                        <option value="__new__">+ 新建章节…</option>
                      </select>
                    </label>
                    <label>
                      <span>页面角色</span>
                      <select v-model="slide.slideRole">
                        <option value="cover">cover</option>
                        <option value="toc">toc</option>
                        <option value="transition">transition</option>
                        <option value="content">content</option>
                        <option value="case-study">case-study</option>
                        <option value="summary">summary</option>
                        <option value="qa">qa</option>
                        <option value="appendix">appendix</option>
                      </select>
                    </label>
                    <label>
                      <span>标题</span>
                      <input v-model.trim="slide.title" type="text" />
                    </label>
                    <label>
                      <span>章节目标</span>
                      <input v-model.trim="slide.goal" type="text" />
                    </label>
                    <label class="full-row">
                      <span>要点</span>
                      <textarea :value="slide.bullets.join('\n')" rows="4"
                        @input="updateBullets(slide.id, ($event.target as HTMLTextAreaElement).value)" />
                    </label>
                  </div>
                </article>
              </section>
            </div>
          </section>

          <section v-else-if="generationStep === 'pages'" class="step-section">
            <div class="section-title with-action">
              <div>
                <p class="eyebrow">Step 4</p>
                <h3>逐页补充检索、正文、备注与事实检查</h3>
              </div>
              <label class="select-shell">
                <span>当前页</span>
                <select v-model="activeSlideId" :disabled="allContentLoading || allKnowledgeLoading">
                  <option v-for="(slide, index) in slides" :key="slide.id" :value="slide.id">
                    {{ index + 1 }}. {{ slide.title || '未命名页面' }}
                  </option>
                </select>
              </label>
            </div>
            <div v-if="!activeSlide" class="empty-state">请先完成大纲生成</div>
            <div v-else class="page-workbench">
              <div class="page-title-row">
                <div>
                  <p class="eyebrow">{{ activeSlide.sectionTitle || '未分组' }}</p>
                  <h3>{{ activeSlide.title || '未命名页面' }}</h3>
                </div>
                <span class="status-pill small" :class="factStatusClass(activeSlide.factCheckStatus)">
                  {{ factStatusText(activeSlide.factCheckStatus) }}
                </span>
              </div>

              <div class="button-grid">
                <button class="secondary-button" type="button"
                  :disabled="pageLoading.knowledge || allKnowledgeLoading || allContentLoading"
                  @click="fillKnowledge(activeSlide)">
                  <Search :size="18" />
                  {{ pageLoading.knowledge ? '检索中' : '补充检索' }}
                </button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="pageLoading.content || allContentLoading || allKnowledgeLoading"
                  @click="fillContent(activeSlide)"
                >
                  <FileText :size="18" />
                  {{ pageLoading.content ? '生成中' : '生成正文' }}
                </button>
                <button class="secondary-button" type="button" :disabled="pageLoading.notes || allContentLoading || allKnowledgeLoading"
                  @click="fillNotes(activeSlide)">
                  <NotebookPen :size="18" />
                  {{ pageLoading.notes ? '生成中' : '生成备注' }}
                </button>
                <button class="secondary-button" type="button" :disabled="pageLoading.fact || allContentLoading || allKnowledgeLoading"
                  @click="checkFacts(activeSlide)">
                  <CheckCircle2 :size="18" />
                  {{ pageLoading.fact ? '检查中' : '事实检查' }}
                </button>
              </div>

              <p v-if="allKnowledgeLoading || allContentLoading" class="batch-hint">
                <template v-if="allKnowledgeLoading">正在一键检索，请稍候…</template>
                <template v-else>正在一键生成正文，请稍候…</template>
              </p>

              <div class="button-grid batch-actions">
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="allKnowledgeLoading || allContentLoading || pageLoading.knowledge || slides.length === 0"
                  @click="fillAllKnowledge"
                >
                  <Search :size="18" />
                  {{ allKnowledgeLoading ? '一键检索中' : '一键检索' }}
                </button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="allContentLoading || allKnowledgeLoading || pageLoading.content || slides.length === 0"
                  @click="fillAllContent"
                >
                  <Files :size="18" />
                  {{ allContentLoading ? '一键生成中' : '一键生成' }}
                </button>
              </div>

              <div class="page-content-layout">
                <label class="content-block content-block-primary">
                  <div class="field-header">
                    <span class="field-label">正文内容</span>
                    <button
                      class="secondary-button field-inline-action"
                      type="button"
                      :disabled="allContentLoading || allKnowledgeLoading || pageLoading.content || !activeSlide.content.trim()"
                      @click="openReviseDialog"
                    >
                      <PencilLine :size="15" />
                      按建议修改
                    </button>
                  </div>
                  <textarea v-model="activeSlide.content" rows="10" />
                </label>
                <div class="content-grid content-grid-secondary">
                  <label>
                    <span>检索摘要与来源</span>
                    <textarea v-model="activeSlide.knowledge" rows="8" />
                  </label>
                  <label>
                    <span>演讲备注</span>
                    <textarea v-model="activeSlide.notes" rows="8" />
                  </label>
                  <label>
                    <span>事实检查结果</span>
                    <textarea v-model="activeSlide.factCheckMessage" rows="8" />
                  </label>
                </div>
              </div>
            </div>
          </section>

          <section v-else class="step-section">
            <div class="section-title with-action">
              <div>
                <p class="eyebrow">Step 5</p>
                <h3>最终 Markdown 文本</h3>
              </div>
              <div class="button-row">
                <button class="secondary-button" type="button" @click="copyMarkdown">
                  <Copy :size="18" />
                  复制
                </button>
                <button class="primary-button" type="button" @click="downloadMarkdown">
                  <Download :size="18" />
                  下载
                </button>
              </div>
            </div>
            <textarea class="markdown-preview" :value="markdownText" readonly />
          </section>
        </div>

        <div class="flow-actions">
          <button class="secondary-button" type="button" :disabled="generationStepIndex === 0" @click="goPreviousStep">
            上一步
          </button>
          <span class="flow-hint">{{ currentStepHint }}</span>
          <button class="primary-button" type="button" :disabled="!canGoNext" @click="goNextStep">
            {{ nextStepLabel }}
          </button>
        </div>
      </section>

      <section v-else-if="activeMode === 'history'" class="panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">History Workflow</p>
            <h2>查看历史记录</h2>
          </div>
          <button class="secondary-button" type="button" @click="openHistoryFlow">
            <RefreshCw :size="18" />
            刷新
          </button>
        </div>

        <div v-if="historyRecords.length === 0" class="empty-state">暂无历史记录</div>
        <div v-else-if="!selectedHistory" class="history-list">
          <article v-for="record in historyRecords" :key="record.id" class="history-row">
            <div>
              <h3>{{ record.title }}</h3>
              <p>{{ formatDate(record.updatedAt) }} · {{ record.slides.length }} 页 · {{ record.references.length }} 份资料
              </p>
            </div>
            <div class="button-row">
              <button class="secondary-button" type="button" @click="selectedHistoryId = record.id">
                <Eye :size="18" />
                查看详情
              </button>
              <button class="secondary-button" type="button" @click="downloadMarkdownForRecord(record)">
                <Download :size="18" />
                下载 MD
              </button>
              <button class="secondary-button" type="button" @click="restoreRecord(record)">
                <RotateCcw :size="18" />
                恢复编辑
              </button>
              <button class="ghost-button danger" type="button" title="删除记录" @click="removeHistoryRecord(record.id)">
                <Trash2 :size="18" />
              </button>
            </div>
          </article>
        </div>

        <div v-else class="history-detail">
          <div class="detail-toolbar">
            <button class="secondary-button" type="button" @click="selectedHistoryId = null">返回列表</button>
            <div class="button-row">
              <button class="secondary-button" type="button" @click="downloadMarkdownForRecord(selectedHistory)">
                <Download :size="18" />
                下载 MD
              </button>
              <button class="primary-button" type="button" @click="restoreRecord(selectedHistory)">
                <RotateCcw :size="18" />
                恢复到生成流程
              </button>
            </div>
          </div>

          <section class="detail-section">
            <h3>任务信息</h3>
            <dl class="detail-grid">
              <div>
                <dt>主题</dt>
                <dd>{{ selectedHistory.form.topic || '未填写' }}</dd>
              </div>
              <div>
                <dt>场景</dt>
                <dd>{{ selectedHistory.form.scene }}</dd>
              </div>
              <div>
                <dt>目标页数</dt>
                <dd>{{ selectedHistory.form.pageCount }}</dd>
              </div>
              <div>
                <dt>受众</dt>
                <dd>{{ selectedHistory.form.audience || '未填写' }}</dd>
              </div>
              <div class="wide">
                <dt>额外要求</dt>
                <dd>{{ selectedHistory.form.requirements || '无' }}</dd>
              </div>
            </dl>
          </section>

          <section class="detail-section">
            <h3>资料导入</h3>
            <div v-if="selectedHistory.references.length === 0" class="sub-empty">无参考资料记录</div>
            <div v-else class="doc-list">
              <article v-for="doc in selectedHistory.references" :key="doc.id" class="doc-row readonly-row">
                <strong>{{ doc.filePath || '未填写路径' }}</strong>
                <span class="status-pill small" :class="docStatusClass(doc.status)">{{ docStatusText(doc.status)
                }}</span>
                <p v-if="doc.message" class="row-message">{{ doc.message }}</p>
              </article>
            </div>
          </section>

          <section class="detail-section">
            <h3>大纲生成与修改</h3>
            <div v-if="selectedHistory.slides.length === 0" class="sub-empty">无大纲记录</div>
            <ol v-else class="outline-summary">
              <li v-for="slide in selectedHistory.slides" :key="slide.id">
                <strong>{{ slide.title || '未命名页面' }}</strong>
                <span>{{ slide.sectionTitle || '未分组' }}</span>
                <p>{{ slide.goal || '未填写核心目标' }}</p>
                <ul>
                  <li v-for="bullet in slide.bullets" :key="bullet">{{ bullet }}</li>
                </ul>
              </li>
            </ol>
          </section>

          <section class="detail-section">
            <h3>逐页内容补充</h3>
            <details v-for="(slide, index) in selectedHistory.slides" :key="slide.id" class="page-detail">
              <summary class="page-summary-row">
                <div>
                  <p class="eyebrow">第 {{ index + 1 }} 页 · {{ slide.sectionTitle || '未分组' }}</p>
                  <h3>{{ slide.title || '未命名页面' }}</h3>
                </div>
                <span class="status-pill small" :class="factStatusClass(slide.factCheckStatus)">
                  {{ factStatusText(slide.factCheckStatus) }}
                </span>
              </summary>
              <div class="history-step-grid">
                <div><strong>检索摘要与来源</strong>
                  <p>{{ slide.knowledge || '未补充' }}</p>
                </div>
                <div><strong>正文内容</strong>
                  <p>{{ slide.content || '未生成' }}</p>
                </div>
                <div><strong>演讲备注</strong>
                  <p>{{ slide.notes || '未生成' }}</p>
                </div>
                <div><strong>事实检查</strong>
                  <p>{{ slide.factCheckMessage || '未检查' }}</p>
                </div>
              </div>
            </details>
          </section>

          <section class="detail-section">
            <h3>最终 Markdown</h3>
            <textarea class="markdown-preview compact-preview"
              :value="selectedHistory.markdown || buildMarkdownForRecord(selectedHistory)" readonly />
          </section>
        </div>
      </section>

      <section v-if="activeMode === 'cost'" class="panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">API Usage & Quotas</p>
            <h2>API 成本控制</h2>
          </div>
          <button class="secondary-button" type="button" :disabled="costLoading" @click="loadApiUsage">
            <RefreshCw :size="18" />
            刷新用量
          </button>
        </div>

        <div v-if="costLoading && !apiUsage" class="empty-state">正在读取 API 用量...</div>
        <div v-else-if="apiUsage && selectedApiUsage" class="cost-layout">
          <nav class="cost-api-list" aria-label="API 列表">
            <button
              v-for="(usage, provider) in apiUsage.providers"
              :key="provider"
              type="button"
              :class="{ active: selectedCostProvider === provider }"
              @click="selectedCostProvider = provider"
            >
              <span>
                <strong>{{ providerLabel(provider) }}</strong>
                <small>{{ usage.calls }} 次调用 · {{ formatNumber(usage.total_tokens) }} Token</small>
              </span>
              <span class="status-dot" :class="{ warning: usage.blocked_calls > 0 }" aria-hidden="true"></span>
            </button>
          </nav>

          <div class="cost-api-detail">
          <section class="cost-provider">
            <div class="cost-provider-head">
              <div>
                <p class="eyebrow">{{ selectedCostProvider }}</p>
                <h3>{{ providerLabel(selectedCostProvider) }}</h3>
              </div>
              <span class="status-pill small" :class="selectedApiUsage.blocked_calls ? 'status-warn' : 'status-ok'">
                {{ selectedApiUsage.blocked_calls ? `已拦截 ${selectedApiUsage.blocked_calls} 次` : '额度正常' }}
              </span>
            </div>
            <div class="cost-metrics">
              <div><span>调用次数</span><strong>{{ selectedApiUsage.calls }}</strong><small>/ {{ limitText(selectedApiUsage.call_limit) }}</small></div>
              <div><span>累计 Token</span><strong>{{ formatNumber(selectedApiUsage.total_tokens) }}</strong><small>/ {{ limitText(selectedApiUsage.token_limit) }}</small></div>
              <div><span>预估成本</span><strong>{{ formatCost(selectedApiUsage.estimated_cost, selectedApiUsage.currency) }}</strong><small>/ {{ costLimitText(selectedApiUsage.cost_limit, selectedApiUsage.currency) }}</small></div>
              <div><span>平均耗时</span><strong>{{ selectedApiUsage.average_duration_ms }} ms</strong><small>失败 {{ selectedApiUsage.failed_calls }} 次</small></div>
            </div>
            <div class="quota-form">
              <label><span>调用次数上限</span><input v-model.number="quotaDrafts[selectedCostProvider].call_limit" min="1" type="number" placeholder="不限" /></label>
              <label><span>Token 上限</span><input v-model.number="quotaDrafts[selectedCostProvider].token_limit" min="1" type="number" placeholder="不限" /></label>
              <label><span>成本上限（{{ selectedApiUsage.currency }}）</span><input v-model.number="quotaDrafts[selectedCostProvider].cost_limit" min="0.000001" step="0.000001" type="number" placeholder="不限" /></label>
            </div>
            <div class="button-row cost-action-row">
              <button class="primary-button" type="button" :disabled="costLoading" @click="saveProviderLimits(selectedCostProvider)">
                <Save :size="18" />保存限额
              </button>
              <button class="secondary-button" type="button" :disabled="costLoading" @click="clearProviderLimits(selectedCostProvider)">
                清除限额
              </button>
              <button class="ghost-button danger" type="button" :disabled="costLoading" @click="resetProviderUsage(selectedCostProvider)">
                <RotateCcw :size="18" />清零用量
              </button>
            </div>
          </section>

          <section class="recent-api-calls">
            <div class="recent-api-head">
              <h3>最近调用</h3>
              <span>共 {{ allSelectedApiCalls.length }} 条</span>
            </div>
            <div v-if="selectedApiCalls.length === 0" class="sub-empty">暂无 API 调用记录</div>
            <div v-else class="api-call-table-wrap">
              <table class="api-call-table">
                <thead><tr><th>API / 模型</th><th>状态</th><th>Token</th><th>Token 来源</th><th>耗时</th><th>重试</th><th>预估成本</th><th>时间</th></tr></thead>
                <tbody>
                  <tr v-for="(call, index) in selectedApiCalls" :key="`${call.called_at}-${index}`">
                    <td>{{ providerLabel(call.provider) }}<small v-if="call.model"><br />{{ call.model }}</small></td>
                    <td>{{ call.success ? '成功' : '失败' }}</td>
                    <td>{{ formatNumber(call.input_tokens + call.output_tokens) }}</td>
                    <td>{{ call.token_source === 'actual' ? 'API 实际值' : '估算值' }}</td>
                    <td>{{ call.duration_ms }} ms</td>
                    <td>{{ call.retry_count }}</td>
                    <td>{{ formatCost(call.estimated_cost, call.currency) }}</td>
                    <td>{{ formatCallTime(call.called_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="apiCallPageCount > 1" class="api-pagination">
              <button class="secondary-button" type="button" :disabled="apiCallPage <= 1" @click="apiCallPage -= 1">
                <ArrowLeft :size="17" />上一页
              </button>
              <span>第 {{ apiCallPage }} / {{ apiCallPageCount }} 页</span>
              <button class="secondary-button" type="button" :disabled="apiCallPage >= apiCallPageCount" @click="apiCallPage += 1">
                下一页<ArrowRight :size="17" />
              </button>
            </div>
          </section>

          <section class="usage-charts">
            <div class="usage-charts-head">
              <div>
                <p class="eyebrow">Last 15 Days</p>
                <h3>近十五日用量</h3>
              </div>
              <span>{{ providerLabel(selectedCostProvider) }}</span>
            </div>
            <div class="usage-chart-grid">
              <article v-for="chart in usageCharts" :key="chart.key" class="usage-chart">
                <div class="usage-chart-title">
                  <span>{{ chart.label }}</span>
                  <strong>{{ chart.totalLabel }}</strong>
                </div>
                <div class="bar-chart" :aria-label="chart.label">
                  <div v-for="item in chart.items" :key="item.date" class="bar-column">
                    <div class="bar-track">
                      <div class="bar-value" :style="{ height: `${item.height}%` }"></div>
                    </div>
                    <small>{{ item.shortDate }}</small>
                    <span class="bar-tooltip">
                      <strong>{{ item.date }}</strong>
                      <span>{{ item.label }}</span>
                    </span>
                  </div>
                </div>
              </article>
            </div>
          </section>
          </div>
        </div>
      </section>
    </main>

    <div v-if="isGenerating" class="generating-overlay" role="status" aria-live="polite" aria-busy="true">
      <div class="generating-overlay__panel">
        <div class="generating-spinner" aria-hidden="true"></div>
        <p>{{ generatingLabel }}</p>
      </div>
    </div>

    <div
      v-if="uploadDialogOpen"
      class="dialog-overlay"
      role="presentation"
      @click.self="closeUploadDialog"
    >
      <div class="dialog-panel" role="dialog" aria-modal="true" aria-labelledby="upload-dialog-title">
        <h3 id="upload-dialog-title" class="dialog-panel__title">选择参考资料</h3>
        <p class="dialog-hint">从本机选择 PDF、Word、TXT 或 Markdown 文件，确认后将上传并写入本地知识库。</p>
        <input
          ref="uploadFileInputRef"
          class="file-input-hidden"
          type="file"
          accept=".pdf,.doc,.docx,.txt,.md,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
          @change="handleUploadFileChange"
        />
        <button
          class="file-picker"
          type="button"
          :disabled="uploadSubmitting"
          @click="triggerUploadFilePicker"
        >
          <Upload :size="20" />
          <span>{{ pendingUploadFile ? '重新选择文件' : '点击选择文件' }}</span>
        </button>
        <p v-if="pendingUploadFile" class="file-picker__name">{{ pendingUploadFile.name }}</p>
        <p v-if="uploadDialogError" class="dialog-error">{{ uploadDialogError }}</p>
        <div class="dialog-actions">
          <button class="secondary-button" type="button" :disabled="uploadSubmitting" @click="closeUploadDialog">
            取消
          </button>
          <button
            class="primary-button"
            type="button"
            :disabled="uploadSubmitting || !pendingUploadFile"
            @click="submitUploadReference"
          >
            {{ uploadSubmitting ? '入库中…' : '确认入库' }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="reviseDialogOpen"
      class="dialog-overlay"
      role="presentation"
      @click.self="closeReviseDialog"
    >
      <div class="dialog-panel" role="dialog" aria-modal="true" aria-labelledby="revise-dialog-title">
        <h3 id="revise-dialog-title" class="dialog-panel__title">修改正文</h3>
        <p class="dialog-hint">说明修改方向即可。系统将依据当前正文、页面标题与要点进行轻量修订，不附带检索摘要，速度更快。</p>
        <label class="dialog-field">
          <span>当前正文</span>
          <textarea :value="activeSlide?.content || ''" rows="6" readonly />
        </label>
        <label class="dialog-field">
          <span>修改建议</span>
          <textarea
            v-model="reviseSuggestion"
            rows="5"
            placeholder="例如：要点太多请压缩为 3 条；语气更口语化；删除无来源的数据；加强与本页大纲目标的对应。"
            :disabled="reviseSubmitting"
          />
        </label>
        <div class="dialog-actions">
          <button class="secondary-button" type="button" :disabled="reviseSubmitting" @click="closeReviseDialog">
            取消
          </button>
          <button class="primary-button" type="button" :disabled="reviseSubmitting" @click="submitReviseContent">
            {{ reviseSubmitting ? '修订中…' : '应用修订' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast" :class="toast.type">{{ toast.message }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Activity,
  ArrowLeft,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  Files,
  FileText,
  Gauge,
  History,
  NotebookPen,
  PencilLine,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Trash2,
  Upload,
  WandSparkles
} from 'lucide-vue-next'
import {
  expandContent,
  expandContentBatch,
  formatApiError,
  generateNotes,
  generateOutline,
  getApiUsage,
  getApiBaseUrl,
  getHealth,
  getModelInfo,
  isUsingMockApi,
  queryRag,
  reviseContent,
  searchKnowledge,
  searchKnowledgeBatch,
  switchModel,
  resetApiUsage,
  updateApiLimits,
  uploadDocumentFile
} from './api'
import { deleteRecord, loadHistory, upsertRecord } from './storage'
import type {
  FactCheckStatus,
  NarrativeOutline,
  OutlineResponse,
  PageContentProtocol,
  ProjectForm,
  ProjectRecord,
  ReferenceDoc,
  ReferenceStatus,
  SlidePage,
  ApiLimitUpdate,
  ApiUsageSummary
} from './types'

type AppMode = 'generate' | 'history' | 'cost'
type GenerationStep = 'task' | 'references' | 'outline' | 'pages' | 'markdown'

type OutlineSectionGroup = {
  key: string
  index: number
  sectionId: string
  title: string
  start: number
  end: number
  slides: SlidePage[]
}

const NEW_SECTION_OPTION = '__new__'

const generationSteps: Array<{ key: GenerationStep; label: string; summary: string }> = [
  { key: 'task', label: '任务信息', summary: '填写主题与要求' },
  { key: 'references', label: '参考资料', summary: '选择文件入库与状态反馈' },
  { key: 'outline', label: '大纲编辑', summary: '生成、调整、增删页面' },
  { key: 'pages', label: '内容补充', summary: '检索、正文、备注、检查' },
  { key: 'markdown', label: '最终文本', summary: '预览、复制、下载' }
]

const form = reactive<ProjectForm>({
  topic: '',
  scene: '学术汇报',
  pageCount: 10,
  audience: '',
  requirements: ''
})

const activeMode = ref<AppMode>('generate')
const generationStepIndex = ref(0)
const references = ref<ReferenceDoc[]>([])
const slides = ref<SlidePage[]>([])
const activeSlideId = ref('')
const healthOk = ref(false)
const healthLabel = ref(`后端未连接 · ${getApiBaseUrl()}`)
const availableProviders = ref<string[]>([])
const selectedProvider = ref('')
const modelLoading = ref(false)
const outlineLoading = ref(false)
const outlineProtocolMeta = ref<Pick<NarrativeOutline, 'protocolVersion' | 'language' | 'presentationTitle' | 'targetSlideCount'> | null>(null)
const historyRecords = ref<ProjectRecord[]>(loadHistory())
const selectedHistoryId = ref<string | null>(null)
const currentRecordId = ref(createId())
const createdAt = ref(new Date().toISOString())
const toast = ref<{ message: string; type: 'success' | 'warning' | 'error' } | null>(null)
const pageLoading = reactive({
  knowledge: false,
  content: false,
  notes: false,
  fact: false
})
const allContentLoading = ref(false)
const allKnowledgeLoading = ref(false)
const pipelineLoading = ref(false)
const uploadDialogOpen = ref(false)
const uploadFileInputRef = ref<HTMLInputElement | null>(null)
const pendingUploadFile = ref<File | null>(null)
const uploadSubmitting = ref(false)
const uploadDialogError = ref('')

const reviseDialogOpen = ref(false)
const reviseSuggestion = ref('')
const reviseSubmitting = ref(false)
const costLoading = ref(false)
const apiUsage = ref<ApiUsageSummary | null>(null)
const quotaDrafts = reactive<Record<string, ApiLimitUpdate>>({})
const selectedCostProvider = ref('deepseek')
const apiCallPage = ref(1)
const API_CALL_PAGE_SIZE = 10
const selectedApiUsage = computed(() => apiUsage.value?.providers[selectedCostProvider.value] ?? null)
const allSelectedApiCalls = computed(() =>
  (apiUsage.value?.recent_calls ?? [])
    .filter((call) => call.provider === selectedCostProvider.value)
    .slice()
    .reverse()
)
const apiCallPageCount = computed(() => Math.max(1, Math.ceil(allSelectedApiCalls.value.length / API_CALL_PAGE_SIZE)))
const selectedApiCalls = computed(() => {
  const start = (apiCallPage.value - 1) * API_CALL_PAGE_SIZE
  return allSelectedApiCalls.value.slice(start, start + API_CALL_PAGE_SIZE)
})
const usageCharts = computed(() => {
  const daily = apiUsage.value?.daily_usage?.[selectedCostProvider.value] ?? {}
  const currency = selectedApiUsage.value?.currency ?? 'CNY'
  const days = Array.from({ length: 15 }, (_, offset) => {
    const date = new Date()
    date.setDate(date.getDate() - (14 - offset))
    const key = date.toLocaleDateString('sv-SE')
    return {
      date: key,
      shortDate: `${date.getMonth() + 1}-${date.getDate()}`,
      usage: daily[key]
    }
  })
  const makeChart = (key: string, label: string, getValue: (item: typeof days[number]) => number, format: (value: number) => string) => {
    const values = days.map(getValue)
    const max = Math.max(...values, 1)
    return {
      key,
      label,
      totalLabel: format(values.reduce((sum, value) => sum + value, 0)),
      items: days.map((item, index) => ({
        date: item.date,
        shortDate: item.shortDate,
        label: format(values[index]),
        height: values[index] === 0 ? 0 : Math.max(4, (values[index] / max) * 100)
      }))
    }
  }
  return [
    makeChart('tokens', 'Token 用量', (item) => item.usage?.total_tokens ?? 0, formatNumber),
    makeChart('calls', 'API 调用次数', (item) => item.usage?.calls ?? 0, formatNumber),
    makeChart('cost', '消费金额', (item) => item.usage?.estimated_cost ?? 0, (value) => formatCost(value, currency))
  ]
})

watch(selectedCostProvider, () => {
  apiCallPage.value = 1
})

watch(apiCallPageCount, (count) => {
  apiCallPage.value = Math.min(apiCallPage.value, count)
})

const isGenerating = computed(
  () =>
    outlineLoading.value ||
    pipelineLoading.value ||
    allContentLoading.value ||
    allKnowledgeLoading.value ||
    pageLoading.knowledge ||
    pageLoading.content ||
    pageLoading.notes ||
    pageLoading.fact ||
    reviseSubmitting.value
)

const generatingLabel = computed(() => {
  if (pipelineLoading.value && outlineLoading.value) return '正在生成大纲…'
  if (outlineLoading.value) return '正在生成大纲，请稍候…'
  if (pipelineLoading.value && allKnowledgeLoading.value) return '正在一键检索全部页面…'
  if (pipelineLoading.value && allContentLoading.value) return '正在一键生成全部正文…'
  if (pipelineLoading.value) return '正在执行一键生成流程…'
  if (allKnowledgeLoading.value) return '正在一键检索…'
  if (allContentLoading.value) return '正在一键生成…'
  if (pageLoading.knowledge) return '正在补充检索…'
  if (pageLoading.content && reviseSubmitting.value) return '正在按建议修改正文…'
  if (pageLoading.content) return '正在生成正文…'
  if (pageLoading.notes) return '正在生成演讲备注…'
  if (pageLoading.fact) return '正在进行事实检查…'
  return '正在生成，请稍候…'
})

const generationStep = computed(() => generationSteps[generationStepIndex.value].key)
const activeSlide = computed(() => slides.value.find((slide) => slide.id === activeSlideId.value) ?? slides.value[0])
const selectedHistory = computed(() => historyRecords.value.find((record) => record.id === selectedHistoryId.value) ?? null)
const outlineSectionGroups = computed(() => {
  const groups: OutlineSectionGroup[] = []
  let current: OutlineSectionGroup | null = null

  slides.value.forEach((slide, index) => {
    const sectionId = slide.sectionId || `sec-${String((current?.index ?? -1) + 2).padStart(2, '0')}`
    const title = slide.sectionTitle || '未命名章节'

    if (!current || current.sectionId !== sectionId) {
      current = {
        key: `${sectionId}-${groups.length}`,
        index: groups.length,
        sectionId,
        title,
        start: index + 1,
        end: index + 1,
        slides: [slide]
      }
      groups.push(current)
      return
    }

    current.end = index + 1
    current.slides.push(slide)
  })

  return groups
})

const outlineSectionCatalog = computed(() =>
  outlineSectionGroups.value.map((section) => ({
    sectionId: section.sectionId,
    sectionTitle: section.title,
    goal: section.slides[0]?.goal || '',
    label: `${section.sectionId} · ${section.title || '未命名章节'}`
  }))
)

const requirementsText = computed(() => {
  const lines = [
    `使用场景：${form.scene}`,
    `目标页数：${form.pageCount}`,
    form.audience ? `目标受众：${form.audience}（这是听众/观看者，不是汇报人身份）` : '',
    '不要根据目标受众推断汇报人身份；除非用户明确提供汇报人，否则不要生成“汇报人”“我是...”等身份表述。',
    form.requirements ? `额外要求：${form.requirements}` : ''
  ]
  return lines.filter(Boolean).join('\n')
})

const markdownText = computed(() => buildMarkdown())

const canGoNext = computed(() => {
  if (generationStep.value === 'task') {
    return Boolean(form.topic.trim()) && Number(form.pageCount) > 0
  }
  if (generationStep.value === 'references') {
    return references.value.every((doc) => doc.status !== 'parsing')
  }
  if (generationStep.value === 'outline') {
    return slides.value.length > 0 && slides.value.every((slide) => Boolean(slide.title.trim()))
  }
  if (generationStep.value === 'pages') {
    return slides.value.length > 0 && slides.value.every((slide) => Boolean(slide.content.trim()))
  }
  return false
})

const nextStepLabel = computed(() => {
  const labels: Record<GenerationStep, string> = {
    task: '下一步：参考资料',
    references: '下一步：生成大纲',
    outline: '下一步：内容补充',
    pages: '下一步：最终文本',
    markdown: '流程已完成'
  }
  return labels[generationStep.value]
})

const currentStepHint = computed(() => {
  if (generationStep.value === 'references') {
    const parsingCount = references.value.filter((doc) => doc.status === 'parsing').length
    if (parsingCount > 0) {
      return `还有 ${parsingCount} 份资料正在入库，请稍候。`
    }
    return '没有资料时可以直接继续；已入库的资料会用于后续检索。'
  }
  const hints: Record<GenerationStep, string> = {
    task: '填写主题后才能进入资料环节。',
    references: '资料正在处理时请稍候，处理完成后可继续。',
    outline: '必须先生成或新增至少一页大纲，才能进入逐页内容补充。',
    pages: '每一页至少需要有正文内容，才能进入最终文本。',
    markdown: '最终文本已根据当前任务自动组装。'
  }
  return hints[generationStep.value]
})

watch(
  slides,
  () => {
    if (!slides.value.some((slide) => slide.id === activeSlideId.value)) {
      activeSlideId.value = slides.value[0]?.id ?? ''
    }
  },
  { deep: true }
)

onMounted(() => {
  loadServiceState()
})

async function loadServiceState() {
  try {
    const [health, model] = await Promise.all([getHealth(), getModelInfo()])
    healthOk.value = health.status === 'healthy'
    healthLabel.value = isUsingMockApi() ? `Mock 数据模式 · ${health.status}` : `${health.status} · v${health.version}`
    availableProviders.value = model.available_providers
    selectedProvider.value = model.current_provider
  } catch (error) {
    healthOk.value = false
    healthLabel.value = `后端未连接 · ${getApiBaseUrl()}`
    showToast(getErrorMessage(error), 'warning')
  }
}

async function handleModelSwitch() {
  if (!selectedProvider.value) {
    return
  }
  modelLoading.value = true
  try {
    const result = await switchModel(selectedProvider.value)
    selectedProvider.value = result.current_provider
    showToast(result.message || '模型已切换', result.success ? 'success' : 'warning')
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    modelLoading.value = false
  }
}

function openHistoryFlow() {
  activeMode.value = 'history'
  historyRecords.value = loadHistory()
  if (selectedHistoryId.value && !historyRecords.value.some((record) => record.id === selectedHistoryId.value)) {
    selectedHistoryId.value = null
  }
}

async function openCostControl() {
  activeMode.value = 'cost'
  await loadApiUsage()
}

async function loadApiUsage() {
  costLoading.value = true
  try {
    apiUsage.value = await getApiUsage()
    for (const [provider, usage] of Object.entries(apiUsage.value.providers)) {
      quotaDrafts[provider] = {
        call_limit: usage.call_limit,
        token_limit: usage.token_limit,
        cost_limit: usage.cost_limit
      }
    }
    if (!apiUsage.value.providers[selectedCostProvider.value]) {
      selectedCostProvider.value = Object.keys(apiUsage.value.providers)[0] || ''
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    costLoading.value = false
  }
}

async function saveProviderLimits(provider: string) {
  costLoading.value = true
  try {
    const result = await updateApiLimits(provider, quotaDrafts[provider])
    showToast(result.message || `${providerLabel(provider)} 限额已保存`, result.success ? 'success' : 'warning')
    await loadApiUsage()
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
    costLoading.value = false
  }
}

async function clearProviderLimits(provider: string) {
  quotaDrafts[provider] = { call_limit: null, token_limit: null, cost_limit: null }
  await saveProviderLimits(provider)
}

async function resetProviderUsage(provider: string) {
  costLoading.value = true
  try {
    await resetApiUsage(provider)
    showToast(`${providerLabel(provider)} 用量已清零`, 'success')
    await loadApiUsage()
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
    costLoading.value = false
  }
}

function providerLabel(provider: string) {
  return ({ deepseek: 'DeepSeek 大模型', qwen: '千问大模型' } as Record<string, string>)[provider] || provider
}

function limitText(value: number | null) {
  return value === null ? '不限' : formatNumber(value)
}

function costLimitText(value: number | null, currency: string) {
  return value === null ? '不限' : formatCost(value, currency)
}

function formatCost(value: number, currency: string) {
  return `${currency === 'CNY' ? '¥' : '$'}${value.toFixed(6)}`
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatCallTime(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

function goPreviousStep() {
  if (generationStepIndex.value > 0) {
    generationStepIndex.value -= 1
  }
}

function goNextStep() {
  if (!canGoNext.value || generationStepIndex.value >= generationSteps.length - 1) {
    showToast(currentStepHint.value, 'warning')
    return
  }
  generationStepIndex.value += 1
  if (generationStep.value === 'markdown') {
    saveCurrentRecord(false)
  }
}

function openUploadDialog() {
  uploadDialogError.value = ''
  pendingUploadFile.value = null
  uploadDialogOpen.value = true
  if (uploadFileInputRef.value) {
    uploadFileInputRef.value.value = ''
  }
}

function closeUploadDialog() {
  if (uploadSubmitting.value) {
    return
  }
  uploadDialogOpen.value = false
  uploadDialogError.value = ''
  pendingUploadFile.value = null
  if (uploadFileInputRef.value) {
    uploadFileInputRef.value.value = ''
  }
}

function triggerUploadFilePicker() {
  uploadFileInputRef.value?.click()
}

function handleUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  pendingUploadFile.value = input.files?.[0] ?? null
  uploadDialogError.value = ''
}

function patchReferenceDoc(docId: string, patch: Partial<ReferenceDoc>) {
  references.value = references.value.map((item) => (item.id === docId ? { ...item, ...patch } : item))
}

async function submitUploadReference() {
  if (uploadSubmitting.value) {
    return
  }
  const file = pendingUploadFile.value
  if (!file) {
    uploadDialogError.value = '请先选择文件'
    return
  }

  uploadSubmitting.value = true
  uploadDialogError.value = ''

  const docId = createId()
  references.value.push({
    id: docId,
    filePath: file.name,
    status: 'parsing',
    message: '解析中'
  })
  uploadDialogOpen.value = false
  pendingUploadFile.value = null
  if (uploadFileInputRef.value) {
    uploadFileInputRef.value.value = ''
  }

  try {
    const result = await uploadDocumentFile(file)
    patchReferenceDoc(docId, {
      status: result.success ? 'stored' : 'failed',
      docId: result.doc_id,
      message: result.message || (result.success ? '已入库' : '解析失败')
    })
    if (result.success) {
      showToast(`已入库：${file.name}`, 'success')
    } else {
      showToast(result.message || '入库失败', 'error')
    }
  } catch (error) {
    const message = getErrorMessage(error)
    patchReferenceDoc(docId, {
      status: 'failed',
      message
    })
    showToast(message, 'error')
  } finally {
    uploadSubmitting.value = false
  }
}

function removeReference(docId: string) {
  references.value = references.value.filter((doc) => doc.id !== docId)
}

async function executeGenerateOutline(): Promise<{ ok: boolean; message?: string }> {
  const result = await generateOutline(form.topic, requirementsText.value)
  if (!result.success) {
    return { ok: false, message: result.message }
  }
  slides.value = normalizeOutline(result.outline)
  normalizeOutlineSlides()
  activeSlideId.value = slides.value[0]?.id ?? ''
  return {
    ok: slides.value.length > 0 && slides.value.every((slide) => Boolean(slide.title.trim())),
    message: result.message
  }
}

async function handleGenerateOutline() {
  outlineLoading.value = true
  try {
    const outcome = await executeGenerateOutline()
    if (!outcome.ok) {
      showToast(outcome.message || '大纲生成失败', 'error')
      return
    }
    showToast('大纲生成成功，可以检查并修改页面结构', 'success')
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    outlineLoading.value = false
  }
}

function normalizeOutline(outline: OutlineResponse) {
  if (isNarrativeOutline(outline)) {
    outlineProtocolMeta.value = {
      protocolVersion: outline.protocolVersion,
      language: outline.language,
      presentationTitle: outline.presentationTitle,
      targetSlideCount: outline.targetSlideCount
    }
    const pages = outline.sections.flatMap((section) =>
      section.slides.map((slide) =>
        createSlide({
          protocolSlideId: slide.slideId,
          slideNumber: slide.slideNumber,
          slideRole: slide.slideRole,
          sectionId: section.sectionId,
          slideRange: section.slideRange,
          sectionTitle: section.sectionTitle,
          title: cleanTitle(slide.slideTitle),
          goal: section.sectionObjective,
          bullets: slide.keyPoints.map((point) => String(point).trim()).filter(Boolean),
          notes: slide.notes || ''
        })
      )
    )
    return pages.length ? pages : [createSlide({ sectionTitle: outline.presentationTitle, title: outline.presentationTitle })]
  }

  outlineProtocolMeta.value = null
  const pages: SlidePage[] = []
  outline.sections?.forEach((section) => {
    const sectionTitle = cleanTitle(section.title || '')
    const subsections = section.subsections?.length ? section.subsections : [sectionTitle]
    subsections.forEach((subsection) => {
      if (typeof subsection === 'string') {
        const title = cleanTitle(subsection)
        pages.push(createSlide({
          sectionTitle,
          title,
          goal: `围绕“${title}”说明核心信息`,
          bullets: title ? [title] : []
        }))
        return
      }
      const title = cleanTitle(subsection.title || '')
      const goal = (subsection.goal || '').trim() || `围绕“${title}”说明核心信息`
      const bullets = (subsection.bullets || []).map((b) => String(b).trim()).filter(Boolean)
      pages.push(createSlide({
        sectionTitle,
        title,
        goal,
        bullets: bullets.length ? bullets : title ? [title] : []
      }))
    })
  })

  if (pages.length > 0) {
    return pages.slice(0, Math.max(form.pageCount, 1))
  }

  return [createSlide({ sectionTitle: outline.title || form.topic, title: outline.title || form.topic })]
}

function isNarrativeOutline(outline: OutlineResponse): outline is NarrativeOutline {
  return (outline as NarrativeOutline).protocolVersion === 'ppt-narrative-outline.v1'
}

function pageContentToText(pageContent?: PageContentProtocol | null) {
  const slide = pageContent?.slides?.[0]
  if (!slide) {
    return ''
  }
  const plainLines: string[] = []
  const addPlainLine = (value?: string) => {
    const text = (value || '').trim()
    if (!text || isDuplicatePageLine(text, plainLines)) {
      return
    }
    plainLines.push(text)
  }

  addPlainLine(slide.coreMessage)
  const bulletLines: string[] = []
  slide.displayBullets.forEach((item) => {
    const text = item.trim()
    if (text && !isDuplicatePageLine(text, [...plainLines, ...bulletLines])) {
      bulletLines.push(text)
    }
  })
  addPlainLine(slide.actionableTakeaway || '')

  return [
    ...plainLines.slice(0, 1),
    ...bulletLines.map((item) => `- ${item}`),
    ...plainLines.slice(1)
  ].join('\n')
}

function compactPageLine(value: string) {
  return value.replace(/[\s，。；：、,.!！?？\-]/g, '')
}

function isDuplicatePageLine(candidate: string, existing: string[]) {
  const compactCandidate = compactPageLine(candidate)
  return existing.some((item) => {
    const compactItem = compactPageLine(item)
    return (
      compactCandidate === compactItem ||
      (compactCandidate.length >= 18 && compactItem.includes(compactCandidate)) ||
      (compactItem.length >= 18 && compactCandidate.includes(compactItem))
    )
  })
}

function pageContentToSpeakerNotes(pageContent?: PageContentProtocol | null) {
  return pageContent?.slides?.[0]?.speakerNotes?.trim() || ''
}

function normalizeOutlineSlides() {
  renumberSectionIdsInOrder()
  slides.value.forEach((slide, index) => {
    slide.slideNumber = index + 1
    slide.protocolSlideId = `slide-${String(index + 1).padStart(3, '0')}`
  })
  if (outlineProtocolMeta.value) {
    outlineProtocolMeta.value.targetSlideCount = slides.value.length
  }
}

/** 按文档顺序将连续章节重编号为 sec-01、sec-02… */
function renumberSectionIdsInOrder() {
  if (!slides.value.length) {
    return
  }

  let sectionNumber = 0
  let previousGroupKey: string | null = null

  slides.value.forEach((slide) => {
    const groupKey = slide.sectionId || `__${slide.sectionTitle || 'section'}`
    if (groupKey !== previousGroupKey) {
      sectionNumber += 1
      previousGroupKey = groupKey
    }
    slide.sectionId = `sec-${String(sectionNumber).padStart(2, '0')}`
  })
}

function insertSlideAt(insertIndex: number, input: Partial<SlidePage> = {}) {
  const slide = createSlide({
    slideRole: slides.value.length === 0 ? 'cover' : 'content',
    title: `新增页面 ${slides.value.length + 1}`,
    bullets: [],
    ...input
  })
  const next = [...slides.value]
  next.splice(insertIndex, 0, slide)
  slides.value = next
  normalizeOutlineSlides()
  activeSlideId.value = slide.id
  return slide
}

function moveSlideToSectionEnd(slideId: string, targetSectionId: string) {
  const fromIndex = slides.value.findIndex((slide) => slide.id === slideId)
  if (fromIndex < 0) {
    return
  }

  const next = [...slides.value]
  const [item] = next.splice(fromIndex, 1)

  let insertAt = next.length
  for (let index = next.length - 1; index >= 0; index -= 1) {
    if (next[index].sectionId === targetSectionId) {
      insertAt = index + 1
      break
    }
  }

  next.splice(insertAt, 0, item)
  slides.value = next
}

function addSlideInSection(section: OutlineSectionGroup) {
  insertSlideAt(section.end, {
    slideRole: 'content',
    sectionId: section.sectionId,
    sectionTitle: section.title,
    goal: section.slides[0]?.goal || '',
    title: `新增页面 ${slides.value.length + 1}`,
    bullets: []
  })
}

function addSectionAfter(section: OutlineSectionGroup) {
  insertSlideAt(section.end, {
    slideRole: 'content',
    sectionId: '__new_section__',
    sectionTitle: '新章节',
    goal: '',
    title: '新章节页面',
    bullets: []
  })
}

function handleSlideSectionChange(slideId: string, targetSectionId: string) {
  const slide = slides.value.find((item) => item.id === slideId)
  if (!slide) {
    return
  }

  if (targetSectionId === NEW_SECTION_OPTION) {
    slide.sectionId = '__new_section__'
    slide.sectionTitle = '新章节'
    slide.goal = ''
    moveSlideToSectionEnd(slideId, '__new_section__')
    normalizeOutlineSlides()
    return
  }

  const option = outlineSectionCatalog.value.find((item) => item.sectionId === targetSectionId)
  if (!option) {
    return
  }

  slide.sectionId = option.sectionId
  slide.sectionTitle = option.sectionTitle
  slide.goal = option.goal
  moveSlideToSectionEnd(slideId, option.sectionId)
  normalizeOutlineSlides()
}

function renameSectionGroup(section: OutlineSectionGroup, value: string) {
  const title = value.trim() || '未命名章节'
  section.slides.forEach((slide) => {
    slide.sectionTitle = title
  })
}

function syncSlideSectionFromNeighbor(index: number) {
  const slide = slides.value[index]
  const above = slides.value[index - 1]
  const below = slides.value[index + 1]

  if (above) {
    slide.sectionId = above.sectionId
    slide.sectionTitle = above.sectionTitle
    slide.goal = above.goal
    return
  }

  if (below) {
    slide.sectionId = below.sectionId
    slide.sectionTitle = below.sectionTitle
    slide.goal = below.goal
  }
}

function removeSlide(slideId: string) {
  slides.value = slides.value.filter((slide) => slide.id !== slideId)
  normalizeOutlineSlides()
}

function getSlideIndex(slide: SlidePage) {
  const index = slides.value.findIndex((item) => item.id === slide.id)
  return index >= 0 ? index : 0
}

function moveSlide(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= slides.value.length) {
    return
  }
  const next = [...slides.value]
  const [item] = next.splice(index, 1)
  next.splice(target, 0, item)
  slides.value = next
  syncSlideSectionFromNeighbor(target)
  normalizeOutlineSlides()
}

function updateBullets(slideId: string, value: string) {
  const slide = slides.value.find((item) => item.id === slideId)
  if (!slide) {
    return
  }
  slide.bullets = value.split('\n').map((line) => line.trim()).filter(Boolean)
}

function buildKnowledgeQuery(slide: SlidePage) {
  return `${form.topic}\n${slide.sectionTitle}\n${slide.title}\n${slide.bullets.join('\n')}`
}

function buildSlideGenerationContext(slide: SlidePage) {
  return [
    requirementsText.value,
    slide.knowledge ? `检索证据：\n${slide.knowledge}` : ''
  ].filter(Boolean).join('\n\n')
}

async function fillKnowledge(slide: SlidePage) {
  pageLoading.knowledge = true
  try {
    const result = await searchKnowledge(buildKnowledgeQuery(slide))
    if (result.success) {
      slide.knowledge = result.knowledge
      showToast('补充检索完成', 'success')
    } else {
      showToast(result.message || '补充检索失败', 'warning')
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    pageLoading.knowledge = false
  }
}

async function executeAllKnowledge() {
  const items = slides.value.map((slide, index) => ({
    index,
    id: slide.id,
    query: buildKnowledgeQuery(slide)
  }))
  const result = await searchKnowledgeBatch(items)
  let okCount = 0
  for (const row of result.results) {
    const slide = slides.value.find((s) => s.id === row.id)
    if (!slide) {
      continue
    }
    if (row.success) {
      slide.knowledge = row.knowledge
      okCount += 1
    }
  }
  return {
    okCount,
    failCount: slides.value.length - okCount,
    elapsedHint: result.elapsed_sec ? `，耗时 ${result.elapsed_sec}s` : ''
  }
}

async function executeAllContent() {
  const items = slides.value.map((slide, index) => ({
    index,
    id: slide.id,
    outline_node: {
      id: slide.protocolSlideId || slide.id,
      number: index + 1,
      role: slide.slideRole || 'content',
      title: slide.title,
      section: slide.sectionTitle,
      goal: slide.goal,
      bullets: slide.bullets
    },
    context: buildSlideGenerationContext(slide)
  }))
  const result = await expandContentBatch(items, requirementsText.value)
  let okCount = 0
  const failedTitles: string[] = []
  const failureMessages: string[] = []
  for (const row of result.results) {
    const slide = slides.value.find((s) => s.id === row.id)
    if (!slide) {
      continue
    }
    if (row.success) {
      slide.content = pageContentToText(row.page_content) || row.content
      slide.notes = pageContentToSpeakerNotes(row.page_content) || slide.notes
      okCount += 1
    } else {
      failedTitles.push(slide.title || `第 ${row.index + 1} 页`)
      if (row.message && !failureMessages.includes(row.message)) {
        failureMessages.push(row.message)
      }
    }
  }
  return {
    okCount,
    failCount: slides.value.length - okCount,
    failedTitles,
    failureMessages,
    elapsedHint: result.elapsed_sec ? `，耗时 ${result.elapsed_sec}s` : ''
  }
}

async function fillAllKnowledge() {
  if (slides.value.length === 0) {
    showToast('请先完成大纲', 'warning')
    return
  }
  allKnowledgeLoading.value = true
  try {
    const { okCount, failCount, elapsedHint } = await executeAllKnowledge()
    if (failCount === 0) {
      showToast(`一键检索完成（${okCount} 页${elapsedHint}）`, 'success')
    } else {
      showToast(
        `检索完成 ${okCount} 页，失败 ${failCount} 页${elapsedHint}`,
        failCount === slides.value.length ? 'error' : 'warning'
      )
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    allKnowledgeLoading.value = false
  }
}

async function handleOneClickPipelineFromOutline() {
  if (!form.topic.trim()) {
    showToast('请先填写主题', 'warning')
    return
  }

  pipelineLoading.value = true
  try {
    outlineLoading.value = true
    const outlineOutcome = await executeGenerateOutline()
    outlineLoading.value = false
    if (!outlineOutcome.ok) {
      showToast(outlineOutcome.message || '大纲生成失败，流程已中止', 'error')
      return
    }

    allKnowledgeLoading.value = true
    const knowledgeStats = await executeAllKnowledge()
    allKnowledgeLoading.value = false

    allContentLoading.value = true
    const contentStats = await executeAllContent()
    allContentLoading.value = false

    saveCurrentRecord(false)
    generationStepIndex.value = generationSteps.length - 1

    const quotaMessage = contentStats.failureMessages.find((message) => message.includes('限额拦截'))
    if (quotaMessage) {
      showToast(quotaMessage, 'error')
      return
    }

    const totalFail = knowledgeStats.failCount + contentStats.failCount
    const summary = `大纲已生成，检索 ${knowledgeStats.okCount}/${slides.value.length} 页，正文 ${contentStats.okCount}/${slides.value.length} 页`
    if (totalFail === 0) {
      showToast(`${summary}，已跳转至最终文本${contentStats.elapsedHint}`, 'success')
    } else {
      showToast(`${summary}，部分失败，已跳转至最终文本`, 'warning')
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    outlineLoading.value = false
    allKnowledgeLoading.value = false
    allContentLoading.value = false
    pipelineLoading.value = false
  }
}

async function generateSlideContent(slide: SlidePage): Promise<{ ok: boolean; message?: string }> {
  const result = await expandContent(
    {
      id: slide.protocolSlideId || slide.id,
      number: slides.value.findIndex((item) => item.id === slide.id) + 1,
      role: slide.slideRole || 'content',
      title: slide.title,
      section: slide.sectionTitle,
      goal: slide.goal,
      bullets: slide.bullets
    },
    buildSlideGenerationContext(slide)
  )
  if (result.success) {
    slide.content = pageContentToText(result.page_content) || result.content
    slide.notes = pageContentToSpeakerNotes(result.page_content) || slide.notes
    return { ok: true }
  }
  return { ok: false, message: result.message }
}

async function fillContent(slide: SlidePage) {
  pageLoading.content = true
  try {
    const outcome = await generateSlideContent(slide)
    if (outcome.ok) {
      showToast('正文生成完成', 'success')
    } else {
      showToast(outcome.message || '正文生成失败', 'warning')
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    pageLoading.content = false
  }
}

function openReviseDialog() {
  const slide = activeSlide.value
  if (!slide?.content.trim()) {
    showToast('请先生成或填写正文后再修改', 'warning')
    return
  }
  reviseSuggestion.value = ''
  reviseDialogOpen.value = true
}

function closeReviseDialog() {
  if (reviseSubmitting.value) {
    return
  }
  reviseDialogOpen.value = false
}

async function submitReviseContent() {
  const slide = activeSlide.value
  if (!slide) {
    return
  }
  const suggestion = reviseSuggestion.value.trim()
  if (!suggestion) {
    showToast('请填写修改建议', 'warning')
    return
  }
  if (!slide.content.trim()) {
    showToast('当前正文为空，请先生成正文', 'warning')
    return
  }

  reviseSubmitting.value = true
  pageLoading.content = true
  try {
    const result = await reviseContent({
      outline_node: {
        title: slide.title,
        bullets: slide.bullets.slice(0, 4)
      },
      current_content: slide.content,
      revision_suggestion: suggestion
    })
    if (result.success) {
      slide.content = result.content
      saveCurrentRecord(false)
      reviseDialogOpen.value = false
      showToast('正文已按建议更新', 'success')
    } else {
      showToast(result.message || '正文修改失败', 'warning')
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    reviseSubmitting.value = false
    pageLoading.content = false
  }
}

async function fillAllContent() {
  if (slides.value.length === 0) {
    showToast('请先完成大纲', 'warning')
    return
  }
  allContentLoading.value = true
  try {
    const { okCount, failCount, failedTitles, failureMessages, elapsedHint } = await executeAllContent()
    if (failCount === 0) {
      showToast(`一键生成完成（${okCount} 页${elapsedHint}）`, 'success')
    } else {
      const quotaMessage = failureMessages.find((message) => message.includes('限额拦截'))
      if (quotaMessage) {
        showToast(quotaMessage, 'error')
        return
      }
      const failedHint = failedTitles.length > 0 ? `：${failedTitles.join('、')}` : ''
      showToast(
        `正文生成完成 ${okCount} 页，失败 ${failCount} 页${failedHint}${elapsedHint}`,
        failCount === slides.value.length ? 'error' : 'warning'
      )
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    allContentLoading.value = false
  }
}

async function fillNotes(slide: SlidePage) {
  pageLoading.notes = true
  try {
    const result = await generateNotes({
      project_id: currentRecordId.value || 'current-project',
      slide_id: slide.protocolSlideId || slide.id,
      slide_title: slide.title,
      slide_content: slide.content || slide.bullets.join('\n'),
      knowledge_evidence: slide.knowledge,
      style_requirement: requirementsText.value
    })
    if (result.success) {
      slide.notes = result.notes
      saveCurrentRecord(false)
      showToast('备注生成完成', 'success')
    } else {
      showToast(result.message || '备注生成失败', 'warning')
    }
  } catch (error) {
    showToast(getErrorMessage(error), 'error')
  } finally {
    pageLoading.notes = false
  }
}

async function checkFacts(slide: SlidePage) {
  if (!slide.content.trim()) {
    showToast('请先生成或填写正文后再做事实检查', 'warning')
    return
  }
  pageLoading.fact = true
  slide.factCheckStatus = 'review'
  try {
    const prompt = [
      '请仅对下方「正文内容」中的事实性陈述做核查，判断其是否被「检索资料」支持。',
      '不要检查、评论或质疑页面标题、章节名、汇报主题等展示性文字。',
      '不要检查演讲备注；只关注正文里的具体断言、数据、因果关系与结论。',
      '只返回简洁结论，并指出正文中无来源或与材料不一致的表述。',
      `正文内容：${slide.content}`,
      `检索资料：${slide.knowledge || '（无检索资料，仅标注正文里无法核实的断言）'}`
    ].join('\n')
    const result = await queryRag(prompt)
    if (!result.success) {
      slide.factCheckStatus = 'risk'
      slide.factCheckMessage = result.message || '检查失败'
      return
    }
    slide.factCheckMessage = result.answer
    slide.factCheckStatus = inferFactStatus(result.answer)
    showToast('事实检查完成', 'success')
  } catch (error) {
    slide.factCheckStatus = 'risk'
    slide.factCheckMessage = getErrorMessage(error)
    showToast(getErrorMessage(error), 'error')
  } finally {
    pageLoading.fact = false
  }
}

function buildMarkdown() {
  return buildMarkdownFromState(form, slides.value)
}

function buildMarkdownForRecord(record: ProjectRecord) {
  return buildMarkdownFromState(record.form, record.slides)
}

function buildMarkdownFromState(sourceForm: ProjectForm, sourceSlides: SlidePage[]) {
  const title = sourceForm.topic || '未命名 PPT'
  const lines: string[] = [
    `# ${title}`,
    '',
    `- 使用场景：${sourceForm.scene}`,
    `- 目标页数：${sourceForm.pageCount}`,
    `- 受众对象：${sourceForm.audience || '未填写'}`,
    `- 额外要求：${sourceForm.requirements || '无'}`,
    ''
  ]

  sourceSlides.forEach((slide, index) => {
    lines.push(`## ${index + 1}. ${slide.title || '未命名页面'}`)
    lines.push('')
    lines.push('### 核心目标')
    lines.push(slide.goal || '未填写')
    lines.push('')
    lines.push('### 要点')
    if (slide.bullets.length) {
      slide.bullets.forEach((bullet) => lines.push(`- ${bullet}`))
    } else {
      lines.push('- 未填写')
    }
    lines.push('')
    lines.push('### 正文')
    lines.push(slide.content || '未生成')
    lines.push('')
    lines.push('### 演讲备注')
    lines.push(slide.notes || '未生成')
    lines.push('')
  })

  return lines.join('\n')
}

async function copyMarkdown() {
  try {
    await navigator.clipboard.writeText(markdownText.value)
    showToast('Markdown 已复制', 'success')
  } catch {
    showToast('复制失败，请手动选择文本', 'warning')
  }
}

function downloadMarkdown() {
  const blob = new Blob([markdownText.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeFileName(form.topic || 'POGCC-PPT')}.md`
  link.click()
  URL.revokeObjectURL(url)
  saveCurrentRecord()
}

function downloadMarkdownForRecord(record: ProjectRecord) {
  const content = record.markdown || buildMarkdownForRecord(record)
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeFileName(record.title || record.form.topic || 'POGCC-PPT')}.md`
  link.click()
  URL.revokeObjectURL(url)
}

function saveCurrentRecord(showMessage = true) {
  if (!hasCurrentProjectContent()) {
    if (showMessage) {
      showToast('当前还没有可保存的任务内容', 'warning')
    }
    return
  }
  const now = new Date().toISOString()
  const record: ProjectRecord = {
    id: currentRecordId.value,
    title: form.topic || '未命名任务',
    createdAt: createdAt.value,
    updatedAt: now,
    form: { ...form },
    references: references.value.map((doc) => ({ ...doc })),
    slides: slides.value.map((slide) => ({ ...slide, bullets: [...slide.bullets] })),
    markdown: markdownText.value
  }
  historyRecords.value = upsertRecord(record)
  if (showMessage) {
    showToast('已保存到历史记录', 'success')
  }
}

function startNewProject() {
  if (hasCurrentProjectContent()) {
    saveCurrentRecord(false)
  }
  currentRecordId.value = createId()
  createdAt.value = new Date().toISOString()
  Object.assign(form, {
    topic: '',
    scene: '学术汇报',
    pageCount: 10,
    audience: '',
    requirements: ''
  })
  references.value = []
  slides.value = []
  activeSlideId.value = ''
  selectedHistoryId.value = null
  generationStepIndex.value = 0
  activeMode.value = 'generate'
  showToast('已新建 PPT 任务', 'success')
}

function hasCurrentProjectContent() {
  return Boolean(
    form.topic.trim() ||
    form.audience.trim() ||
    form.requirements.trim() ||
    references.value.some((doc) => doc.filePath.trim() || doc.status !== 'pending') ||
    slides.value.length > 0
  )
}

function normalizeReferences(docs: ReferenceDoc[]) {
  return docs.map((doc) =>
    doc.status === 'parsing'
      ? { ...doc, status: 'pending' as const, message: '入库未完成，请重新添加' }
      : { ...doc }
  )
}

function restoreRecord(record: ProjectRecord) {
  currentRecordId.value = record.id
  createdAt.value = record.createdAt
  Object.assign(form, record.form)
  references.value = normalizeReferences(record.references.map((doc) => ({ ...doc })))
  slides.value = record.slides.map((slide) => ({ ...slide, bullets: [...slide.bullets] }))
  normalizeOutlineSlides()
  activeSlideId.value = slides.value[0]?.id ?? ''
  generationStepIndex.value = getRestoreStepIndex(record)
  activeMode.value = 'generate'
  selectedHistoryId.value = null
  showToast('历史记录已恢复到生成流程', 'success')
}

function getRestoreStepIndex(record: ProjectRecord) {
  if (record.slides.length > 0 && record.slides.every((slide) => slide.content.trim())) {
    return 4
  }
  if (record.slides.length > 0) {
    return 2
  }
  if (record.references.some((doc) => doc.filePath)) {
    return 1
  }
  return 0
}

function removeHistoryRecord(recordId: string) {
  historyRecords.value = deleteRecord(recordId)
  if (selectedHistoryId.value === recordId) {
    selectedHistoryId.value = null
  }
}

function createSlide(input: Partial<SlidePage> = {}): SlidePage {
  return {
    id: createId(),
    protocolSlideId: input.protocolSlideId,
    slideNumber: input.slideNumber,
    slideRole: input.slideRole || 'content',
    sectionId: input.sectionId,
    slideRange: input.slideRange,
    sectionTitle: input.sectionTitle || '',
    title: input.title || '',
    goal: input.goal || '',
    bullets: input.bullets || [],
    knowledge: input.knowledge || '',
    content: input.content || '',
    notes: input.notes || '',
    factCheckStatus: input.factCheckStatus || 'pending',
    factCheckMessage: input.factCheckMessage || ''
  }
}

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function cleanTitle(value: string) {
  return value.replace(/^[0-9]+[.)、]\s*/, '').replace(/^[a-zA-Z][.)、]\s*/, '').trim()
}

function safeFileName(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, '_').trim() || 'POGCC-PPT'
}

function inferFactStatus(answer: string): FactCheckStatus {
  if (/不一致|无来源|风险|错误|缺少|无法验证/.test(answer)) {
    return 'risk'
  }
  if (/通过|一致|支持/.test(answer)) {
    return 'passed'
  }
  return 'review'
}

function factStatusText(status: FactCheckStatus) {
  const map: Record<FactCheckStatus, string> = {
    pending: '待检查',
    passed: '通过',
    review: '需人工确认',
    risk: '存在风险'
  }
  return map[status]
}

function factStatusClass(status: FactCheckStatus) {
  return {
    pending: 'status-neutral',
    passed: 'status-ok',
    review: 'status-warn',
    risk: 'status-danger'
  }[status]
}

function docStatusText(status: ReferenceStatus) {
  const map: Record<ReferenceStatus, string> = {
    pending: '待入库',
    parsing: '解析中',
    stored: '已入库',
    failed: '解析失败'
  }
  return map[status]
}

function docStatusClass(status: ReferenceStatus) {
  return {
    pending: 'status-neutral',
    parsing: 'status-warn',
    stored: 'status-ok',
    failed: 'status-danger'
  }[status]
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

function showToast(message: string, type: 'success' | 'warning' | 'error' = 'success') {
  toast.value = { message, type }
  window.setTimeout(() => {
    toast.value = null
  }, 2600)
}

function getErrorMessage(error: unknown) {
  return formatApiError(error)
}
</script>
