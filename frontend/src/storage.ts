import type { ProjectRecord } from './types'

const HISTORY_KEY = 'pogcc.project.history'

export function loadHistory(): ProjectRecord[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveHistory(records: ProjectRecord[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(records))
}

export function upsertRecord(record: ProjectRecord) {
  const records = loadHistory()
  const next = [record, ...records.filter((item) => item.id !== record.id)].slice(0, 20)
  saveHistory(next)
  return next
}

export function deleteRecord(recordId: string) {
  const next = loadHistory().filter((item) => item.id !== recordId)
  saveHistory(next)
  return next
}
